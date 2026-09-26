"""Stage 4 interfaces exercised only in temporary packages with blocked I/O."""
import copy
import fcntl
import gzip
import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

with patch('dotenv.load_dotenv'):
    from src.backtesting import sic_stage4 as study

CIK = '0000000001'
ACC = '0000000001-20-000001'
CASE = dict(label='EXAMPLE', cik=CIK, start='2020-01-01', end_exclusive='2022-01-01',
            expected_names=['Example Inc'], reason='Identity fixture', saved_local_identities=[], candidate_pair=None)


def header(acc=ACC, form='10-K', role='FILER', cik=CIK, sic='1234', clock='20200102120000'):
    return f'''<pre>ACCESSION NUMBER: {acc}
ACCEPTANCE-DATETIME: {clock}
CONFORMED SUBMISSION TYPE: {form}
FILED AS OF DATE: 20200102
{role}:
COMPANY CONFORMED NAME: Example Inc
CENTRAL INDEX KEY: {cik}
STANDARD INDUSTRIAL CLASSIFICATION: EXAMPLE [{sic}]
</pre>'''.encode()


def row(acc=ACC, form='10-K', stamp='2020-01-02T17:00:00Z'):
    return dict(accessionNumber=acc, filingDate='2020-01-02', acceptanceDateTime=stamp,
                form=form, primaryDocument='example.htm', reportDate='2019-12-31')


def main_catalog(rows, cik=CIK, name='Example Inc', shards=None):
    columns = {k: [r[k] for r in rows] for k in row()}
    return dict(cik=cik, name=name, formerNames=[], filings=dict(recent=columns, files=shards or []))


class Stage4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'stage4'
        self.old = self.base / 'stage3'
        self.cache = self.base / 'cache'
        self.cache.mkdir()
        self.old.mkdir()
        for target in ('socket.socket.connect', 'socket.create_connection', 'requests.sessions.Session.request',
                       'psycopg.connect', 'src.database.get_connection'):
            p = patch(target, side_effect=AssertionError('Real network/database forbidden'))
            p.start(); self.addCleanup(p.stop)

    def package(self, rows=None, reused=None, cached=None, cases=None, bodies=None):
        rows = [row()] if rows is None else rows
        cases = [copy.deepcopy(CASE)] if cases is None else cases
        data = dict(roster=[], catalogs={CIK: rows}, events=[], baseline={'fixture': True}, source_hashes={})
        if cached is not None:
            data['catalogs'] = {}
            study.frozen(self.cache / f'CIK{CIK}.json', cached)
        study.frozen(self.old / 'inputs.json', data)
        observations = []
        for fixture in reused or []:
            acc, raw = fixture[:2]; cik = fixture[2] if len(fixture) == 3 else CIK
            p = self.old / 'headers' / (acc+'.json')
            study.frozen(p, dict(raw_header=raw.decode(), sha256=study.sha(raw)))
            observations.append(dict(cik=cik, accession=acc, source_path=str(p), sha256=study.sha(raw)))
        study.frozen(self.old / 'results.json', dict(observations=observations))
        for fixture in bodies or []:
            acc, raw = fixture[:2]; cik = fixture[2] if len(fixture) == 3 else CIK
            p = self.old/'body'/f'{cik}_{acc}.json'
            p.parent.mkdir(parents=True, exist_ok=True)
            blob = p.with_suffix('.html.gz'); blob.write_bytes(gzip.compress(raw))
            study.frozen(p, dict(kind='body', cik=cik, accession=acc, document='example.htm',
                                raw_gzip=str(blob), sha256=study.sha(raw)))
        for name in ('identity_review.json', 'policy_recommendations.json'): study.frozen(self.old/name, {})
        study.frozen(self.old/'validation.json', dict(files=[dict(path=str(self.old/name), sha256=study.sha((self.old/name).read_bytes()))
                                                           for name in ('inputs.json','results.json','identity_review.json','policy_recommendations.json')]))
        return study.prepare(self.root, stage3=self.old, cache=self.cache, roster=cases, ticker_path=self.base/'missing.json')

    def review(self, **kwargs):
        n = len(list(self.root.glob('review_*.json')))+1
        d = dict(inputs_sha256=study.sha((self.root/'inputs.json').read_bytes()), reviewed_by='fixture reviewer',
                 issuer_reviews=[], relationships=[], eight_k_intervals=[], clock_reviews=[], identity_requests=[])
        rows = study.ledger(self.root)
        if rows: d['continuation'] = dict(ledger_sha256=study.digest(rows), acknowledged_attempts=[r['attempt'] for r in rows if r['outcome'] != 'SUCCESS'])
        d.update(kwargs)
        p = self.root / f'review_{n:02d}.json'
        study.frozen(p, d)
        return p, study.sha(p.read_bytes())

    def plan(self, review=None):
        result = study.plan_requests(self.root, *(review or (None, None)))
        return Path(result['path']), result['sha256']

    def success(self, raw=None):
        return patch.object(study, 'transport', return_value=(200, raw or header(), 'SUCCESS'))

    def test_default_invocation_has_no_action(self):
        with patch.object(study, 'prepare') as p, patch.object(study, 'fetch') as f, patch.object(study, 'analyze') as a:
            with patch('sys.stdout', new=io.StringIO()) as output:
                study.main(['--package-dir', str(self.root)])
                self.assertIn('--fetch', output.getvalue())
        p.assert_not_called(); f.assert_not_called(); a.assert_not_called()
        self.assertFalse(self.root.exists())

    def test_prepare_freezes_candidates_and_unknown_ids(self):
        result = self.package()
        self.assertEqual(result['unknown'], [CIK])
        d = study.load_inputs(self.root)
        self.assertEqual(d['cap'], 240)
        self.assertFalse(study.read(self.root/'candidate_review.json')[CIK]['issuer_identity_accepted'])
        self.assertEqual(d['roster'][0]['saved_local_identities'], [])
        before = (self.root/'inputs.json').read_bytes()
        with self.assertRaises(study.GuardFailure): study.prepare(self.root, self.old, self.cache, [CASE])
        self.assertEqual(before, (self.root/'inputs.json').read_bytes())

    def test_saved_candidate_contradiction_blocks_case(self):
        result = self.package(cached=main_catalog([row()], cik='0000000002', name='Other Issuer'))
        self.assertEqual(result['blocked'], [CIK])
        with self.assertRaises(study.GuardFailure): self.plan()
        p, _ = self.plan(self.review(acknowledged_contradictions=[CIK]))
        self.assertEqual(study.read(p)['requests'], [])
        self.assertIn(CIK, study.read(p)['blocked_cases'])

    def test_matching_saved_name_is_only_candidate_support(self):
        self.package(cached=main_catalog([row()]))
        c = study.read(self.root/'candidate_review.json')[CIK]
        self.assertEqual(c['status'], 'SUPPORTED_CANDIDATE')
        self.assertFalse(c['issuer_identity_accepted'])
        self.assertTrue(c['supporting_sources'][0]['path'])

    def test_changed_saved_stage3_metadata_is_not_trusted(self):
        self.package()
        (self.old/'inputs.json').write_bytes((self.old/'inputs.json').read_bytes()+b' ')
        with self.assertRaises(study.GuardFailure):
            study.prepare(self.base/'another', self.old, self.cache, [CASE], ticker_path=self.base/'missing')

    def test_default_twenty_candidate_roster_in_temporary_fixture(self):
        self.package()
        from src.backtesting.sic_stage3 import CASES
        original = study.read(self.old/'inputs.json')
        original['roster'] = [dict(label=label, cik=f'{n:010d}', start=start+'-01-01', end_exclusive=end+'-01-01',
                                  reason=reason, identities=[dict(verified_header_names=['Example Inc'])])
                              for n, (label, start, end, reason) in enumerate(CASES, 1)]
        (self.old/'inputs.json').write_bytes(study.encoded(original))
        pins = study.read(self.old/'validation.json')
        pins['files'][0]['sha256'] = study.sha((self.old/'inputs.json').read_bytes())
        (self.old/'validation.json').write_bytes(study.encoded(pins))
        result = study.prepare(self.base/'default_roster', self.old, self.cache, ticker_path=self.base/'missing')
        self.assertEqual(result['candidates'], 20)
        rows = study.read(self.base/'default_roster/inputs.json')['roster']
        self.assertEqual(len({r['cik'] for r in rows}), 20)
        self.assertEqual([r['label'] for r in rows[:10]], [r[0] for r in CASES])
        self.assertTrue(all(not r['saved_local_identities'] for r in rows[10:]))

    def test_saved_evidence_is_independent_of_later_source_changes(self):
        self.package(reused=[(ACC, header())])
        before = study.all_evidence(self.root)
        for p in (self.old/'headers').glob('*'): p.write_text('changed source')
        self.assertEqual(study.all_evidence(self.root), before)
        p, h = self.plan()
        self.assertEqual(study.read(p)['requests'], [])
        with patch.object(study, 'transport') as transport: study.fetch(self.root, p, h)
        transport.assert_not_called()

    def test_original_pinned_shard_supplies_seed_without_refresh(self):
        self.package()
        prior = row('0000000001-19-000001'); prior['filingDate'] = '2019-12-01'
        prior['acceptanceDateTime'] = '2019-12-01T17:00:00Z'
        path = self.cache/f'CIK{CIK}-submissions-001.json'
        study.frozen(path, main_catalog([prior, row()])['filings']['recent'])
        d = study.read(self.old/'inputs.json'); d['source_hashes'] = {str(path): study.sha(path.read_bytes())}
        (self.old/'inputs.json').write_bytes(study.encoded(d))
        validation = study.read(self.old/'validation.json'); validation['files'][0]['sha256'] = study.sha((self.old/'inputs.json').read_bytes())
        (self.old/'validation.json').write_bytes(study.encoded(validation))
        package = self.base/'seed_package'
        study.prepare(package, self.old, self.cache, [CASE], ticker_path=self.base/'missing')
        result = study.plan_requests(package)
        requests = study.read(result['path'])['requests']
        self.assertEqual([i['accession'] for i in requests if i['envelope'] == 'seed'], [prior['accessionNumber']])
        self.assertTrue(all(i['kind'] == 'header' for i in requests))

    def test_corrupt_saved_blob_refuses_refetch(self):
        self.package(reused=[(ACC, header())])
        e = study.read(self.root/'reuse_manifest.json')[0]
        (self.root/e['blob']).write_bytes(gzip.compress(b'changed'))
        with patch.object(study, 'transport') as transport:
            with self.assertRaises(study.GuardFailure): self.plan()
        transport.assert_not_called()

    def test_plan_pin_inputs_code_and_review_changes_rejected(self):
        self.package()
        p, h = self.plan()
        with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, '0'*64)
        original = p.read_bytes(); p.write_bytes(original+b' ')
        with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)
        p.write_bytes(original)
        with patch.object(study, 'code_pins', return_value={}):
            with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)
        (self.root/'inputs.json').write_bytes((self.root/'inputs.json').read_bytes()+b' ')
        with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)

    def test_review_hash_and_input_pin_required(self):
        self.package()
        p, h = self.review()
        with self.assertRaises(study.GuardFailure): study.plan_requests(self.root, p, '0'*64)
        d = study.read(p); d['inputs_sha256'] = '0'*64
        p.write_bytes(study.encoded(d))
        with self.assertRaises(study.GuardFailure): study.plan_requests(self.root, p, study.sha(p.read_bytes()))

    def test_reservation_is_persisted_before_transport(self):
        self.package(); p, h = self.plan()
        def call(item):
            rows = study.ledger(self.root)
            self.assertEqual(rows[0]['outcome'], 'IN_FLIGHT')
            self.assertEqual(study.read(self.root/'attempts/000001.json')['outcome'], 'IN_FLIGHT')
            return 200, header(), 'SUCCESS'
        with patch.object(study, 'transport', side_effect=call): study.fetch(self.root, p, h)
        self.assertEqual(study.ledger(self.root)[0]['outcome'], 'SUCCESS')
        with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)

    def test_failure_retry_restart_and_per_url_ceiling(self):
        self.package()
        for n in range(3):
            p, h = self.plan(None if n == 0 else self.review())
            with patch.object(study, 'transport', side_effect=RuntimeError('Suppressed transport detail')):
                with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)
            rows = study.ledger(self.root)
            self.assertEqual(len(rows), n+1)
            self.assertEqual(rows[-1]['charged_envelope'], 'periodic' if n == 0 else 'contingency')
            with self.assertRaises(study.GuardFailure): self.plan()
        with self.assertRaises(study.GuardFailure): self.plan(self.review())

    def test_interrupt_consumes_attempt_and_requires_review(self):
        self.package(); p, h = self.plan()
        with patch.object(study, 'transport', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): study.fetch(self.root, p, h)
        self.assertEqual(study.ledger(self.root)[0]['outcome'], 'IN_FLIGHT')
        with self.assertRaises(study.GuardFailure): self.plan()
        p, _ = self.plan(self.review())
        self.assertEqual(study.read(p)['requests'][0]['charged_envelope'], 'contingency')

    def test_interrupt_after_raw_response_never_refetches_it(self):
        self.package(); p, h = self.plan()
        with self.success(), patch.object(study, 'parse_observation', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): study.fetch(self.root, p, h)
        self.assertEqual(study.ledger(self.root)[0]['outcome'], 'IN_FLIGHT')
        self.assertEqual(study.evidence_raw(self.root, study.all_evidence(self.root)[0]), header())
        p, _ = self.plan(self.review())
        self.assertEqual(study.read(p)['requests'], [])

    def test_ledger_cannot_be_reset_or_reservation_changed(self):
        self.package(); p, h = self.plan()
        with self.success(): study.fetch(self.root, p, h)
        (self.root/'requests.json').write_bytes(study.encoded([]))
        with self.assertRaises(study.GuardFailure): study.ledger(self.root)
        (self.root/'requests.json').unlink()
        with self.assertRaises(FileNotFoundError): study.ledger(self.root)

    def test_ledger_digest_matches_saved_snapshot_hash(self):
        self.package(); p, h = self.plan()
        with self.success(): study.fetch(self.root, p, h)
        self.assertEqual(study.digest(study.ledger(self.root)), study.sha((self.root/'requests.json').read_bytes()))

    def test_envelope_and_stage_cap_include_interrupted_reservations(self):
        self.package()
        for category, maximum in study.ENVELOPES.items():
            for n in range(maximum):
                acc = f'0000000001-20-{len(study.ledger(self.root))+1:06d}'
                kind = 'body' if category == 'identity' and n < 30 else 'header'
                item = dict(kind=kind, cik=CIK, accession=acc, envelope=category)
                if kind == 'body': item['document'] = 'example.htm'
                study.reserve(self.root, item, 'fixture', category)
            with self.assertRaises(study.GuardFailure):
                study.reserve(self.root, dict(kind='header', cik=CIK, accession='0000000001-20-999999'), 'fixture', category)
        self.assertEqual(len(study.ledger(self.root)), 240)
        self.assertTrue(all(r['outcome'] == 'IN_FLIGHT' for r in study.ledger(self.root)))

    def test_lock_excludes_prepare_plan_fetch_analysis(self):
        self.package(); p, h = self.plan()
        with (self.root/'.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for fn in (lambda: self.plan(), lambda: study.fetch(self.root, p, h), lambda: study.analyze(self.root)):
                with self.assertRaises(study.GuardFailure): fn()

    def test_catalogue_batch_ten_header_batch_twenty(self):
        cases = [dict(CASE, cik=f'{n:010d}') for n in range(1, 16)]
        self.package(rows=[], cases=cases)
        p, _ = self.plan()
        self.assertEqual(len(study.read(p)['requests']), 10)
        self.assertTrue(all(i['kind'] == 'catalogue' for i in study.read(p)['requests']))

    def test_header_batch_twenty_and_plan_preflight_rejects_oversize(self):
        self.package(rows=[row(f'0000000001-20-{n:06d}') for n in range(1, 26)])
        p, _ = self.plan()
        data = study.read(p); self.assertEqual(len(data['requests']), 20)
        extra = dict(data['requests'][-1], accession='0000000001-20-000025')
        extra['url'] = study.url(extra); data['requests'].append(extra); p.write_bytes(study.encoded(data))
        with patch.object(study, 'transport') as transport:
            with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, study.sha(p.read_bytes()))
        transport.assert_not_called()

    def test_denial_redirect_and_size_are_persistent_stops(self):
        self.package(); p, h = self.plan()
        with patch.object(study, 'transport', return_value=(429, b'', 'HTTP_FAILURE')):
            with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)
        with self.assertRaises(study.GuardFailure): self.plan(self.review())

    def test_redirect_and_size_stops_cannot_be_acknowledged_away(self):
        self.package()
        for status, outcome in ((302, 'HTTP_FAILURE'), (200, 'SIZE_FAILURE')):
            rows = [dict(attempt=1, outcome=outcome, status=status)]
            with self.assertRaises(study.GuardFailure):
                study.stop_review(rows, dict(continuation=dict(ledger_sha256=study.digest(rows), acknowledged_attempts=[1])))

    def test_transport_has_one_bounded_nonredirecting_call(self):
        response = MagicMock(); response.status_code = 200
        response.__enter__.return_value = response
        response.iter_content.return_value = [header()]
        item = dict(kind='header', cik=CIK, accession=ACC)
        with patch('src.sec.sec_http._pace') as pace, patch('requests.get', return_value=response) as get:
            status, raw, outcome = study.transport(item)
        pace.assert_called_once(); get.assert_called_once()
        self.assertEqual((status, raw, outcome), (200, header(), 'SUCCESS'))
        self.assertFalse(get.call_args.kwargs['allow_redirects'])
        self.assertEqual(get.call_args.kwargs['timeout'], (10, 30))
        response.iter_content.return_value = [b'x' * 262145]
        with patch('src.sec.sec_http._pace'), patch('requests.get', return_value=response):
            self.assertEqual(study.transport(item)[2], 'SIZE_FAILURE')

    def test_raw_processing_failure_is_saved_never_refetched(self):
        self.package(); p, h = self.plan()
        with self.success(b'malformed header'):
            with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)
        rows = study.ledger(self.root)
        self.assertEqual(rows[0]['outcome'], 'PROCESSING_FAILURE')
        self.assertEqual(study.evidence_raw(self.root, rows[0]['evidence']), b'malformed header')
        p, _ = self.plan(self.review())
        self.assertEqual(study.read(p)['requests'], [])
        report = study.analyze(self.root)
        results = study.read(Path(report['path'])/'results.json')
        self.assertFalse(results['windows'][0]['periodic_complete'])
        self.assertEqual(len(results['rejected_headers']), 1)

    def test_identity_header_without_form_hint_still_checks_catalogue(self):
        self.package(reused=[(ACC, header())], rows=[row(), row('0000000001-20-000002', 'SD')])
        acc2 = '0000000001-20-000002'
        review = self.review(identity_requests=[dict(kind='header', cik=CIK, accession=acc2, reason='Dated identity evidence')])
        p, h = self.plan(review)
        with self.success(header(acc2, form='8-K')):
            with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)
        self.assertEqual(study.ledger(self.root)[0]['outcome'], 'PROCESSING_FAILURE')

    def test_discovery_and_shards_use_same_budget(self):
        self.package(rows=[], cases=[dict(CASE, cik='0000000002')])
        p, h = self.plan()
        data = main_catalog([row()], cik='0000000002', shards=[dict(name='CIK0000000002-submissions-001.json', filingFrom='2019-01-01', filingTo='2021-01-01')])
        with self.success(study.encoded(data)): study.fetch(self.root, p, h)
        p, _ = self.plan(self.review())
        self.assertEqual(study.read(p)['requests'][0]['kind'], 'shard')
        self.assertEqual(study.ledger(self.root)[0]['charged_envelope'], 'catalogue')

    def test_reviewed_exhibit_consumes_identity_document_budget(self):
        self.package()
        review = self.review(identity_requests=[dict(kind='exhibit', cik=CIK, accession=ACC, document='action.htm', reason='Explicit action assertion')])
        p, h = self.plan(review)
        def response(item): return 200, header() if item['kind'] == 'header' else b'<html>Action assertion</html>', 'SUCCESS'
        with patch.object(study, 'transport', side_effect=response): study.fetch(self.root, p, h)
        rows = study.ledger(self.root)
        self.assertEqual([r['charged_envelope'] for r in rows], ['periodic', 'identity'])
        self.assertEqual(rows[1]['item']['kind'], 'exhibit')
        self.assertEqual(len(rows), 2)

    def test_changed_review_and_stale_plan_refuse_before_transport(self):
        self.package()
        review = self.review(); p, h = self.plan(review)
        r = review[0]; r.write_bytes(r.read_bytes()+b' ')
        with patch.object(study, 'transport') as transport:
            with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)
        transport.assert_not_called()

    def test_no_budget_transfer_in_edited_plan(self):
        self.package(); p, _ = self.plan()
        d = study.read(p); d['requests'][0]['charged_envelope'] = 'contingency'
        p.write_bytes(study.encoded(d))
        with patch.object(study, 'transport') as transport:
            with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, study.sha(p.read_bytes()))
        transport.assert_not_called()

    def test_fetched_candidate_contradiction_keeps_raw_and_blocks_case(self):
        self.package(rows=[], cases=[dict(CASE, cik='0000000002')]); p, h = self.plan()
        raw = study.encoded(main_catalog([], cik='0000000002', name='Unrelated Issuer'))
        with self.success(raw):
            with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)
        self.assertEqual(study.ledger(self.root)[0]['outcome'], 'SUCCESS')
        review = self.review(acknowledged_contradictions=['0000000002'])
        p, _ = self.plan(review)
        self.assertEqual(study.read(p)['requests'], [])

    def test_invalid_discovery_report_preserves_partial_results(self):
        self.package(rows=[], cases=[dict(CASE, cik='0000000002')]); p, h = self.plan()
        with self.success(b'not-json'):
            with self.assertRaises(study.GuardFailure): study.fetch(self.root, p, h)
        report = study.analyze(self.root)
        w = study.read(Path(report['path'])/'coverage.json')[0]
        self.assertFalse(w['catalog_known']); self.assertFalse(w['periodic_complete'])
        self.assertTrue(w['candidate_review']['contradictions'])

    def test_form_role_isolation_and_same_instant_conflict(self):
        for role in ('ISSUER', 'SUBJECT COMPANY', 'REPORTING-OWNER'):
            with self.assertRaises(ValueError): study.parse_observation(header(role=role).decode(), CIK, ACC)
        raw = header(cik='0000000002').decode().replace('</pre>', '')+'FILER:\nCENTRAL INDEX KEY: '+CIK+'\n</pre>'
        with self.assertRaises(ValueError): study.parse_observation(raw, CIK, ACC)
        a = study.parse_observation(header().decode(), CIK, ACC)
        b = study.parse_observation(header(acc='0000000001-20-000002', sic='5678').decode(), CIK, '0000000001-20-000002')
        self.assertEqual(study.lookup([a, b], CIK, study.instant('2020-01-03T00:00:00Z'))['status'], 'AMBIGUOUS')

    def identities(self, conflict=False):
        self.package(reused=[(ACC, header())], rows=[row(stamp='2020-01-02T12:00:00Z' if conflict else '2020-01-02T17:00:00Z')])
        entries = study.all_evidence(self.root); inputs = study.load_inputs(self.root)
        catalogs, _, _ = study.inventories(self.root, inputs, entries)
        obs, _, clocks, _ = study.header_observations(self.root, inputs, entries, catalogs)
        proof = dict(url=entries[0]['url'], sha256=entries[0]['sha256'], quote='Example Inc', location='FILER company name')
        identity = dict(cik=CIK, status='ACCEPTED', reviewed_by='fixture', knowledge_at='2020-01-01T00:00:00Z', evidence=[proof])
        review = dict(issuer_reviews=[identity], relationships=[], clock_reviews=[])
        return entries, obs, clocks, review

    def test_identity_known_at_never_predates_disclosure(self):
        entries, obs, _, review = self.identities()
        early = study.gated_lookup(self.root, review, entries, obs, CIK, study.instant('2020-01-02T16:59:59Z'))
        self.assertEqual(early['status'], 'UNKNOWN')
        later = study.gated_lookup(self.root, review, entries, obs, CIK, study.instant('2020-01-02T17:00:00Z'))
        self.assertEqual(later['status'], 'CLASSIFIED')
        self.assertEqual(study.gated_lookup(self.root, review, entries, obs, CIK, study.instant('2020-01-03T00:00:00Z'), 999)['status'], 'UNKNOWN')

    def test_future_identity_conflict_does_not_leak_back(self):
        entries, obs, _, review = self.identities()
        review['issuer_reviews'].append(dict(cik=CIK, status='CONFLICT', knowledge_at='2021-01-01T00:00:00Z'))
        self.assertEqual(study.gated_lookup(self.root, review, entries, obs, CIK, study.instant('2020-01-03T00:00:00Z'))['status'], 'CLASSIFIED')
        self.assertEqual(study.gated_lookup(self.root, review, entries, obs, CIK, study.instant('2021-01-03T00:00:00Z'))['status'], 'AMBIGUOUS')

    def test_undated_conflict_is_unknown_never_silently_dismissed(self):
        entries, obs, _, review = self.identities()
        review['issuer_reviews'].append(dict(cik=CIK, status='CONFLICT', knowledge_at=None))
        self.assertEqual(study.gated_lookup(self.root, review, entries, obs, CIK, study.instant('2020-01-03T00:00:00Z'))['status'], 'UNKNOWN')

    def test_clock_conflict_raw_Z_preserved_and_review_required(self):
        entries, obs, clocks, review = self.identities(conflict=True)
        self.assertEqual(clocks[0]['raw_submissions'], '2020-01-02T12:00:00Z')
        self.assertEqual(clocks[0]['header_utc'], '2020-01-02T17:00:00+00:00')
        with self.assertRaises(study.GuardFailure): self.plan()
        self.assertEqual(study.gated_lookup(self.root, review, entries, obs, CIK, study.instant('2020-01-03T00:00:00Z'))['status'], 'UNKNOWN')
        review['clock_reviews'] = [dict(cik=CIK, accession=ACC, header_sha256=obs[0]['sha256'], basis='verified_header_research_only', reviewed_by='fixture')]
        result = study.gated_lookup(self.root, review, entries, obs, CIK, study.instant('2020-01-03T00:00:00Z'))
        self.assertEqual(result['status'], 'CLASSIFIED')
        # A separate earlier accepted identity exposes the availability disagreement.
        with patch.object(study, 'identity_gate', return_value='ACCEPTED'):
            result = study.gated_lookup(self.root, review, entries, obs, CIK, study.instant('2020-01-02T13:00:00Z'))
        self.assertEqual(result['status'], 'UNKNOWN'); self.assertEqual(result['timing_conflicts'], [ACC])

    def test_invalid_proof_and_unknown_interval_never_accept_security(self):
        entries, obs, _, review = self.identities()
        binding = dict(review['issuer_reviews'][0], security_id=7, effective_from=None, class_title='Class A', interval_basis='Explicit reviewed action')
        review['relationships'] = [binding]
        self.assertEqual(study.identity_gate(self.root, review, entries, obs, CIK, study.instant('2020-01-03T00:00:00Z'), 7), 'UNKNOWN')
        review['issuer_reviews'][0]['evidence'][0]['quote'] = 'Not present'
        with self.assertRaises(study.GuardFailure): study.identity_gate(self.root, review, entries, obs, CIK, study.instant('2020-01-03T00:00:00Z'))

    def test_class_binding_source_effective_and_knowledge_gates(self):
        raw = b'<html>Example Inc Class A common stock. Effective January 2, 2020.</html>'
        self.package(reused=[(ACC, header())], bodies=[(ACC, raw)])
        entries = study.all_evidence(self.root); inputs = study.load_inputs(self.root)
        catalogs, _, _ = study.inventories(self.root, inputs, entries)
        obs, _, _, _ = study.header_observations(self.root, inputs, entries, catalogs)
        doc = next(e for e in entries if e['item']['kind'] == 'body')
        proof = dict(url=doc['url'], sha256=doc['sha256'], quote='Example Inc Class A common stock. Effective January 2, 2020.', location='Action paragraph')
        binding = dict(cik=CIK, security_id=7, class_title='Class A common stock', status='ACCEPTED', reviewed_by='fixture',
                       knowledge_at='2020-01-01T00:00:00Z', effective_from='2020-01-02T00:00:00Z',
                       effective_to='2020-01-05T00:00:00Z', interval_basis='Explicit reviewed action paragraph', evidence=[proof])
        issuer = {k: binding[k] for k in ('cik', 'status', 'reviewed_by', 'knowledge_at', 'evidence')}
        review = dict(issuer_reviews=[issuer], relationships=[binding], clock_reviews=[])
        gate = lambda stamp: study.identity_gate(self.root, review, entries, obs, CIK, study.instant(stamp), 7)
        self.assertEqual(gate('2020-01-02T16:00:00Z'), 'UNKNOWN')
        self.assertEqual(gate('2020-01-02T17:00:00Z'), 'ACCEPTED')
        self.assertEqual(gate('2020-01-05T00:00:00Z'), 'UNKNOWN')
        binding['class_title'] = 'Class C'
        with self.assertRaises(study.GuardFailure): gate('2020-01-03T00:00:00Z')

    def test_cross_cik_overlapping_bindings_are_ambiguous_not_merged(self):
        cik2, acc2 = '0000000002', '0000000002-20-000001'
        raw = b'<html>Example Inc Class A common stock. Effective January 2, 2020.</html>'
        self.package(cases=[CASE, dict(CASE, cik=cik2)], reused=[(ACC, header()), (acc2, header(acc2, cik=cik2), cik2)],
                     bodies=[(ACC, raw), (acc2, raw, cik2)])
        entries = study.all_evidence(self.root); inputs = study.load_inputs(self.root)
        catalogs, _, _ = study.inventories(self.root, inputs, entries)
        obs, _, _, _ = study.header_observations(self.root, inputs, entries, catalogs)
        issuers, relationships = [], []
        for cik in (CIK, cik2):
            e = next(e for e in entries if e['item']['kind'] == 'body' and e['item']['cik'] == cik)
            proof = dict(url=e['url'], sha256=e['sha256'], location='Action paragraph', quote='Example Inc Class A common stock. Effective January 2, 2020.')
            issuer = dict(cik=cik, status='ACCEPTED', reviewed_by='fixture', knowledge_at='2020-01-01T00:00:00Z', evidence=[proof])
            issuers.append(issuer)
            relationships.append(dict(issuer, security_id=7, effective_from='2020-01-02T00:00:00Z', effective_to=None,
                                      class_title='Class A common stock', interval_basis='Explicit action paragraph'))
        review = dict(issuer_reviews=issuers, relationships=relationships, clock_reviews=[])
        self.assertEqual(study.identity_gate(self.root, review, entries, obs, CIK, study.instant('2020-01-03T00:00:00Z'), 7), 'AMBIGUOUS')

    def test_same_url_conflicting_vintages_are_not_silently_selected(self):
        item = dict(kind='catalogue', cik=CIK)
        entries = [dict(url=study.url(item), sha256='a'), dict(url=study.url(item), sha256='b')]
        with self.assertRaises(study.GuardFailure): study.by_url(entries, study.url(item))

    def test_8k_cannot_preempt_missing_periodic_baseline(self):
        acc2 = '0000000001-20-000002'
        self.package(rows=[row(), row(acc2, '8-K')])
        review = self.review(eight_k_intervals=[dict(cik=CIK, start='2020-01-01', end_exclusive='2020-01-03', reason='Identity action', reviewed=True)])
        p, _ = self.plan(review)
        self.assertEqual([r['envelope'] for r in study.read(p)['requests']], ['periodic'])

    def test_fetch_cli_requires_explicit_plan_and_hash(self):
        with patch.object(study, 'fetch') as fetch:
            with self.assertRaises(study.GuardFailure): study.main(['--fetch', '--package-dir', str(self.root)])
        fetch.assert_not_called()

    def test_selected_8k_intervals_and_incomplete_report(self):
        acc2, acc3 = '0000000001-20-000002', '0000000001-20-000003'
        outside = row(acc3, '8-K'); outside['filingDate'] = '2020-02-01'
        self.package(rows=[row(), row(acc2, '8-K/A'), outside], reused=[(ACC, header())])
        review = self.review(eight_k_intervals=[dict(cik=CIK, start='2020-01-01', end_exclusive='2020-01-03', reason='Identity action', reviewed=True)])
        p, _ = self.plan(review)
        requests = study.read(p)['requests']
        self.assertEqual([r['accession'] for r in requests], [acc2])
        report = study.analyze(self.root, *review)
        coverage = study.read(Path(report['path'])/'coverage.json')[0]
        self.assertEqual(coverage['eight_k_unexamined_outside_intervals'], [acc3])
        self.assertEqual(coverage['eight_k_selected_unretrieved'], [acc2])
        self.assertFalse(coverage['eight_k_complete'])
        self.assertEqual(len(coverage['probes']), 24)
        self.assertTrue(all(p['synthetic'] and not p['trading_session'] for p in coverage['probes']))
        self.assertTrue(all(p['periodic']['status'] == 'UNKNOWN' for p in coverage['probes']))
        before = (Path(report['path'])/'results.json').read_bytes()
        again = study.analyze(self.root, *review)
        self.assertNotEqual(again['path'], report['path'])
        self.assertEqual(before, (Path(report['path'])/'results.json').read_bytes())

    def test_whole_8k_interval_must_fit_budget(self):
        rows = [row()] + [row(f'0000000001-20-{n:06d}', '8-K') for n in range(2, 33)]
        self.package(rows=rows, reused=[(ACC, header())])
        review = self.review(eight_k_intervals=[dict(cik=CIK, start='2020-01-01', end_exclusive='2020-01-03', reason='Identity action', reviewed=True)])
        with self.assertRaises(study.GuardFailure): self.plan(review)

    def test_supplemental_forms_not_in_comparison(self):
        acc2 = '0000000001-20-000002'
        self.package(rows=[row(), row(acc2, 'DEF 14A')], reused=[(ACC, header()), (acc2, header(acc2, 'DEF 14A', sic='5678'))])
        report = study.analyze(self.root)
        results = study.read(Path(report['path'])/'results.json')
        self.assertEqual(len(results['supplemental_other_forms']), 1)
        self.assertEqual(results['windows'][0]['transition_bounds']['periodic_plus_8k'], [])

    def test_exhibit_escape_and_protected_package_refused(self):
        with self.assertRaises(ValueError): study.url(dict(kind='exhibit', cik=CIK, accession=ACC, document='../bad.htm'))
        for root in (study.STAGE3, Path('data/stage4'), Path('logs/research/ttwo_acceptance_correction_2026-09-26_v2/subdir')):
            with self.assertRaises(study.GuardFailure): study.safe_root(root)


if __name__ == '__main__':
    unittest.main()
