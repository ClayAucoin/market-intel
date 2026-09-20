"""Offline paper execution tests. No database, credentials, APIs or notifications.

The transactional double verifies SQL call ordering/state and rollback, not
PostgreSQL's implementation of constraints/row locks. Migration is never run.
"""
import copy
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal as D
import sys
import threading
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

# Prevent application imports from loading real configuration or notification SDKs.
notifier = types.ModuleType('src.notifications.notifier')
notifier.send_notification = Mock(side_effect=AssertionError('No notifications in offline tests'))
with patch('dotenv.load_dotenv'), patch.dict(sys.modules, {'src.notifications.notifier': notifier}):
    from src.paper_trading import paper_trading_engine as engine
    from src.paper_trading import paper_execution as rules
    from src.paper_trading import paper_position_manager as manager
    from src.paper_trading import run_paper_trading as runner
    from src.paper_trading import paper_trading_report as report
    from src.migrations.migrate_prospective_paper_trading import MIGRATION_SQL
    from src.migrations.migrate_paper_cutover_immutability import MIGRATION_SQL as CUTOVER_SQL

EASTERN = rules.EASTERN
FRIDAY = date(2026, 9, 18)
MONDAY = date(2026, 9, 21)
NOW = datetime(2026, 9, 18, 18, tzinfo=EASTERN)


def account():
    return dict(id=1, name=engine.ACCOUNT_NAME, cash=D(10000), starting_cash=D(10000),
                trade_size=D(1000), ticker_cap_percent=D(20), holding_days=45,
                prospective_cutover_at=NOW-timedelta(days=1))


def event():
    return dict(id=1, security_id=10, ticker='ABC', sector='Technology',
                period_end=date(2026, 6, 30), entry_date=FRIDAY, entry_price=D(999),
                revenue_yoy=D(30), revenue_acceleration=D(25), eps_yoy=D(30),
                operating_margin_change=D(1), pre_excess_20d=D(2))


def provenance():
    return dict(accession_number='test-accession', company_id=20, filing_company_id=20,
                filed_date=FRIDAY, filing_date=FRIDAY,
                acceptance_datetime=NOW.replace(hour=8))


def recommendation():
    return engine.add_scores([event()], {'Technology': {'label': 'Supported'}})[0]


class MemoryDB:
    def __init__(self):
        self.account = account()
        self.event = event()
        self.source = [provenance()]
        self.signals = {}
        self.positions = {}
        self.prices = {MONDAY: D(50)}
        self.lock = threading.RLock()
        self.queries = []
        self.fail_debit = False

    def connect(self):
        return Connection(self)


class Connection:
    def __init__(self, db):
        self.db = db
        self.locked = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if self.locked:
            if exc_type:
                self.db.account, self.db.signals, self.db.positions = self.snapshot
            self.db.lock.release()

    def cursor(self, **_):
        return Cursor(self)


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.db = connection.db
        self.rows = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows

    def execute(self, sql, params=()):
        q = ' '.join(sql.split())
        self.db.queries.append((q, params))
        self.rows = []
        self.rowcount = 0
        db = self.db
        if q.startswith('SELECT') and 'FROM paper_accounts' in q and 'FOR UPDATE' in q:
            assert not self.connection.locked, 'account must be first and locked once'
            db.lock.acquire()
            self.connection.locked = True
            self.connection.snapshot = copy.deepcopy((db.account, db.signals, db.positions))
            self.rows = [copy.deepcopy(db.account)]
        elif q.startswith(('INSERT', 'UPDATE')) or 'FOR UPDATE' in q:
            assert self.connection.locked, 'write/signal/position lock before account lock'
            self.mutation_or_lock(q, params)
        elif q.startswith('SELECT * FROM backtest_events'):
            self.rows = [copy.deepcopy(db.event)] if db.event and db.event['id'] == params[0] else []
        elif 'FROM financial_facts' in q:
            self.rows = copy.deepcopy(db.source)
        elif q.startswith('SELECT ticker, invested_amount'):
            self.rows = [copy.deepcopy(p) for p in db.positions.values() if p['status'] == 'OPEN']
        elif q.startswith('SELECT ticker, committed_amount'):
            self.rows = [copy.deepcopy(p) for p in db.signals.values() if p['action'] == 'PENDING_BUY']
        elif q.startswith('SELECT id FROM paper_positions WHERE signal_id'):
            self.rows = [dict(id=p['id']) for p in db.positions.values() if p['signal_id'] == params[0]]
        elif q.startswith('SELECT adjusted_open FROM daily_prices'):
            if params[1] in db.prices:
                self.rows = [dict(adjusted_open=db.prices[params[1]])]
        else:
            raise AssertionError(f'Unexpected SQL: {q}')

    def mutation_or_lock(self, q, p):
        db = self.db
        if q.startswith('SELECT id, action FROM paper_signals'):
            self.rows = [copy.deepcopy(s) for s in db.signals.values()
                         if (s['account_id'], s['security_id'], s['period_end']) == p]
        elif q.startswith('SELECT * FROM paper_signals'):
            self.rows = [copy.deepcopy(db.signals[p[0]])] if p[0] in db.signals else []
        elif q.startswith('SELECT * FROM paper_positions'):
            self.rows = [copy.deepcopy(db.positions[p[0]])] if p[0] in db.positions else []
        elif q.startswith('INSERT INTO paper_signals'):
            columns = q.split('(', 1)[1].split(')', 1)[0].replace(' ', '').split(',')
            s = dict(zip(columns, p))
            assert not any((s['account_id'], s['security_id'], s['period_end']) ==
                           (v['account_id'], v['security_id'], v['period_end']) for v in db.signals.values())
            s.update(id=len(db.signals)+1, execution_session_date=None)
            db.signals[s['id']] = s
        elif q.startswith('UPDATE paper_signals SET execution_session_date'):
            db.signals[p[1]]['execution_session_date'] = p[0]
        elif q.startswith('INSERT INTO paper_positions'):
            assert not any(v['signal_id'] == p[1] for v in db.positions.values())
            keys = ('account_id','signal_id','security_id','ticker','entry_date','entry_price',
                    'shares','invested_amount','planned_exit_date')
            position = dict(zip(keys,p), id=len(db.positions)+1, status='OPEN')
            db.positions[position['id']] = position
        elif q.startswith('UPDATE paper_accounts SET cash = cash -'):
            if db.fail_debit:
                raise RuntimeError('simulated debit failure')
            db.account['cash'] -= p[0]
        elif q.startswith("UPDATE paper_signals SET action = 'BUY'"):
            if db.signals[p[1]]['action'] == 'PENDING_BUY':
                db.signals[p[1]]['action'] = 'BUY'
                self.rowcount = 1
        elif q.startswith('UPDATE paper_positions'):
            position = db.positions[p[5]]
            if position['status'] == 'OPEN':
                position.update(status='CLOSED', exit_date=p[0], exit_price=p[1],
                                exit_value=p[2], profit=p[3], return_percent=p[4])
                self.rows = [dict(id=position['id'])]
        elif q.startswith('UPDATE paper_accounts SET cash = cash +'):
            db.account['cash'] += p[0]
            self.rows = [dict(cash=db.account['cash'])]
        else:
            raise AssertionError(f'Unexpected write/lock SQL: {q}')


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.db = MemoryDB()
        self.addCleanup(patch.stopall)
        patch.object(engine, 'get_connection', self.db.connect).start()
        patch.object(manager, 'get_connection', self.db.connect).start()
        # Guard against any accidental connection through another code path.
        patch('psycopg.connect', side_effect=AssertionError('No database access')).start()
        patch.object(engine, 'eastern_now', return_value=NOW).start()
        patch.object(engine, 'observed_sessions', return_value=[FRIDAY]).start()
        patch.object(manager, 'eastern_now', return_value=NOW+timedelta(days=60)).start()

    def commit(self):
        return engine.process_recommendation(recommendation())

    def fill(self, now=None, sessions=None):
        with patch.object(engine, 'observed_sessions', return_value=sessions or [MONDAY]):
            return self.fill_transaction(now)

    def fill_transaction(self, now=None):
        with self.db.connect() as conn:
            with conn.cursor() as cur:
                a = engine.lock_account(cur)
                return engine.fill_pending_signal(cur,a,1,now or NOW+timedelta(days=3))

    def test_fresh_commitment_reserves_without_buy_or_debit(self):
        self.assertEqual(self.commit(), 'PENDING_BUY')
        self.assertEqual(self.db.account['cash'], D(10000))
        self.assertFalse(self.db.positions)
        signal = self.db.signals[1]
        self.assertEqual(signal['purchase_committed_at'], NOW)
        self.assertEqual(signal['not_before_date'], FRIDAY+timedelta(days=1))
        self.assertEqual(signal['committed_amount'], D(1000))
        self.assertEqual(signal['signal_date'], FRIDAY)

    def test_cutover_unset(self):
        self.db.account['prospective_cutover_at'] = None
        self.assertEqual(self.commit(), 'CUTOVER_UNSET')
        self.assertFalse(self.db.signals)

    def test_pre_cutover_rejected(self):
        self.db.account['prospective_cutover_at'] = NOW
        self.assertEqual(self.commit(), 'NOT_FRESH')
        self.assertFalse(self.db.signals)

    def test_stale_event_rejected(self):
        item = recommendation()
        item['row']['entry_date'] -= timedelta(days=1)
        self.assertEqual(engine.process_recommendation(item), 'STALE_EVENT')
        self.assertFalse(self.db.signals)

    def test_ambiguous_provenance_rejected(self):
        self.db.source *= 2
        self.assertEqual(self.commit(), 'NOT_FRESH')

    def test_rebuild_changed_event_rejected(self):
        self.db.event['operating_margin_change'] = D(-1)
        self.assertEqual(self.commit(), 'EVENT_CHANGED')

    def test_wait_crossing_midnight_does_not_catch_up(self):
        engine.eastern_now.side_effect = [NOW, NOW+timedelta(days=1)]
        self.assertEqual(self.commit(), 'MISSED_PRODUCTION_DAY')
        self.assertFalse(self.db.signals)

    def test_missing_spy_coverage_rejected(self):
        engine.observed_sessions.return_value = None
        self.assertEqual(self.commit(), 'NOT_FRESH')

    def test_session_integrity_prevents_catch_up_commitments(self):
        thursday = FRIDAY - timedelta(days=1)
        wednesday = FRIDAY - timedelta(days=2)
        self.db.account['prospective_cutover_at'] = NOW - timedelta(days=2)
        self.db.source[0].update(
            acceptance_datetime=NOW.replace(hour=8) - timedelta(days=1),
            filed_date=thursday, filing_date=thursday)
        for spy_dates, stock_dates in (
            ([wednesday, FRIDAY], [wednesday, FRIDAY]),  # synchronized gap
            ([wednesday, FRIDAY], [wednesday, thursday, FRIDAY]),
            ([wednesday, thursday, FRIDAY], [wednesday, FRIDAY]),
        ):
            with self.subTest(spy=spy_dates, stock=stock_dates):
                cur = Mock()
                cur.fetchall.side_effect = [
                    [dict(trade_date=d, adjusted_open=D(100), adjusted_close=D(101))
                     for d in spy_dates],
                    [dict(trade_date=d) for d in stock_dates],
                ]
                engine.observed_sessions.side_effect = (
                    lambda unused, start, end: rules.observed_sessions(cur, start, end))
                self.assertEqual(self.commit(), 'NOT_FRESH')
                self.assertFalse(self.db.signals)
                self.assertFalse(self.db.positions)
                self.assertEqual(self.db.account['cash'], D(10000))

    def test_complete_session_evidence_allows_commitment(self):
        cur = Mock()
        cur.fetchall.side_effect = [
            [dict(trade_date=d, adjusted_open=D(100), adjusted_close=D(101))
             for d in (FRIDAY-timedelta(days=1), FRIDAY)],
            [dict(trade_date=FRIDAY)],
        ]
        engine.observed_sessions.side_effect = (
            lambda unused, start, end: rules.observed_sessions(cur, start, end))
        self.assertEqual(self.commit(), 'PENDING_BUY')
        self.assertEqual(self.db.account['cash'], D(10000))

    def test_uncertain_session_evidence_cannot_fill_pending_purchase(self):
        self.assertEqual(self.commit(), 'PENDING_BUY')
        engine.observed_sessions.return_value = None
        self.assertIsNone(self.fill_transaction())
        self.assertEqual(self.db.signals[1]['action'], 'PENDING_BUY')
        self.assertFalse(self.db.positions)
        self.assertEqual(self.db.account['cash'], D(10000))

    def test_rerun_and_concurrent_calls_commit_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.commit(), range(2)))
        self.assertCountEqual(results, ['PENDING_BUY','ALREADY_RECORDED'])
        self.assertEqual(len(self.db.signals), 1)
        self.assertEqual(self.commit(), 'ALREADY_RECORDED')

    def test_skip_states_terminal(self):
        for cash, cap, expected in [(D(500),D(20),'SKIP_CASH'), (D(10000),D(5),'SKIP_CAP')]:
            self.db.signals.clear()
            self.db.account.update(cash=cash, ticker_cap_percent=cap)
            self.assertEqual(self.commit(), expected)
            for field in ('purchase_committed_at', 'not_before_date', 'committed_amount',
                          'source_accession', 'source_acceptance_at', 'execution_session_date'):
                self.assertIsNone(self.db.signals[1][field])
            self.db.account.update(cash=D(10000),ticker_cap_percent=D(20))
            self.assertEqual(self.commit(), 'ALREADY_RECORDED')

    def test_new_logical_event_sees_existing_cash_reservation(self):
        self.db.account.update(cash=D(1500),ticker_cap_percent=D(100))
        self.assertEqual(self.commit(),'PENDING_BUY')
        item = recommendation()
        item['row']['period_end'] -= timedelta(days=1)
        self.db.event = copy.deepcopy(item['row'])
        self.assertEqual(engine.process_recommendation(item),'SKIP_CASH')
        self.assertEqual(self.db.account['cash'],D(1500))

    def test_new_logical_event_sees_existing_ticker_reservation(self):
        self.db.account['ticker_cap_percent'] = D(10)
        self.assertEqual(self.commit(),'PENDING_BUY')
        item = recommendation()
        item['row']['period_end'] -= timedelta(days=1)
        self.db.event = copy.deepcopy(item['row'])
        self.assertEqual(engine.process_recommendation(item),'SKIP_CAP')
        self.assertEqual(self.db.account['cash'],D(10000))

    def test_fill_exact_prospective_price_and_45_day_hold(self):
        self.commit()
        self.db.account['trade_size'] = D(9999)
        result = self.fill()
        p = self.db.positions[1]
        self.assertEqual(result['action'], 'BUY')
        self.assertEqual(result['execution_session_date'], MONDAY)
        self.assertEqual(result['signal_date'], FRIDAY)
        self.assertEqual(result['entry_date'], MONDAY)
        self.assertEqual(p['entry_date'], MONDAY)
        self.assertEqual(p['entry_price'], D(50))
        self.assertNotEqual(p['entry_price'], self.db.event['entry_price'])
        self.assertEqual(p['invested_amount'], D(1000))
        self.assertEqual(p['shares'], D(20))
        self.assertEqual(p['planned_exit_date'], MONDAY+timedelta(days=45))
        self.assertEqual(self.db.account['cash'], D(9000))
        self.assertEqual(self.db.signals[1]['action'], 'BUY')
        self.assertEqual(self.db.signals[1]['purchase_committed_at'], NOW)

    def test_missing_exact_open_does_not_skip_to_tuesday(self):
        self.commit()
        self.db.prices = {MONDAY+timedelta(days=1): D(60)}
        self.assertIsNone(self.fill(sessions=[MONDAY, MONDAY+timedelta(days=1)]))
        self.assertEqual(self.db.signals[1]['execution_session_date'], MONDAY)
        self.assertFalse(self.db.positions)
        self.assertEqual(self.db.account['cash'], D(10000))
        self.db.prices[MONDAY] = D(50)
        self.assertIsNotNone(self.fill())

    def test_future_or_uncompleted_session_cannot_fill(self):
        self.commit()
        self.assertIsNone(self.fill(now=NOW))
        self.assertIsNone(self.fill(now=(NOW+timedelta(days=3)).replace(hour=15)))
        self.assertFalse(self.db.positions)

    def test_fill_does_not_recheck_historical_qualification(self):
        self.commit()
        self.db.event = None
        self.db.source = []
        self.assertIsNotNone(self.fill())

    def test_existing_position_blocks_second_debit_even_if_signal_is_pending(self):
        self.commit()
        self.fill()
        self.db.signals[1]['action'] = 'PENDING_BUY'
        with self.assertRaises(ValueError):
            self.fill()
        self.assertEqual(self.db.account['cash'],D(9000))

    def test_disabled_main_does_not_evaluate_candidates(self):
        self.db.account['prospective_cutover_at'] = None
        with patch.object(engine,'get_current_recommendations') as recommendations:
            engine.main('expanded_500')
        recommendations.assert_not_called()

    def test_invalid_open_remains_pending(self):
        self.commit()
        for value in [None, D(0), D(-1), D('NaN'), D('Infinity')]:
            self.db.prices[MONDAY] = value
            self.assertIsNone(self.fill())
        self.assertFalse(self.db.positions)

    def test_changed_frozen_session_fails_closed(self):
        self.commit()
        self.db.signals[1]['execution_session_date'] = MONDAY+timedelta(days=1)
        self.assertIsNone(self.fill())

    def test_concurrent_fill_debits_once(self):
        self.commit()
        with patch.object(engine, 'observed_sessions', return_value=[MONDAY]):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: self.fill_transaction(), range(2)))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(len(self.db.positions),1)
        self.assertEqual(self.db.account['cash'],D(9000))

    def test_fill_rollback_is_atomic(self):
        self.commit()
        self.db.fail_debit = True
        with self.assertRaises(RuntimeError):
            self.fill()
        self.assertFalse(self.db.positions)
        self.assertEqual(self.db.signals[1]['action'],'PENDING_BUY')
        self.assertEqual(self.db.account['cash'],D(10000))

    def test_underfunded_reservations_block_fill(self):
        self.commit()
        self.db.account['cash'] = D(500)
        with self.assertRaises(ValueError):
            self.fill()
        self.assertFalse(self.db.positions)

    def test_concurrent_close_credits_once(self):
        self.commit()
        self.fill()
        position = copy.deepcopy(self.db.positions[1])
        exit_data = dict(exit_date=position['planned_exit_date'],exit_price=D(55))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: manager.close_position(account(),position,exit_data),range(2)))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertEqual(self.db.account['cash'],D(10100))
        self.assertEqual(self.db.positions[1]['status'],'CLOSED')

    def test_pending_never_sends_filled_notification(self):
        self.commit()
        with patch.dict(sys.modules, {'src.notifications.notifier': notifier}), \
             patch.object(notifier, 'send_notification') as send:
            engine.send_buy_notification(self.db.signals[1])
        send.assert_not_called()

    def test_fill_notification_restores_frozen_qualification_details(self):
        self.commit()
        result = self.fill()
        with patch.dict(sys.modules, {'src.notifications.notifier': notifier}), \
             patch.object(notifier, 'send_notification') as send:
            engine.send_buy_notification(result)
        message = send.call_args.kwargs['message']
        self.assertIn('PAPER BUY FILLED', send.call_args.kwargs['subject'])
        for text in ('Historical signal date: 2026-09-18',
                     'Actual paper entry date: 2026-09-21',
                     'Revenue acceleration: +25.00%',
                     'Operating margin change: +1.00%',
                     '20-day excess return vs. SPY: +2.00%',
                     'Revenue acceleration >= 20%',
                     'Operating margin change > 0%',
                     '20-day excess return vs. SPY > 0%',
                     result['recommendation_reason'], result['action_reason']):
            self.assertIn(text, message)


class RuleTests(unittest.TestCase):
    def test_pending_cash_and_ticker_exposure_reserved(self):
        a = account()
        a['cash'] = D(1500)
        pending = [dict(ticker='XYZ',committed_amount=D(1000))]
        self.assertEqual(rules.reservation_action(a,[],pending,'ABC')[0],'SKIP_CASH')
        a['cash'] = D(10000)
        pending = [dict(ticker='abc',committed_amount=D(2000))]
        self.assertEqual(rules.reservation_action(a,[],pending,'ABC')[0],'SKIP_CAP')

    def test_pending_not_double_counted_in_cap_denominator(self):
        a = account()
        positions = [dict(ticker='ABC',invested_amount=D(1000))]
        a['cash'] = D(9000)
        pending = [dict(ticker='XYZ',committed_amount=D(8000))]
        # Denominator remains 10000, so exactly 2000 of ABC is allowed.
        self.assertEqual(rules.reservation_action(a,positions,pending,'ABC')[0],'PENDING_BUY')
        positions[0]['invested_amount'] = D(1100)
        self.assertEqual(rules.reservation_action(a,positions,pending,'ABC')[0],'SKIP_CAP')

    def test_report_distinguishes_pending_cash_and_signal_date(self):
        from contextlib import redirect_stdout
        from io import StringIO
        a = account()
        a.update(created_at=NOW, minimum_priority=3)
        pending = dict(ticker='ABC', signal_date=FRIDAY, purchase_committed_at=NOW,
                       not_before_date=FRIDAY+timedelta(days=1), committed_amount=D(1000),
                       execution_session_date=None)
        benchmark = dict(symbol='SPY',start_date=None,start_price=None,latest_date=None,
                         latest_price=None,return_percent=None)
        output = StringIO()
        with patch.object(report,'get_connection',return_value=MagicMock()), \
             patch.object(report,'get_account',return_value=a), \
             patch.object(report,'get_pending_commitments',return_value=[pending]), \
             patch.object(report,'get_open_positions',return_value=[]), \
             patch.object(report,'get_closed_positions',return_value=[]), \
             patch.object(report,'get_signal_summary',return_value={'PENDING_BUY':1}), \
             patch.object(report,'get_benchmark_performance',return_value=benchmark), \
             redirect_stdout(output):
            report.main()
        self.assertIn('Spendable cash:       $9,000.00',output.getvalue())
        self.assertIn('Reserved cash:        $1,000.00',output.getvalue())
        self.assertIn('PENDING (not a filled BUY)',output.getvalue())
        self.assertIn('historical signal 2026-09-18',output.getvalue())

    def sessions(self, start, end, dates, stock_dates=None):
        cur = Mock()
        cur.fetchall.side_effect = [
            [dict(trade_date=d,adjusted_open=D(100),adjusted_close=D(101)) for d in dates],
            [dict(trade_date=d) for d in (stock_dates if stock_dates is not None else dates)],
        ]
        return rules.observed_sessions(cur,start,end)

    def test_friday_commitment_weekend_and_monday(self):
        start = FRIDAY+timedelta(days=1)
        self.assertEqual(self.sessions(start,start,[FRIDAY]),[])
        self.assertEqual(self.sessions(start,MONDAY,[FRIDAY,MONDAY]),[MONDAY])

    def test_weekday_holiday_without_calendar_fails_closed(self):
        friday = date(2026,9,4)
        tuesday = date(2026,9,8)
        # Local absence cannot prove that Monday was a holiday.
        self.assertIsNone(self.sessions(friday+timedelta(days=1),tuesday,[friday,tuesday]))

    def test_complete_weekday_evidence(self):
        self.assertEqual(self.sessions(FRIDAY, FRIDAY,
                                       [FRIDAY-timedelta(days=1), FRIDAY]), [FRIDAY])

    def test_synchronized_september_17_gap_fails_closed(self):
        self.assertIsNone(self.sessions(FRIDAY-timedelta(days=1), FRIDAY,
                                       [FRIDAY-timedelta(days=2), FRIDAY]))

    def test_friday_acceptance_and_weekend_candidates_reach_monday(self):
        for accepted in (NOW.replace(hour=9, minute=30), NOW,
                         NOW+timedelta(days=1), NOW+timedelta(days=2)):
            with self.subTest(accepted=accepted):
                p = dict(provenance(), acceptance_datetime=accepted)
                start = rules.get_candidate_entry_date(p)
                sessions = self.sessions(start, MONDAY, [FRIDAY, MONDAY])
                self.assertEqual(sessions, [MONDAY])
                self.assertIsNone(rules.freshness_reason(
                    dict(event(), entry_date=MONDAY), [p], NOW-timedelta(days=1),
                    NOW+timedelta(days=3), sessions))

    def test_invalid_spy_evidence_fails_closed(self):
        for price in (None, D(0), D('NaN'), D('Infinity')):
            with self.subTest(price=price):
                cur = Mock()
                cur.fetchall.return_value = [
                    dict(trade_date=FRIDAY-timedelta(days=1), adjusted_open=D(100), adjusted_close=D(101)),
                    dict(trade_date=FRIDAY, adjusted_open=price, adjusted_close=D(101)),
                ]
                self.assertIsNone(rules.observed_sessions(cur, FRIDAY, FRIDAY))

    def test_missing_spy_with_stock_evidence_fails_closed(self):
        self.assertIsNone(self.sessions(FRIDAY,MONDAY,[FRIDAY-timedelta(days=1),MONDAY],
                                       [FRIDAY-timedelta(days=1),FRIDAY,MONDAY]))

    def test_no_prior_anchor_fails_closed(self):
        self.assertIsNone(self.sessions(FRIDAY,FRIDAY,[FRIDAY]))

    def test_completed_session_bound(self):
        self.assertEqual(rules.completed_through(NOW.replace(hour=15)), FRIDAY-timedelta(days=1))
        self.assertEqual(rules.completed_through(NOW), FRIDAY)
        cur = Mock()
        self.assertIsNone(rules.observed_sessions(cur, MONDAY, FRIDAY))
        cur.execute.assert_not_called()

    def test_freshness_rejects_prior_session_even_if_stock_entry_is_today(self):
        p = provenance()
        p['acceptance_datetime'] = NOW-timedelta(days=1,hours=10)
        self.assertIsNotNone(rules.freshness_reason(event(),[p],NOW-timedelta(days=5),NOW,
                                                   [FRIDAY-timedelta(days=1),FRIDAY]))

    def test_intraday_filing_previous_day_is_fresh_today(self):
        p = provenance()
        p['acceptance_datetime'] = NOW-timedelta(days=1,hours=6)
        self.assertIsNone(rules.freshness_reason(event(),[p],NOW-timedelta(days=5),NOW,[FRIDAY]))

    def test_after_hours_friday_first_session_monday(self):
        row = event()
        row['entry_date'] = MONDAY
        p = provenance()
        p['acceptance_datetime'] = NOW
        self.assertIsNone(rules.freshness_reason(row,[p],NOW-timedelta(days=1),
                                                 NOW+timedelta(days=3),[MONDAY]))

    def test_premarket_production_and_future_acceptance_rejected(self):
        self.assertIsNotNone(rules.freshness_reason(event(),[provenance()],NOW-timedelta(days=1),
                                                   NOW.replace(hour=9),[FRIDAY]))
        p = provenance()
        p['acceptance_datetime'] = NOW+timedelta(hours=1)
        self.assertIsNotNone(rules.freshness_reason(event(),[p],NOW-timedelta(days=1),NOW,[FRIDAY]))

    def test_runner_order(self):
        calls = []
        with patch.object(runner,'fill_pending_purchases',side_effect=lambda: calls.append('fill')), \
             patch.object(runner,'manage_positions',side_effect=lambda: calls.append('close')), \
             patch.object(runner,'process_signals',side_effect=lambda _: calls.append('commit')), \
             patch.object(runner,'show_report',side_effect=lambda: calls.append('report')):
            runner.main('expanded_500')
        self.assertEqual(calls,['fill','close','commit','report'])

    def test_migration_does_not_activate_or_rewrite_records(self):
        self.assertNotIn('UPDATE paper_accounts', MIGRATION_SQL)
        self.assertNotIn('UPDATE paper_signals', MIGRATION_SQL)
        self.assertIn('ON paper_signals (account_id, security_id, period_end)', MIGRATION_SQL)
        self.assertIn('ON paper_positions (signal_id)', MIGRATION_SQL)
        self.assertIn('A paper purchase commitment is immutable', MIGRATION_SQL)


class SchemaPredicateTests(unittest.TestCase):
    """Exercise actual migration predicates via SELECT expressions only.

    SQLite is an offline expression evaluator, NOT a PostgreSQL integration
    test. Adapt only PostgreSQL regex, timezone/date and numeric literal syntax.
    DDL, PL/pgSQL execution and PostgreSQL numeric semantics remain untested.
    """
    def setUp(self):
        self.sql = sqlite3.connect(':memory:')
        self.addCleanup(self.sql.close)
        self.sql.create_function('nonblank', 1, lambda s: bool(s and s.strip()))
        self.sql.create_function('next_eastern_date', 1, lambda s: (
            (datetime.fromisoformat(s).astimezone(EASTERN).date() + timedelta(days=1)).isoformat()
            if s else None))
        self.row = dict(action='PENDING_BUY', purchase_committed_at=NOW,
                        not_before_date=FRIDAY+timedelta(days=1), committed_amount=D(1000),
                        source_accession='test-accession', source_acceptance_at=NOW-timedelta(hours=10),
                        execution_session_date=None, account_id=1, security_id=10,
                        period_end=date(2026,6,30), signal_date=FRIDAY, ticker='ABC')
        self.check = MIGRATION_SQL.split('CHECK (', 1)[1].split(');', 1)[0]
        self.check = self.check.replace("source_accession ~ '[^[:space:]]'", 'nonblank(source_accession)')
        self.check = self.check.replace("'Infinity'::numeric", '1e999')
        self.check = self.check.replace(
            "(purchase_committed_at AT TIME ZONE 'America/New_York')::date + 1",
            'next_eastern_date(purchase_committed_at)')
        self.guards = re.findall(r'IF (.*?) THEN\s*RAISE EXCEPTION',
                                 MIGRATION_SQL.split('CREATE OR REPLACE FUNCTION preserve_paper_commitment()',1)[1]
                                 .split('END $$;',1)[0], re.S)
        self.assertEqual(len(self.guards), 4)

    def evaluate(self, expression, bindings):
        for key in sorted(bindings, key=len, reverse=True):
            expression = re.sub(r'\b' + re.escape(key) + r'\b', ':' + key.replace('.', '_'), expression)
        values = {k.replace('.', '_'): (v.isoformat() if isinstance(v, (date, datetime))
                  else float(v) if isinstance(v, D) else v) for k,v in bindings.items()}
        return self.sql.execute('SELECT ' + expression, values).fetchone()[0]

    def valid(self, row):
        return self.evaluate(self.check, row)

    def transition(self, old, new):
        bindings = {**{'OLD.'+k:v for k,v in old.items()}, **{'NEW.'+k:v for k,v in new.items()}}
        return self.valid(new) == 1 and not any(
            self.evaluate(re.sub(r'\bROW\(', '(', guard), bindings) == 1 for guard in self.guards)

    def test_valid_pending(self):
        self.assertEqual(self.valid(self.row), 1)

    def test_each_missing_commitment_component_rejected(self):
        for key in ('purchase_committed_at', 'not_before_date', 'committed_amount',
                    'source_accession', 'source_acceptance_at'):
            with self.subTest(key=key):
                self.assertEqual(self.valid(dict(self.row, **{key:None})), 0)

    def test_blank_accession_rejected(self):
        for value in ('', ' ', '\t\n '):
            with self.subTest(value=value):
                self.assertEqual(self.valid(dict(self.row, source_accession=value)), 0)

    def test_invalid_amounts_rejected(self):
        for value in (D(0), D(-1), D('Infinity'), D('-Infinity'), D('NaN')):
            with self.subTest(value=value):
                self.assertEqual(self.valid(dict(self.row, committed_amount=value)), 0)

    def test_invalid_timing_rejected(self):
        for changes in (dict(source_acceptance_at=NOW+timedelta(seconds=1)),
                        dict(not_before_date=FRIDAY), dict(execution_session_date=FRIDAY)):
            with self.subTest(changes=changes):
                self.assertEqual(self.valid(dict(self.row, **changes)), 0)

    def terminal(self, action):
        return dict(self.row, action=action, **{k:None for k in (
            'purchase_committed_at','not_before_date','committed_amount',
            'source_accession','source_acceptance_at','execution_session_date')})

    def test_terminal_metadata_rejected(self):
        for action in ('SKIP_CASH','SKIP_CAP'):
            row = self.terminal(action)
            self.assertEqual(self.valid(row), 1)
            for key in ('purchase_committed_at','not_before_date','committed_amount',
                        'source_accession','source_acceptance_at','execution_session_date'):
                with self.subTest(action=action, field=key):
                    self.assertEqual(self.valid(dict(row, **{key:self.row[key] or MONDAY})), 0)

    def test_unknown_and_null_actions_rejected(self):
        for action in ('WAIT', 'OTHER', None):
            self.assertEqual(self.valid(self.terminal(action)), 0)

    def test_buy_requires_execution_session(self):
        self.assertEqual(self.valid(dict(self.row, action='BUY')), 0)
        self.assertEqual(self.valid(dict(self.row, action='BUY', execution_session_date=MONDAY)), 1)

    def test_valid_pending_to_buy(self):
        frozen = dict(self.row, execution_session_date=MONDAY)
        self.assertTrue(self.transition(self.row, frozen))
        self.assertTrue(self.transition(frozen, dict(frozen, action='BUY')))

    def test_terminal_skip_cannot_commit(self):
        for action in ('SKIP_CASH','SKIP_CAP'):
            self.assertFalse(self.transition(self.terminal(action), self.row))

    def test_buy_cannot_become_pending(self):
        buy = dict(self.row, action='BUY', execution_session_date=MONDAY)
        self.assertFalse(self.transition(buy, dict(buy, action='PENDING_BUY')))

    def test_session_freezes_once(self):
        frozen = dict(self.row, execution_session_date=MONDAY)
        self.assertTrue(self.transition(self.row, frozen))
        for action in ('PENDING_BUY','BUY'):
            old = dict(frozen, action=action)
            self.assertTrue(self.transition(old, old))
            for session in (None, MONDAY+timedelta(days=1)):
                self.assertFalse(self.transition(old, dict(old, execution_session_date=session)))

    def test_frozen_identity_and_provenance_cannot_change(self):
        changes = dict(account_id=2, security_id=11, period_end=date(2026,3,31),
                       signal_date=MONDAY, ticker='XYZ', source_accession='changed',
                       source_acceptance_at=NOW-timedelta(hours=9), committed_amount=D(900),
                       purchase_committed_at=NOW+timedelta(minutes=1))
        for key,value in changes.items():
            with self.subTest(field=key):
                self.assertFalse(self.transition(self.row, dict(self.row, **{key:value})))


class CutoverProtectionTests(unittest.TestCase):
    """Evaluate the actual guard offline; PostgreSQL trigger execution is not tested."""

    def setUp(self):
        self.sql = sqlite3.connect(':memory:')
        self.addCleanup(self.sql.close)
        guards = re.findall(r'IF (.*?) THEN\s*RAISE EXCEPTION', CUTOVER_SQL, re.S)
        self.assertEqual(len(guards), 1)
        self.guard = guards[0].replace('OLD.prospective_cutover_at', ':old').replace(
            'NEW.prospective_cutover_at', ':new')

    def rejected(self, old, new):
        return bool(self.sql.execute('SELECT ' + self.guard, dict(old=old, new=new)).fetchone()[0])

    def test_null_and_first_activation_allowed(self):
        self.assertFalse(self.rejected(None, None))
        self.assertFalse(self.rejected(None, NOW.isoformat()))

    def test_activated_cutover_cannot_move_or_clear(self):
        for new in (None, (NOW-timedelta(seconds=1)).isoformat(),
                    (NOW+timedelta(seconds=1)).isoformat()):
            with self.subTest(new=new):
                self.assertTrue(self.rejected(NOW.isoformat(), new))

    def test_unchanged_cutover_allows_unrelated_updates(self):
        self.assertFalse(self.rejected(NOW.isoformat(), NOW.isoformat()))
        # The actual trigger predicate consults no cash/updated_at/other columns.
        self.assertEqual(set(re.findall(r'(?:OLD|NEW)\.(\w+)', CUTOVER_SQL)),
                         {'prospective_cutover_at'})

    def test_idempotent_ddl_and_no_activation(self):
        self.assertIn('CREATE OR REPLACE FUNCTION preserve_paper_cutover()', CUTOVER_SQL)
        self.assertIn('DROP TRIGGER IF EXISTS preserve_paper_cutover ON paper_accounts;', CUTOVER_SQL)
        self.assertIn('CREATE TRIGGER preserve_paper_cutover BEFORE UPDATE ON paper_accounts', CUTOVER_SQL)
        self.assertIn('FOR EACH ROW EXECUTE FUNCTION preserve_paper_cutover()', CUTOVER_SQL)
        self.assertNotRegex(CUTOVER_SQL, r'(?i)\b(?:UPDATE\s+paper_accounts|INSERT\s+INTO|DELETE\s+FROM)\b')
        self.assertTrue(MIGRATION_SQL.endswith(CUTOVER_SQL))

    def test_migration_runs_in_one_transaction_without_account_writes(self):
        from src.migrations import migrate_paper_cutover_immutability as migration
        connection = MagicMock()
        with patch.object(migration, 'get_connection', return_value=connection):
            migration.migrate()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(CUTOVER_SQL)
        connection.__exit__.assert_called_once_with(None, None, None)


class ReportSnapshotTests(unittest.TestCase):
    def test_read_only_repeatable_read_precedes_all_reads_on_one_connection(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cur = connection.cursor.return_value.__enter__.return_value
        readers = ('get_account','get_pending_commitments','get_open_positions',
                   'get_closed_positions','get_signal_summary','get_benchmark_performance')
        calls = []
        def read(name):
            def run(*args):
                cur.execute.assert_called_once_with(
                    'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                self.assertIs(args[-1], connection)
                calls.append(name)
                return dict(account(),created_at=NOW) if name == 'get_account' else []
            return run
        from contextlib import ExitStack
        with ExitStack() as stack:
            connect = stack.enter_context(patch.object(report,'get_connection',return_value=connection))
            for name in readers:
                stack.enter_context(patch.object(report,name,side_effect=read(name)))
            report.load_report_snapshot()
        connect.assert_called_once_with()
        self.assertEqual(calls, list(readers))
        connection.__exit__.assert_called_once()

    def test_open_position_price_uses_same_connection(self):
        connection = MagicMock()
        cur = connection.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = [('ABC',MONDAY,D(50),D(20),D(1000),MONDAY+timedelta(days=45),
                                     5,3,'BUY','Supported',D(25),D(1),D(2),FRIDAY)]
        with patch.object(report,'get_connection',side_effect=AssertionError('Independent snapshot')), \
             patch.object(report,'get_latest_price',return_value=dict(trade_date=MONDAY,price=D(51))) as price:
            positions = report.get_open_positions(1, connection)
        price.assert_called_once_with('ABC', connection)
        self.assertEqual(positions[0]['market_value'],D(1020))


if __name__ == '__main__':
    unittest.main()
