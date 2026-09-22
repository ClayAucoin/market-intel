"""Offline checks of audit classification; never connect to the database."""
import unittest
from datetime import datetime, date, timezone
from decimal import Decimal
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    from src.backtesting.audit_sector_readiness import availability, dependencies, stats, valid


class AuditTests(unittest.TestCase):
    def fact(self, **changes):
        f = dict(company_id=1, filing_company_id=1, accession_number='fixture',
                 acceptance_datetime=datetime(2020,1,1,tzinfo=timezone.utc),
                 filed_date=date(2020,1,1), is_derived=False)
        f.update(changes)
        return f

    def test_direct_available(self):
        self.assertTrue(availability([self.fact()],datetime(2020,1,2,tzinfo=timezone.utc))['direct_sources_available'])

    def test_late_missing_and_derived_are_separate(self):
        now=datetime(2019,12,31,tzinfo=timezone.utc)
        self.assertTrue(availability([self.fact()],now)['late'])
        self.assertTrue(availability([self.fact(acceptance_datetime=None)],now)['missing_evidence'])
        self.assertTrue(availability([self.fact(is_derived=True)],now)['derived_lineage_unproven'])
        self.assertTrue(availability([None],now)['missing_evidence'])

    def test_wrong_issuer_is_unproven(self):
        self.assertFalse(availability([self.fact(filing_company_id=2)],datetime(2021,1,1,tzinfo=timezone.utc))['direct_sources_available'])

    def test_performance_uses_completed_only_and_stable_identity(self):
        rows=[dict(security_id=1,excess_30d=Decimal('2')),dict(security_id=1,excess_30d=None),dict(security_id=2,excess_30d=Decimal('-1'))]
        self.assertEqual(stats(rows),dict(events=3,securities=2,completed=2,sum_excess_pp=Decimal(1),mean_excess_pp=Decimal('.5')))

    def test_dependencies_include_previous_quarter_year_comparison(self):
        rev=[dict(period_end=date(y,m,30),value=Decimal(1)) for y,m in [(2019,6),(2019,9),(2020,6),(2020,9)]]
        r,o=dependencies(rev,rev,date(2020,9,30))
        self.assertEqual([x['period_end'] for x in r],[date(2020,9,30),date(2019,9,30),date(2020,6,30),date(2019,6,30)])
        self.assertEqual(len(o),4)

    def test_price_validity(self):
        for x in [None,Decimal(0),Decimal('-1'),Decimal('NaN'),Decimal('Infinity')]:
            self.assertFalse(valid(x))
        self.assertTrue(valid(Decimal(1)))


if __name__=='__main__':
    unittest.main()
