"""Offline checks for the bounded momentum counterfactual."""
import unittest
from decimal import Decimal
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    from src.backtesting.audit_acceptance_signal_impact import excess
    from src.analysis.experimental_signal import qualifies_experimental_signal


class SignalImpactTests(unittest.TestCase):
    def prices(self, end):
        return [{'close': Decimal('100')}] * 20 + [{'close': Decimal(end)}]

    def test_equal_returns_fail_strict_positive_signal(self):
        value = excess({'stock': self.prices('105'), 'SPY': self.prices('105')})
        self.assertEqual(value, Decimal('0.00'))
        self.assertFalse(qualifies_experimental_signal(dict(
            revenue_acceleration=20, operating_margin_change=1, pre_excess_20d=value)))

    def test_round_individual_returns_before_excess(self):
        self.assertEqual(excess({'stock': self.prices('105.006'), 'SPY': self.prices('102.004')}), Decimal('3.01'))

    def test_insufficient_window_is_unknown(self):
        self.assertIsNone(excess({'stock': self.prices('105')[:-1], 'SPY': self.prices('102')}))


if __name__ == '__main__':
    unittest.main()
