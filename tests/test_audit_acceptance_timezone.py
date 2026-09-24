"""Pure offline tests documenting the bug, not changing production parsing."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    from src.backtesting.audit_acceptance_timezone import normalize_explicit, timestamp_format, candidate
    from src.backtesting.audit_acceptance_timezone import legacy_parse_acceptance_datetime as parse_acceptance_datetime
    from src.backtesting.audit_sector_readiness import availability


class AcceptanceAuditTests(unittest.TestCase):
    def test_explicit_utc_summer_shift(self):
        raw='2026-08-07T20:03:52.000Z'
        self.assertEqual((parse_acceptance_datetime(raw)-normalize_explicit(raw)).total_seconds(),4*3600)

    def test_explicit_utc_winter_shift(self):
        raw='2020-02-07T20:03:52.000Z'
        self.assertEqual((parse_acceptance_datetime(raw)-normalize_explicit(raw)).total_seconds(),5*3600)

    def test_eastern_explicit_offset(self):
        for raw in ('2026-08-07T16:03:52-04:00','2020-02-07T15:03:52-05:00'):
            self.assertEqual(parse_acceptance_datetime(raw),normalize_explicit(raw))

    def test_other_explicit_offset_preserved_by_reference(self):
        self.assertEqual(normalize_explicit('2026-08-07T21:03:52+01:00'),normalize_explicit('2026-08-07T20:03:52Z'))

    def test_naive_not_assumed_utc(self):
        self.assertIsNone(normalize_explicit('2026-08-07T16:03:52'))
        self.assertEqual(parse_acceptance_datetime('2026-08-07T16:03:52').utcoffset().total_seconds(),-4*3600)

    def test_fractional_seconds_currently_truncated(self):
        raw='2026-08-07T20:03:52.123Z'
        self.assertEqual(normalize_explicit(raw).microsecond,123000)
        self.assertEqual(parse_acceptance_datetime(raw).microsecond,0)

    def test_invalid_suffix_currently_ignored(self):
        raw='2026-08-07T20:03:52BAD'
        with self.assertRaises(ValueError): normalize_explicit(raw)
        self.assertIsNotNone(parse_acceptance_datetime(raw))

    def test_dst_transition_reference_respects_instant(self):
        for raw in ('2026-03-08T06:30:00Z','2026-03-08T07:30:00Z',
                    '2026-11-01T05:30:00Z','2026-11-01T06:30:00Z'):
            self.assertEqual(normalize_explicit(raw).tzinfo,timezone.utc)
        self.assertNotEqual(normalize_explicit('2026-11-01T01:30:00-04:00'),normalize_explicit('2026-11-01T01:30:00-05:00'))

    def test_candidate_entry_changes_at_open(self):
        raw='2026-08-07T12:00:00Z'
        old=candidate(parse_acceptance_datetime(raw),None)
        new=candidate(normalize_explicit(raw),None)
        self.assertEqual((old-new).days,1)

    def test_formats(self):
        self.assertEqual(timestamp_format(None),'missing')
        self.assertEqual(timestamp_format('2020-01-01T01:00:00Z'),'explicit_Z')
        self.assertEqual(timestamp_format('2020-01-01T01:00:00-05:00'),'explicit_offset')
        self.assertEqual(timestamp_format('2020-01-01T01:00:00'),'naive')

    def test_fixed_decision_can_be_unchanged_despite_shift(self):
        raw='2026-08-07T12:00:00Z'
        cutoff=datetime(2026,8,10,13,30,tzinfo=timezone.utc)
        fact=dict(is_derived=False,accession_number='fixture',company_id=1,filing_company_id=1,
                  filed_date=cutoff.date(),acceptance_datetime=parse_acceptance_datetime(raw))
        old=availability([fact],cutoff)
        fact['acceptance_datetime']=normalize_explicit(raw)
        self.assertEqual(old,availability([fact],cutoff))


if __name__=='__main__': unittest.main()
