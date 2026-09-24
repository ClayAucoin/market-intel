"""Offline repair-manifest fail-closed and provenance tests."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

with patch('dotenv.load_dotenv'):
    from src.backtesting import acceptance_repair_manifest as repair
    from src.backtesting.audit_acceptance_timezone import legacy_parse_acceptance_datetime
from src.sec.acceptance_time import parse_submissions_acceptance


class ManifestTests(unittest.TestCase):
    def test_categories_and_no_guessed_instant(self):
        raw = '2026-08-07T20:03:52.000Z'
        new = parse_submissions_acceptance(raw)
        old = legacy_parse_acceptance_datetime(raw)
        sources = [dict(raw=raw)]
        self.assertEqual(repair.classify(old, sources), ('safely_correctable', new))
        self.assertEqual(repair.classify(new, sources), ('already_correct', new))
        self.assertEqual(repair.classify(old, []), ('unresolved_source', None))
        self.assertEqual(repair.classify(old, sources+[dict(raw='2026-08-07T21:03:52Z')]), ('unresolved_source', None))
        doubled = legacy_parse_acceptance_datetime(old.astimezone(repair.timezone.utc).isoformat())
        self.assertEqual(repair.classify(doubled, sources), ('exceptional_offset', new))

    def test_matching_four_hour_delta_alone_is_not_enough(self):
        # Near spring-forward, the legacy parser applies the offset to the wrong
        # clock. Require exact bug reproduction, not a blanket delta match.
        from datetime import timedelta
        raw = '2026-03-08T01:30:00Z'
        source = parse_submissions_acceptance(raw)
        self.assertEqual(repair.classify(source+timedelta(hours=4), [dict(raw=raw)])[0], 'exceptional_offset')
        self.assertEqual(repair.classify(source+timedelta(hours=5), [dict(raw=raw)])[0], 'safely_correctable')

    def test_cache_identity_and_content_are_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            source = cache/'CIK0000000001.json'
            raw = '2026-08-07T20:03:52Z'
            payload = dict(cik=1, filings=dict(recent=dict(accessionNumber=['fixture'],
                acceptanceDateTime=[raw], filingDate=['2026-08-07'])))
            source.write_text(json.dumps(payload))
            evidence = dict(source=str(source), raw=raw, accepted=raw, filing_date='2026-08-07')
            row = dict(cik='1', accession_number='fixture', filing_date='2026-08-07', evidence=[evidence])
            with patch.object(repair, 'CACHE', cache):
                hashes = repair.validate_local_sources([row])
                self.assertEqual(hashes[str(source)]['sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
                row['cik'] = '2'
                with self.assertRaises(ValueError): repair.validate_local_sources([row])
                row['cik'] = '1'
                evidence['raw'] = '2026-08-07T21:03:52Z'
                with self.assertRaises(ValueError): repair.validate_local_sources([row])

    def test_saved_manifest_reconciles_and_only_safe_rows_are_proposed(self):
        data = repair.OUTPUT.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), repair.OUTPUT.with_suffix('.gz.sha256').read_text().split()[0])
        manifest = json.loads(gzip.decompress(data))
        self.assertEqual(manifest['counts'], repair.EXPECTED)
        self.assertEqual(len(manifest['rows']), 31097)
        for row in manifest['rows']:
            self.assertEqual(row['proposed_timestamp'] is not None, row['category']=='safely_correctable')
            if row['source_evidence']:
                for source in row['source_evidence']:
                    self.assertEqual(source['sha256'], manifest['source_files'][source['source']]['sha256'])
                    self.assertEqual(parse_submissions_acceptance(source['raw']), repair.instant(row['source_normalized_utc']))

    def test_population_drift_stops_manifest(self):
        with self.assertRaisesRegex(ValueError, 'population differs'):
            repair.build(dict(filings=[], summary=dict(filings=0)), {})

    def test_preflight_detects_timestamp_or_cutover_drift_read_only(self):
        old = '2026-08-08T00:03:52+00:00'
        manifest = dict(rows=[dict(filing_id=1, company_id=2, cik='0000000002',
            accession='fixture', stored_timestamp=old, filing_date='2026-08-07')],
            cutover_preconditions=[dict(id=1, prospective_cutover_at=old)])
        for timestamp, cutover, expected in ((old, old, True),
                ('2026-08-07T20:03:52+00:00', old, False), (old, None, False)):
            with self.subTest(timestamp=timestamp, cutover=cutover):
                conn = MagicMock()
                conn.__enter__.return_value = conn
                cursor = conn.cursor.return_value.__enter__.return_value
                cursor.fetchone.side_effect = [dict(read_only='on'), dict(total=1, historical_membership=1)]
                cursor.fetchall.side_effect = [[dict(id=1, company_id=2, cik='0000000002',
                    accession_number='fixture', acceptance_datetime=repair.instant(timestamp),
                    filing_date='2026-08-07')], [dict(id=1, prospective_cutover_at=repair.instant(cutover))]]
                with patch('src.database.get_connection', return_value=conn):
                    result = repair.verify_database(manifest)
                self.assertEqual(result['passed'], expected)
                self.assertIs(conn.read_only, True)
                for call in cursor.execute.call_args_list:
                    self.assertTrue(call.args[0].startswith(('SELECT ', 'SET LOCAL ')))


if __name__ == '__main__': unittest.main()
