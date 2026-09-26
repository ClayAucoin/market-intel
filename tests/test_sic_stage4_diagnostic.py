"""Only temporary packages and mocked transport; real external I/O is blocked."""
import fcntl
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from src.backtesting import sic_stage4 as stage
from src.backtesting import sic_stage4_diagnostic as diagnostic


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'package'
        self.root.mkdir()
        for target in ('socket.socket.connect', 'socket.create_connection',
                       'requests.sessions.Session.request', 'psycopg.connect', 'src.database.get_connection'):
            blocker = patch(target, side_effect=AssertionError('External I/O forbidden'))
            blocker.start()
            self.addCleanup(blocker.stop)
        cases = [dict(cik=diagnostic.CIK, expected_names=['DELL INC'], start='2012-01-01',
                      end_exclusive='2014-01-01', label='DELL')]
        cases += [dict(cik=c, expected_names=['Expected'], start='2012-01-01',
                       end_exclusive='2014-01-01', label='blocked') for c in diagnostic.BLOCKED]
        entries = []
        catalog_rows = []
        for n in range(27):
            acc = diagnostic.ACCESSION if n == 0 else f'0000826083-12-{n+10:06d}'
            row = dict(accessionNumber=acc, filingDate='2012-03-13', acceptanceDateTime='2012-03-13T20:21:54Z',
                       form='10-K', primaryDocument='dell.htm', reportDate='2012-02-03')
            catalog_rows.append(row)
            raw = f'''<pre>ACCESSION NUMBER: {acc}
ACCEPTANCE-DATETIME: 20120313202154
CONFORMED SUBMISSION TYPE: 10-K
FILED AS OF DATE: 20120313
FILER:
COMPANY CONFORMED NAME: DELL INC
CENTRAL INDEX KEY: 0000826083
STANDARD INDUSTRIAL CLASSIFICATION: EXAMPLE [1234]
</pre>'''.encode()
            entries.append(stage.store_raw(self.root, dict(kind='header', cik=diagnostic.CIK, accession=acc), raw,
                                           dict(basis='fixture')))
        checks = {diagnostic.CIK:dict(status='SUPPORTED_CANDIDATE', supporting_sources=[], contradictions=[],
                                     issuer_identity_accepted=False, relationship_verified=False)}
        checks.update({c:dict(status='BLOCKED_CONTRADICTION', supporting_sources=[],
                             contradictions=[dict(reason='fixture disagreement')],
                             issuer_identity_accepted=False, relationship_verified=False) for c in diagnostic.BLOCKED})
        stage.frozen(self.root/'reuse_manifest.json', entries)
        stage.frozen(self.root/'candidate_review.json', checks)
        stage.frozen(self.root/'relationships.json', {})
        inputs = dict(roster=cases, catalogs={diagnostic.CIK:catalog_rows}, cap=stage.CAP,
                      envelopes=stage.ENVELOPES, code_sha256=stage.code_pins(),
                      frozen_files={n:stage.sha((self.root/n).read_bytes()) for n in
                                    ('reuse_manifest.json', 'candidate_review.json', 'relationships.json')})
        stage.frozen(self.root/'inputs.json', inputs)
        stage.frozen(self.root/'inputs.sha256', stage.sha((self.root/'inputs.json').read_bytes()))
        stage.frozen(self.root/'requests.json', [])
        for n in range(1,7):
            item = dict(kind='header', cik=diagnostic.CIK, accession=diagnostic.ACCESSION)
            reservation = dict(attempt=n, item=item, url=stage.url(item)+(f'?fixture={n}' if n<6 else ''), plan='fixture.json',
                               charged_envelope='periodic', outcome='IN_FLIGHT', reserved_at='2026-01-01T00:00:00Z')
            stage.frozen(self.root/'attempts'/f'{n:06d}.json', reservation)
            rows = stage.read(self.root/'requests.json')
            stage.atomic_json(self.root/'requests.json', rows+[reservation])
            stage.finish(self.root, reservation, dict(outcome='SUCCESS' if n<6 else 'HTTP_FAILURE', status=200 if n<6 else 404))
        ledger_pin = stage.digest(stage.ledger(self.root))
        override = patch.object(diagnostic, 'EXPECTED_LEDGER', ledger_pin)
        override.start()
        self.addCleanup(override.stop)
        catalogs, _, _ = stage.inventories(self.root, inputs, entries)
        _, _, clocks, _ = stage.header_observations(self.root, inputs, entries, catalogs)
        self.assertEqual(len(clocks), 27)
        self.review = self.root/'review_03.json'
        stage.frozen(self.review, dict(inputs_sha256=stage.sha((self.root/'inputs.json').read_bytes()), reviewed_by='fixture',
                     issuer_reviews=[], relationships=[], clock_reviews=[], identity_requests=[], eight_k_intervals=[],
                     acknowledged_contradictions=diagnostic.BLOCKED,
                     acknowledged_clock_conflicts=sorted(c['cik']+'/'+c['accession']+'/'+c['header_sha256'] for c in clocks)))
        self.originals = {p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def prepare(self):
        result = diagnostic.prepare(self.root, self.review, stage.sha(self.review.read_bytes()))
        return Path(result['path']), result['sha256']

    def fetch(self, status=200, chunks=None, error=None):
        manifest, pin = self.prepare()
        response = MagicMock()
        response.status_code = status
        response.iter_content.return_value = iter(chunks if chunks is not None else [b'<a href="file.htm">filing</a>'])
        if error:
            response.iter_content.side_effect = error
        with patch('requests.get', return_value=response) as get, patch('src.sec.sec_http._pace') as pace:
            response.__enter__.return_value = response
            result = diagnostic.fetch(self.root, manifest, pin)
        get.assert_called_once()
        pace.assert_called_once()
        self.assertEqual(get.call_args.kwargs['timeout'], (10,30))
        self.assertFalse(get.call_args.kwargs['allow_redirects'])
        return result, manifest, pin

    def test_success_and_reader_compatibility(self):
        before = stage.all_evidence(self.root)
        result, manifest, pin = self.fetch()
        self.assertEqual(result['outcome'], 'SUCCESS')
        rows = stage.ledger(self.root)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[-1]['charged_envelope'], 'contingency')
        self.assertEqual(stage.all_evidence(self.root), before)
        self.assertEqual(len(stage.header_observations(self.root, stage.load_inputs(self.root), before,
                         stage.inventories(self.root, stage.load_inputs(self.root), before)[0])[2]), 27)
        for p, raw in self.originals.items():
            if p.name != 'requests.json': self.assertEqual(p.read_bytes(), raw)
        evidence = rows[-1]['diagnostic_evidence']
        self.assertEqual(stage.sha((self.root/evidence['body']).read_bytes()), evidence['raw_sha256'])
        with self.assertRaises(stage.GuardFailure): diagnostic.fetch(self.root, manifest, pin)
        self.assertEqual(len(stage.ledger(self.root)),7)

    def test_non200_body_preserved(self):
        result, _, _ = self.fetch(404, [b'not found'])
        self.assertEqual(result['outcome'], 'HTTP_FAILURE')
        self.assertEqual((self.root/'diagnostics/000007/body.bin').read_bytes(), b'not found')
        self.assertEqual(stage.ledger(self.root)[-1]['status'],404)

    def test_redirect_body_preserved_without_following(self):
        result, _, _ = self.fetch(302,[b'redirect'])
        self.assertEqual(result['http_status'],302)

    def test_bounds(self):
        result, _, _ = self.fetch(200,[b'x'*(diagnostic.LIMIT+1)])
        self.assertEqual(result['outcome'],'SIZE_FAILURE')
        self.assertEqual((self.root/'diagnostics/000007/body.bin').stat().st_size,diagnostic.LIMIT)
        self.assertTrue(stage.ledger(self.root)[-1]['diagnostic_evidence']['truncated'])

    def test_non200_bound_and_persistent_original_stop(self):
        result, _, _ = self.fetch(404,[b'x'*(diagnostic.LIMIT+1)])
        self.assertEqual(result['outcome'],'SIZE_FAILURE')
        self.assertEqual(result['http_status'],404)
        rows=stage.ledger(self.root)
        with self.assertRaises(stage.GuardFailure):
            stage.stop_review(rows,dict(continuation=dict(ledger_sha256=stage.digest(rows),acknowledged_attempts=[6,7])))

    def test_exact_bound_is_complete(self):
        result, _, _ = self.fetch(200,[b'x'*diagnostic.LIMIT])
        self.assertEqual(result['outcome'],'SUCCESS')

    def test_incomplete_read_retains_prefix(self):
        def chunks():
            yield b'prefix'
            raise OSError('fixture failure')
        result, _, _ = self.fetch(500,chunks())
        self.assertEqual(result['outcome'],'NETWORK_FAILURE')
        self.assertEqual((self.root/'diagnostics/000007/body.bin').read_bytes(),b'prefix')
        self.assertTrue(stage.ledger(self.root)[-1]['diagnostic_evidence']['incomplete_read'])
        self.assertEqual(result['http_status'],500)

    def test_transport_failure_without_status(self):
        manifest,pin=self.prepare()
        with patch('requests.get',side_effect=OSError('secret must not persist')), patch('src.sec.sec_http._pace'):
            result=diagnostic.fetch(self.root,manifest,pin)
        self.assertIsNone(result['http_status'])
        self.assertEqual(result['outcome'],'NETWORK_FAILURE')
        self.assertNotIn('secret', (self.root/'diagnostics/000007/response.json').read_text())
        rows = stage.ledger(self.root)
        stage.stop_review(rows, dict(continuation=dict(ledger_sha256=stage.digest(rows), acknowledged_attempts=[6,7])))
        self.assertEqual(len(stage.all_evidence(self.root)),27)

    def test_reservation_is_durable_before_transport(self):
        manifest,pin=self.prepare()
        def interrupted():
            self.assertEqual(stage.ledger(self.root)[-1]['outcome'],'IN_FLIGHT')
            self.assertTrue((self.root/'attempts/000007.json').exists())
            raise KeyboardInterrupt()
        with patch.object(diagnostic,'transport',side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt): diagnostic.fetch(self.root,manifest,pin)
        with self.assertRaises(stage.GuardFailure): diagnostic.fetch(self.root,manifest,pin)
        self.assertEqual(len(stage.ledger(self.root)),7)

    def test_locking(self):
        with (self.root/'.lock').open('a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(stage.GuardFailure): self.prepare()

    def test_hash_rejection(self):
        manifest,pin=self.prepare()
        with self.assertRaises(stage.GuardFailure): diagnostic.fetch(self.root,manifest,'0'*64)
        manifest.write_text(manifest.read_text()+' ')
        with self.assertRaises(stage.GuardFailure): diagnostic.fetch(self.root,manifest,pin)
        self.assertEqual(len(stage.ledger(self.root)),6)

    def test_dependency_change_rejected(self):
        manifest,pin=self.prepare()
        (self.root/'attempts/000001.json').write_text('{}')
        with self.assertRaises((stage.GuardFailure,KeyError)): diagnostic.fetch(self.root,manifest,pin)

    def test_interruption_before_snapshot_blocks_reexecution(self):
        manifest,pin=self.prepare()
        with patch.object(stage,'atomic_json',side_effect=OSError('fixture disk interruption')):
            with self.assertRaises(OSError): diagnostic.fetch(self.root,manifest,pin)
        self.assertTrue((self.root/'attempts/000007.json').exists())
        with self.assertRaises(stage.GuardFailure): diagnostic.fetch(self.root,manifest,pin)
        self.assertEqual(len(list((self.root/'attempts').glob('*.json'))),7)

    def test_receipt_alone_blocks_reexecution(self):
        manifest,pin=self.prepare()
        original=stage.frozen
        def fail_reservation(path,value):
            if Path(path).parent.name=='attempts': raise OSError('fixture disk interruption')
            return original(path,value)
        with patch.object(stage,'frozen',side_effect=fail_reservation):
            with self.assertRaises(OSError): diagnostic.fetch(self.root,manifest,pin)
        with self.assertRaises(stage.GuardFailure): diagnostic.fetch(self.root,manifest,pin)
        self.assertEqual(len(stage.ledger(self.root)),6)

    def test_catalogue_target_required(self):
        inputs=stage.read(self.root/'inputs.json')
        inputs['catalogs'][diagnostic.CIK]=[]
        (self.root/'inputs.json').write_bytes(stage.encoded(inputs))
        (self.root/'inputs.sha256').write_bytes(stage.encoded(stage.sha((self.root/'inputs.json').read_bytes())))
        review=stage.read(self.review)
        review['inputs_sha256']=stage.sha((self.root/'inputs.json').read_bytes())
        self.review.write_bytes(stage.encoded(review))
        # Preserve the fixture acknowledgements; absent target must still reject.
        with self.assertRaises(stage.GuardFailure): self.prepare()

    def test_extension_code_pin_rejected(self):
        manifest,pin=self.prepare()
        with patch.object(diagnostic,'implementation_pins',return_value={}):
            with self.assertRaises(stage.GuardFailure): diagnostic.fetch(self.root,manifest,pin)

    def test_budgets(self):
        rows=stage.ledger(self.root)
        with self.assertRaises(stage.GuardFailure): diagnostic.budget(rows*40)
        contingency=[dict(rows[0],charged_envelope='contingency') for _ in range(30)]
        with self.assertRaises(stage.GuardFailure): diagnostic.budget(contingency)
        with self.assertRaises(stage.GuardFailure): diagnostic.budget([dict(rows[0],url=diagnostic.request()['url'])])

    def test_default_no_action_and_prepare_once(self):
        with patch('sys.stdout',new=io.StringIO()), patch.object(diagnostic,'prepare') as prepare, patch.object(diagnostic,'fetch') as fetch:
            diagnostic.main([])
        prepare.assert_not_called();fetch.assert_not_called()
        self.prepare()
        with self.assertRaises(stage.GuardFailure): self.prepare()

    def test_bad_review_or_catalogue_rejected(self):
        data=stage.read(self.review);data['issuer_reviews']=[dict(cik=diagnostic.CIK,status='UNKNOWN')]
        self.review.write_bytes(stage.encoded(data))
        with self.assertRaises(stage.GuardFailure): self.prepare()


if __name__ == '__main__':
    unittest.main()
