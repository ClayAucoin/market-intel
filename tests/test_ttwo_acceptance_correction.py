"""Offline transaction doubles only; never exercise writes on PostgreSQL."""
import copy
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    from src.backtesting import ttwo_acceptance_correction as tool


class MemoryDatabase:
    """Transactional state double, including failure between the two UPDATEs."""
    def __init__(self, state, fail_event=False, event_count=1, commit_uncertain=False):
        self.state = copy.deepcopy(state)
        self.fail_event = fail_event
        self.event_count = event_count
        self.commit_uncertain = commit_uncertain
        self.connections = []

    def connect(self):
        conn = MemoryConnection(self)
        self.connections.append(conn)
        return conn


class MemoryConnection:
    def __init__(self, db):
        self.db = db
        self.working = copy.deepcopy(db.state)
        self.commands = []
        self.rowcount = 0
        self.read_only = None
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, kind, error, tb):
        if kind:
            self.rolled_back = True
        else:
            self.db.state = copy.deepcopy(self.working)
            if self.db.commit_uncertain and self.read_only is False:
                raise ConnectionError('Simulated lost COMMIT acknowledgment')

    def cursor(self):
        return MemoryCursor(self)


class MemoryCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params=()):
        text = query if isinstance(query, str) else query.as_string()
        self.conn.commands.append(text)
        if text.startswith(('SET ', 'LOCK ')):
            return
        if text.startswith('UPDATE filings'):
            assert self.conn.read_only is False
            assert any(q.startswith('LOCK TABLE') for q in self.conn.commands)
            row = self.conn.working['filings'][0]
            self.rowcount = int(row['acceptance_datetime'] == params[2])
            if self.rowcount:
                row.update(acceptance_datetime=params[0], row_version='new-filing-version')
        elif text.startswith('UPDATE backtest_events'):
            if self.conn.db.fail_event:
                raise RuntimeError('Simulated second UPDATE failure')
            self.rowcount = self.conn.db.event_count
            if self.rowcount != 1:
                return
            fields = text.split(' SET ')[1].split(' WHERE ')[0].split(',')
            row = self.conn.working['events'][0]
            offset = 0
            for assignment in fields:
                name, expression = assignment.split('=')
                name = name.strip().strip('"')
                if expression == 'CURRENT_TIMESTAMP':
                    row[name] = '2026-09-25 20:00:00+00:00'
                else:
                    row[name] = params[offset]
                    offset += 1
            row['row_version'] = 'new-event-version'
        else:
            raise AssertionError('Unexpected SQL in transaction double')


class CorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = tool.read(tool.ROOT/'inputs.json')['state']
        cls.baseline = tool.calculate(cls.state, tool.OLD)
        cls.alternative = tool.calculate(cls.state, tool.NEW)
        cls.manifest = dict(event_changes={k: v for k, v in cls.alternative['fields'].items()
                                          if v != cls.baseline['fields'][k]})

    def test_all_31_baseline_fields_and_alternative(self):
        tool.verify_baseline(self.state, self.baseline)
        self.assertEqual(len(self.baseline['fields']), 31)
        alternative = self.alternative['fields']
        self.assertEqual(alternative['entry_date'], '2025-05-20')
        self.assertEqual(alternative['entry_price'], '233.02')
        self.assertEqual(alternative['return_30d'], '2.30')
        self.assertEqual(alternative['excess_30d'], '1.80')
        self.assertEqual(alternative['pre_excess_20d'], '-1.38')
        self.assertEqual(alternative['exit_date_30d'], '2025-06-20')
        self.assertEqual(alternative['exit_date_90d'], '2025-08-18')
        self.assertEqual(alternative['exit_date_180d'], '2025-11-17')
        self.assertFalse(self.baseline['exact_signal'])
        self.assertFalse(self.alternative['exact_signal'])
        self.assertEqual({k: alternative[k] for k in tool.FINANCIAL},
                         {k: self.baseline['fields'][k] for k in tool.FINANCIAL})

    def test_baseline_failure_stops(self):
        bad = copy.deepcopy(self.state)
        bad['events'][0]['return_30d'] = '0.00'
        with self.assertRaisesRegex(tool.GuardFailure, 'Baseline reproduction failed'):
            tool.verify_baseline(bad, self.baseline)

    def test_missing_sessions_and_duplicate_facts_stop(self):
        bad = copy.deepcopy(self.state)
        bad['prices'] = [p for p in bad['prices'] if p['trade_date'] >= '2025-05-01']
        with self.assertRaisesRegex(tool.GuardFailure, 'prior sessions'):
            tool.calculate(bad, tool.NEW)
        bad = copy.deepcopy(self.state)
        bad['facts'].append(bad['facts'][0])
        with self.assertRaisesRegex(tool.GuardFailure, 'Ambiguous fact'):
            tool.calculate(bad, tool.NEW)

    def test_every_dependency_group_and_row_version_is_guarded(self):
        for key in self.state:
            bad = copy.deepcopy(self.state)
            bad[key].append({'unexpected': True})
            with self.subTest(key=key), self.assertRaises((tool.GuardFailure, KeyError)):
                tool.revalidate(bad, self.state)
        bad = copy.deepcopy(self.state)
        bad['events'][0]['row_version'] = 'different-transaction-same-values'
        with self.assertRaises(tool.GuardFailure):
            tool.revalidate(bad, self.state)

    def test_replacement_event_and_already_applied_rejected(self):
        bad = copy.deepcopy(self.state)
        bad['events'][0]['id'] += 1
        with self.assertRaisesRegex(tool.GuardFailure, 'Replacement event ID'):
            tool.revalidate(bad, self.state)
        bad = copy.deepcopy(self.state)
        bad['filings'][0]['acceptance_datetime'] = tool.NEW
        with self.assertRaises(tool.GuardFailure):
            tool.revalidate(bad, self.state)

    def test_post_verification_rejects_unintended_changes(self):
        after = copy.deepcopy(self.state)
        after['filings'][0]['acceptance_datetime'] = tool.NEW
        after['events'][0].update(self.manifest['event_changes'])
        tool.verify_after(self.state, after, self.manifest)
        after['events'][0]['created_at'] = 'unexpected'
        with self.assertRaises(tool.GuardFailure):
            tool.verify_after(self.state, after, self.manifest)

    def execute_double(self, db, root, mode='apply', receipt=None):
        with ExitStack() as stack:
            stack.enter_context(patch.object(tool, 'ROOT', root))
            stack.enter_context(patch.object(tool, 'load_package', return_value=(self.manifest, self.state)))
            stack.enter_context(patch.object(tool, 'get_connection', side_effect=db.connect))
            stack.enter_context(patch.object(tool, 'snapshot', side_effect=lambda conn: copy.deepcopy(conn.working)))
            tool.execute(mode, 'test-pin', receipt)

    def test_partial_failure_rolls_back_both_updates(self):
        db = MemoryDatabase(self.state, fail_event=True)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(tool.GuardFailure):
                self.execute_double(db, Path(directory))
            self.assertEqual(db.state, self.state)
            self.assertTrue(db.connections[0].rolled_back)
            receipt = tool.read(next(Path(directory).rglob('receipt.json')))
            self.assertEqual(receipt['status'], 'FAILED_OR_COMMIT_STATE_UNCERTAIN')

    def test_affected_row_count_failure_rolls_back(self):
        db = MemoryDatabase(self.state, event_count=0)
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(tool.GuardFailure):
            self.execute_double(db, Path(directory))
        self.assertEqual(db.state, self.state)

    def test_atomic_apply_and_rollback_preserve_identity(self):
        db = MemoryDatabase(self.state)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.execute_double(db, root)
            receipt = next(root.rglob('receipt.json'))
            self.assertEqual(tool.read(receipt)['status'], 'COMMITTED_VERIFIED')
            event = db.state['events'][0]
            self.assertEqual(event['id'], tool.EVENT_ID)
            self.assertEqual(event['created_at'], self.state['events'][0]['created_at'])
            self.assertEqual(event['entry_date'], '2025-05-20')
            commands = db.connections[0].commands
            lock = next(q for q in commands if q.startswith('LOCK TABLE'))
            self.assertIn('SHARE ROW EXCLUSIVE', lock)
            for name in tool.TABLES:
                self.assertIn('"'+name+'"', lock)
            self.assertIn("SET LOCAL lock_timeout='3s'", commands)
            self.execute_double(db, root, 'rollback', receipt)
            for key in ('filings', 'events'):
                db.state[key][0]['row_version'] = self.state[key][0]['row_version']
            self.assertEqual(db.state, self.state)

    def test_rollback_refuses_rebuild_and_dependency_drift(self):
        for change in ('id', 'price'):
            db = MemoryDatabase(self.state)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.execute_double(db, root)
                receipt = next(root.rglob('receipt.json'))
                if change == 'id':
                    db.state['events'][0]['id'] += 1
                else:
                    db.state['prices'][0]['adjusted_close'] = '1.00'
                before = copy.deepcopy(db.state)
                with self.assertRaises(tool.GuardFailure):
                    self.execute_double(db, root, 'rollback', receipt)
                self.assertEqual(db.state, before)

    def test_lost_commit_acknowledgment_is_not_reported_as_rollback(self):
        db = MemoryDatabase(self.state, commit_uncertain=True)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(tool.GuardFailure):
                self.execute_double(db, Path(directory))
            self.assertEqual(db.state['filings'][0]['acceptance_datetime'], tool.NEW)
            receipt = tool.read(next(Path(directory).rglob('receipt.json')))
            self.assertEqual(receipt['status'], 'FAILED_OR_COMMIT_STATE_UNCERTAIN')

    def test_offline_package_pin_and_stale_manifest(self):
        tool.load_package(tool.file_hash(tool.ROOT/'manifest.json'))
        with self.assertRaisesRegex(tool.GuardFailure, 'Explicit manifest pin'):
            tool.load_package('0'*64)
        with patch.object(tool, 'file_hash', return_value='changed'):
            with self.assertRaisesRegex(tool.GuardFailure, 'sidecar'):
                tool.load_package()
        real_hash = tool.file_hash
        with patch.object(tool, 'file_hash', side_effect=lambda p: 'changed' if str(p) == tool.CODE[1] else real_hash(p)):
            with self.assertRaisesRegex(tool.GuardFailure, 'Pinned file/code changed'):
                tool.load_package()

    def test_already_applied_execute_refuses_second_update(self):
        db = MemoryDatabase(self.state)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.execute_double(db, root)
            before = copy.deepcopy(db.state)
            with self.assertRaises(tool.GuardFailure):
                self.execute_double(db, root)
            self.assertEqual(db.state, before)
            self.assertFalse(any(q.startswith('UPDATE') for q in db.connections[-1].commands))

    def test_missing_explicit_pin_cannot_connect_for_writes(self):
        with patch.object(tool, 'load_package', return_value=(self.manifest, self.state)), patch.object(tool, 'get_connection') as connection:
            with self.assertRaises(tool.GuardFailure):
                tool.execute('apply', None)
            connection.assert_not_called()

    def test_default_is_read_only_and_offline_never_connects(self):
        db = MemoryDatabase(self.state)
        with patch.object(tool, 'load_package', return_value=(self.manifest, self.state)), patch.object(tool, 'get_connection', side_effect=db.connect), patch.object(tool, 'snapshot', return_value=self.state), patch('sys.argv', ['tool']):
            tool.main()
        self.assertTrue(db.connections[0].read_only)
        self.assertFalse(any(q.startswith(('UPDATE', 'LOCK')) for q in db.connections[0].commands))
        with patch.object(tool, 'load_package', return_value=(self.manifest, self.state)), patch.object(tool, 'get_connection') as connection, patch('sys.argv', ['tool', '--offline']):
            tool.main()
            connection.assert_not_called()


if __name__ == '__main__':
    unittest.main()
