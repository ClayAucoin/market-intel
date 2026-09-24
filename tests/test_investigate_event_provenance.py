"""Offline checks for read adapters and non-database event capture."""
from datetime import date,timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    from src.backtesting.investigate_event_provenance import PriceIndex,Capture
    from src.backtesting import build_backtest_events as builder


class ProvenanceReplayTests(unittest.TestCase):
    def setUp(self):
        self.day=date(2026,9,21)
        self.prices=PriceIndex([('ABC',self.day,Decimal('10'),Decimal('11')),
            ('ABC',self.day+timedelta(days=1),Decimal('12'),None),
            ('ABC',self.day+timedelta(days=2),Decimal('13'),Decimal('14'))])

    def test_exact_next_and_prior_have_distinct_null_and_boundary_semantics(self):
        self.assertIsNone(self.prices.on('ABC',self.day-timedelta(days=1)))
        self.assertEqual(self.prices.next_date('ABC',self.day-timedelta(days=7)),self.day)
        self.assertIsNone(self.prices.next_date('ABC',self.day-timedelta(days=8)))
        self.assertEqual(self.prices.next_date('ABC',self.day+timedelta(days=1)),self.day+timedelta(days=1))
        self.assertEqual(self.prices.prior('ABC',self.day+timedelta(days=2)),[dict(trade_date=self.day,close=Decimal('11'))])
        self.assertEqual(self.prices.prior('ABC',self.day),[])
        with self.assertRaises(TypeError):self.prices.after('ABC',self.day+timedelta(days=1))

    def test_capture_rejects_destructive_sql(self):
        sink=Capture()
        for query in ('DELETE FROM backtest_events','UPDATE filings SET acceptance_datetime=now()','SELECT 1'):
            with self.assertRaises(ValueError):sink.execute(query,())

    def test_original_save_maps_all_fields_without_a_database(self):
        sink=Capture()
        context={k:Decimal('1') for k in ('pre_return_20d','pre_return_60d','pre_excess_20d','pre_excess_60d',
            'pre_volatility_20d','previous_close','entry_open','opening_gap_pct','spy_opening_gap_pct','opening_gap_excess')}
        horizons={h:dict(exit_date=None,return_=None,benchmark_return=None,excess_return=None) for h in builder.HORIZONS}
        for row in horizons.values():row['return']=row.pop('return_')
        kwargs=dict(conn=sink,security_id=1,period_end=self.day,entry_date=self.day,entry_price=Decimal('10'),
            revenue_yoy=1,revenue_acceleration=20,eps_yoy=1,gross_margin_change=1,operating_margin_change=1,
            market_context=context,horizon_results=horizons)
        with patch.object(builder,'get_connection',side_effect=AssertionError('No DB')):
            builder.save_backtest_event(**kwargs)
        row=sink.events[1,self.day]
        self.assertEqual(row['revenue_acceleration'],20)
        self.assertEqual(row['pre_excess_20d'],Decimal('1'))
        self.assertIsNone(row['excess_30d'])
        with self.assertRaises(ValueError):builder.save_backtest_event(**kwargs)


if __name__=='__main__':unittest.main()
