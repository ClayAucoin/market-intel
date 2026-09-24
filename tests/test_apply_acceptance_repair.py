"""Offline pin, exclusion, rollback and protected-state tests for approved repair."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

with patch('dotenv.load_dotenv'):
    from src.backtesting import apply_acceptance_repair as repair


class RepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(gzip.decompress(repair.OUTPUT.read_bytes()))

    def filings(self, after=False):
        return [dict(id=r['filing_id'], company_id=r['company_id'], cik=r['cik'],
            accession_number=r['accession'], form=r['form'], filing_date=r['filing_date'],
            acceptance_datetime=r['proposed_timestamp'] if after and r['category']==repair.SAFE else r['stored_timestamp'])
            for r in self.manifest['rows']]

    def test_manifest_pin_failure_before_any_database_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'manifest.json.gz'
            path.write_bytes(b'changed')
            with patch.object(repair, 'OUTPUT', path), patch.object(repair, 'get_connection') as connect:
                with self.assertRaisesRegex(repair.GuardFailure, 'SHA-256'):
                    repair.load_pinned()
                connect.assert_not_called()

    def test_all_before_after_and_excluded_populations(self):
        before = repair.filing_check(self.manifest, self.filings(), after=False)
        after = repair.filing_check(self.manifest, self.filings(True), after=True)
        self.assertEqual(before['safe_old_remaining'], 29837)
        self.assertEqual(after['safe_corrected'], 29837)
        self.assertEqual(after['safe_old_remaining'], 0)
        self.assertEqual(after['verified_categories'], repair.EXPECTED)

    def test_timestamp_identity_date_missing_and_excluded_drift_abort(self):
        for category in repair.EXPECTED:
            filings = self.filings(True)
            i = next(i for i,r in enumerate(self.manifest['rows']) if r['category']==category)
            for key, value in (('acceptance_datetime', '2000-01-01T00:00:00Z'),
                               ('company_id', -1), ('accession_number', 'wrong'), ('cik', 'wrong'),
                               ('filing_date', '2000-01-01')):
                with self.subTest(category=category, field=key):
                    modified = list(filings)
                    modified[i] = dict(modified[i], **{key:value})
                    with self.assertRaises(repair.GuardFailure):
                        repair.filing_check(self.manifest, modified, after=True)
        with self.assertRaises(repair.GuardFailure):
            repair.filing_check(self.manifest, self.filings()[:-1], after=False)

    def test_second_application_fails_old_value_guard(self):
        with self.assertRaisesRegex(repair.GuardFailure, 'pre/postcondition'):
            repair.filing_check(self.manifest, self.filings(True), after=False)

    def test_update_only_safe_ids_and_guarded_sql(self):
        cursor = MagicMock()
        ids = [r['filing_id'] for r in self.manifest['rows'] if r['category']==repair.SAFE]
        cursor.fetchall.return_value = [dict(id=i) for i in ids]
        cursor.rowcount = len(ids)
        self.assertEqual(repair.update_safe(cursor, self.manifest), 29837)
        query, args = cursor.execute.call_args.args
        self.assertIn('SET acceptance_datetime=x.new_stamp', query)
        self.assertIn('f.acceptance_datetime=x.old_stamp', query)
        self.assertIn('f.company_id=x.company_id', query)
        self.assertIn('f.accession_number=x.accession', query)
        self.assertEqual(args[0], ids)
        self.assertTrue(set(args[0]).isdisjoint({r['filing_id'] for r in self.manifest['rows'] if r['category']!=repair.SAFE}))
        cursor.rowcount = 29836
        with self.assertRaises(repair.GuardFailure): repair.update_safe(cursor, self.manifest)
        cursor.rowcount = 29837
        cursor.fetchall.return_value[-1] = dict(id=-1)
        with self.assertRaises(repair.GuardFailure): repair.update_safe(cursor, self.manifest)

    def state(self):
        return dict(non_acceptance_filing_sha256='fixed', protected_tables={'financial_facts': 'fixed'},
            paper_accounts=[dict(cash=10000, prospective_cutover_at='fixed')],
            backtest_event_counts=dict(total=14824, historical_membership=14741),
            filing_columns=['fixed'], filings=dict(total=31097))

    def run_fixture(self, tmp, failure=None):
        before = self.state()
        locked = deepcopy(before)
        after = deepcopy(before)
        post = deepcopy(before)
        if failure == 'inside': after['paper_accounts'][0]['cash'] = 0
        if failure == 'locked': locked['protected_tables']['financial_facts'] = 'drift'
        if failure == 'post': post['backtest_event_counts']['total'] = 0
        connections = [MagicMock() for _ in range(3)]
        for conn in connections:
            conn.__enter__.return_value = conn
            conn.__exit__.return_value = False
            conn.cursor.return_value.__enter__.return_value.fetchone.return_value = dict(transaction_id=1)
        with patch.object(repair, 'OUTPUT', Path(tmp)/'manifest.json.gz'), \
             patch.object(repair, 'load_pinned', return_value=self.manifest), \
             patch.object(repair, 'get_connection', side_effect=connections), \
             patch.object(repair, 'configure'), \
             patch.object(repair, 'snapshot', side_effect=[(before, []), (locked, []), (after, []), (post, [])]), \
             patch.object(repair, 'save_backup', return_value=dict(verified=True)), \
             patch.object(repair, 'update_safe', return_value=29837) as update, \
             patch.object(repair, 'correction_statistics', return_value={}), patch('builtins.print'):
            if failure:
                with self.assertRaises(repair.GuardFailure): repair.run(True)
            else:
                repair.run(True)
        receipt = json.loads(next(Path(tmp).glob('execution_*/receipt.json')).read_text())
        return receipt, connections, update

    def test_transaction_failure_rolls_back_and_does_not_post_verify(self):
        for failure in ('locked', 'inside'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                receipt, connections, update = self.run_fixture(tmp, failure)
                self.assertEqual(receipt['execution_state'], 'ABORTED_NO_COMMIT')
                self.assertIs(connections[1].__exit__.call_args.args[0], repair.GuardFailure)
                connections[2].__enter__.assert_not_called()
                if failure == 'locked': update.assert_not_called()

    def test_success_commits_then_performs_read_only_postcheck(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt, connections, update = self.run_fixture(tmp)
            self.assertEqual(receipt['execution_state'], 'COMMITTED_AND_VERIFIED')
            self.assertIsNone(connections[1].__exit__.call_args.args[0])
            connections[2].__enter__.assert_called_once()
            update.assert_called_once()

    def test_post_commit_failure_never_claims_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt, connections, update = self.run_fixture(tmp, 'post')
            self.assertEqual(receipt['execution_state'], 'POST_COMMIT_VERIFICATION_FAILED')
            self.assertIsNone(connections[1].__exit__.call_args.args[0])
            update.assert_called_once()


if __name__ == '__main__': unittest.main()
