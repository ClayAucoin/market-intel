"""Offline checks for stable event keys and pre-rebuild drift preservation."""
from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    from src.backtesting.timestamp_rebuild_preflight import event_key, filing_drift, signal_stats


class RebuildPreflightTests(unittest.TestCase):
    def test_key_ignores_recreated_id_entry_date_and_display_ticker(self):
        a=dict(id=1,security_id=7,period_end=date(2020,3,31),entry_date=date(2020,5,1),display_ticker='OLD')
        b=dict(a,id=99,entry_date=date(2020,4,30),display_ticker='NEW')
        self.assertEqual(event_key(a),event_key(b))
        self.assertNotEqual(event_key(a),event_key(dict(b,security_id=8)))

    def fixture(self):
        old=dict(filing_id=1,company_id=2,cik='0000000002',accession='fixture',filing_date='2020-01-01',
            category='safely_correctable',stored_timestamp='2020-01-01T20:00:00Z',proposed_timestamp='2020-01-01T15:00:00Z')
        current=dict(id=1,company_id=2,cik='0000000002',accession_number='fixture',filing_date=date(2020,1,1),
            acceptance_datetime='2020-01-01T15:00:00Z')
        return old,current

    def test_detect_new_missing_and_modified_without_inventing_corrections(self):
        old,current=self.fixture()
        result=filing_drift([current,dict(current,id=3)],dict(rows=[old]))
        self.assertEqual(len(result['new']),1)
        self.assertEqual(result['changed'],[])
        self.assertEqual(result['unchanged_manifest_categories'],{'safely_correctable':1})
        self.assertEqual(filing_drift([],dict(rows=[old]))['missing'],[1])
        result=filing_drift([dict(current,acceptance_datetime=old['stored_timestamp'])],dict(rows=[old]))
        self.assertTrue(result['changed'][0]['fields']['acceptance_datetime'])

    def test_excluded_timestamp_stays_old(self):
        old,current=self.fixture()
        old.update(category='exceptional_offset',proposed_timestamp=None)
        result=filing_drift([dict(current,acceptance_datetime=old['stored_timestamp'])],dict(rows=[old]))
        self.assertEqual(result['changed'],[])

    def test_stats_use_membership_and_completed_denominator(self):
        base=dict(membership_qualified=True,exact_signal=True,split='train',excess_30d=Decimal('2'))
        rows=[base,dict(base,excess_30d=None),dict(base,membership_qualified=False,excess_30d=Decimal('100'))]
        result=signal_stats(rows)['train']
        self.assertEqual(result['events'],2)
        self.assertEqual(result['completed'],1)
        self.assertEqual(result['standard']['average'],Decimal('2'))
        self.assertEqual(result['standard']['win_rate'],Decimal('100'))


if __name__=='__main__': unittest.main()
