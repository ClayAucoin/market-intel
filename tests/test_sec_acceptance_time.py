"""Offline timestamp semantics and both filing-writer regression tests."""
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.sec.acceptance_time import parse_submissions_acceptance as submissions, parse_header_acceptance as header
with patch('dotenv.load_dotenv'):
    from src.sec import import_universe_filings as universe, filing_repository as repository
    from src.sec.json_cache import validate_columns


class AcceptanceTimeTests(unittest.TestCase):
    def test_gen_explicit_instants(self):
        expected = datetime(2026, 8, 7, 20, 3, 52, tzinfo=timezone.utc)
        for raw in ('2026-08-07T20:03:52.000Z', '2026-08-07T20:03:52+00:00',
                    '2026-08-07T16:03:52-04:00', '2026-08-07T21:03:52+01:00',
                    '2026-08-08T01:33:52+0530', '2026-08-07T21:03:52+01'):
            with self.subTest(raw=raw):
                self.assertEqual(submissions(raw), expected)
                self.assertIs(submissions(raw).tzinfo, timezone.utc)
        self.assertEqual(header('20260807160352'), expected)

    def test_standard_time_and_fraction(self):
        self.assertEqual(header('20200207150352'), submissions('2020-02-07T20:03:52Z'))
        self.assertEqual(submissions('2020-02-07T15:03:52.123456-05:00'),
                         datetime(2020, 2, 7, 20, 3, 52, 123456, timezone.utc))

    def test_naive_and_malformed_rejected(self):
        for raw in ('2026-08-07T16:03:52', '2026-08-07T16:03:52BAD',
                    '2026-08-07T16:03:52Zjunk', '2026-08-07T16:03:52+01:60',
                    '2026-08-07T16:03:52+24:00', '2026-08-07T16:03:52.1234567Z',
                    '20260807160352', False, 123):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                submissions(raw)
        self.assertIsNone(submissions(None))
        self.assertIsNone(submissions(''))

    def test_explicit_dst_fold_is_unambiguous(self):
        self.assertEqual(submissions('2026-11-01T01:30:00-04:00'), submissions('2026-11-01T05:30:00Z'))
        self.assertEqual(submissions('2026-11-01T01:30:00-05:00'), submissions('2026-11-01T06:30:00Z'))
        # An explicit offset identifies an instant even if that wall clock does
        # not exist in America/New_York; ISO offsets are not a regional timezone.
        self.assertEqual(submissions('2026-03-08T02:30:00-05:00'), submissions('2026-03-08T07:30:00Z'))

    def test_header_dst_boundaries_and_rejection(self):
        for raw, utc in [('20260308015959', '2026-03-08T06:59:59Z'),
                         ('20260308030000', '2026-03-08T07:00:00Z'),
                         ('20261101005959', '2026-11-01T04:59:59Z'),
                         ('20261101020000', '2026-11-01T07:00:00Z')]:
            self.assertEqual(header(raw), submissions(utc))
        for raw in ('20260308023000', '20261101013000', '2026-08-07T16:03:52Z', None):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                header(raw)

    def test_validator_requires_explicit_timezone(self):
        record = dict(accessionNumber=['fixture'], filingDate=['2026-08-07'],
                      acceptanceDateTime=['2026-08-07T20:03:52Z'])
        validate_columns(record)
        record['acceptanceDateTime'] = ['2026-08-07T20:03:52']
        with self.assertRaises(ValueError):
            validate_columns(record)
        self.assertFalse(universe.valid_filing_metadata(dict(accessionNumber='fixture',
            filingDate='2026-08-07', acceptanceDateTime='2026-08-07T20:03:52')))

    def test_both_writers_send_utc_gen_instant(self):
        raw = '2026-08-07T20:03:52.000Z'
        conn = MagicMock()
        cursor = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        with patch.object(universe, 'get_connection', return_value=conn):
            universe.save_filing(1, '0000849399', dict(accessionNumber='0000849399-26-000031',
                filingDate='2026-08-07', acceptanceDateTime=raw, form='10-Q'))
        self.assertEqual(cursor.execute.call_args.args[1][5], submissions(raw))
        self.assertIs(cursor.execute.call_args.args[1][5].tzinfo, timezone.utc)
        conn.reset_mock()
        filing = dict(accession_number='0000849399-26-000031', form='10-Q',
            filing_date='2026-08-07', report_date=None, acceptance_datetime=raw,
            primary_document=None, primary_doc_description=None)
        with patch.object(repository, 'get_connection', return_value=conn), patch('builtins.print'):
            repository.save_filings(1, [filing])
        self.assertEqual(cursor.executemany.call_args.args[1][0][5], submissions(raw))
        self.assertIs(cursor.executemany.call_args.args[1][0][5].tzinfo, timezone.utc)

    def test_both_writers_reject_naive_before_connection(self):
        with patch.object(universe, 'get_connection') as connect:
            with self.assertRaises(ValueError):
                universe.save_filing(1, '1', dict(filingDate='2026-08-07', acceptanceDateTime='2026-08-07T20:03:52'))
            connect.assert_not_called()
        with patch.object(repository, 'get_connection') as connect:
            with self.assertRaises(ValueError):
                repository.save_filings(1, [dict(accession_number='fixture', form='10-Q',
                    filing_date='2026-08-07', report_date=None, acceptance_datetime='2026-08-07T20:03:52')])
            connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
