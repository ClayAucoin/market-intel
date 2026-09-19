"""Offline SEC freshness tests: every network, database and side-effect boundary is mocked."""
from contextlib import ExitStack, redirect_stdout
from datetime import date, datetime, timedelta
from io import StringIO
import sys
import types
import unittest
from unittest.mock import Mock, patch

import requests

notifier = types.ModuleType('src.notifications.notifier')
notifier.send_notification = Mock(side_effect=AssertionError('Notification forbidden'))
with patch('dotenv.load_dotenv'), patch.dict(sys.modules, {'src.notifications.notifier': notifier}):
    from src.sec import xbrl_client as xbrl, sec_submissions as submissions, sec_http as http
    from src.financials import financial_metrics as metrics, import_universe_financials as financials
    from src.sec import import_universe_filings as filings
    from src import run_daily_market_intel as daily

DAY = date(2026, 9, 18)
CIK = '0000000001'


def facts(cik=1):
    value = dict(start='2026-04-01', end='2026-06-30', val=100,
                 filed='2026-09-18', accn='new', form='10-Q', fy=2026, fp='Q2')
    return dict(cik=cik, facts={'us-gaap': {
        'Revenues': {'units': {'USD': [value]}},
        'NetIncomeLoss': {'units': {'USD': [value]}},
    }})


def columnar(*accessions):
    return dict(accessionNumber=list(accessions), filingDate=['2026-09-18']*len(accessions),
                acceptanceDateTime=['2026-09-18T08:00:00']*len(accessions))


def main_json(*accessions, shards=()):
    return dict(cik=1, filings=dict(recent=columnar(*accessions), files=list(shards)))


def shard(name='history.json', start='2026-09-01', end='2026-09-18'):
    return dict(name=name, filingFrom=start, filingTo=end)


def issuer():
    return dict(company_id=1, cik=CIK, company_name='Test issuer', earliest=DAY,
                latest=DAY, accessions=1, effective_from=None, effective_to=None)


class OfflineTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.output = self.stack.enter_context(redirect_stdout(StringIO()))
        self.stack.enter_context(patch('requests.sessions.Session.request',
                                      side_effect=AssertionError('Network forbidden')))
        self.stack.enter_context(patch('psycopg.connect', side_effect=AssertionError('Database forbidden')))

    def mock(self, module, name, **kwargs):
        return self.stack.enter_context(patch.object(module, name, **kwargs))


class CompanyFactsTests(OfflineTest):
    def setUp(self):
        super().setUp()
        self.cached = self.mock(xbrl, 'load_cached_company_facts', return_value=facts())
        self.download = self.mock(xbrl, 'get_sec_json', return_value=facts())
        self.save = self.mock(xbrl, 'save_cached_company_facts')

    def test_default_reads_cache_without_http(self):
        self.assertEqual(xbrl.get_company_facts(1), facts())
        self.download.assert_not_called()

    def test_default_cache_miss_downloads(self):
        self.cached.return_value = None
        self.assertEqual(xbrl.get_company_facts(1), facts())
        self.download.assert_called_once()

    def test_production_bypasses_cache_even_when_unchanged(self):
        result = xbrl.ProductionCompanyFacts()(1)
        self.assertEqual(result, facts())
        self.download.assert_called_once()
        self.save.assert_called_once()
        self.assertIn('content unchanged', self.output.getvalue())

    def test_production_reports_changed_content(self):
        self.cached.return_value = {'cik': 1, 'facts': {}}
        xbrl.ProductionCompanyFacts()(1)
        self.assertIn('content changed/new', self.output.getvalue())

    def test_once_per_cik_and_payload_identity(self):
        loader = xbrl.ProductionCompanyFacts()
        first = loader(1)
        self.assertIs(first, loader(CIK))
        self.download.return_value = facts(2)
        loader(2)
        self.assertEqual(self.download.call_count, 2)

    def test_failure_remembered_no_stale_fallback(self):
        self.download.side_effect = requests.ConnectionError('offline fixture')
        loader = xbrl.ProductionCompanyFacts()
        with self.assertRaises(requests.ConnectionError): loader(1)
        with self.assertRaises(RuntimeError): loader(CIK)
        self.download.assert_called_once()
        self.save.assert_not_called()

    def test_malformed_or_wrong_issuer_fails(self):
        for data in ({}, {'cik': 2, 'facts': {}}, {'cik': 1, 'facts': []}):
            with self.subTest(data=data):
                self.download.return_value = data
                with self.assertRaises(ValueError): xbrl.ProductionCompanyFacts()(1)

    def configure_import(self):
        self.mock(financials, 'get_companies', return_value=[{'ticker':'AAA'}, {'ticker':'BBB'}])
        self.mock(metrics, 'get_company_by_ticker', return_value={'id':1, 'cik':CIK, 'company_name':'Test'})
        self.mock(metrics, 'get_issuer_history_by_ticker', return_value=[issuer()])
        self.mock(metrics, 'get_company', return_value=None)
        return self.mock(financials, 'save_financial_history', return_value=1)

    def test_metrics_and_tickers_share_fresh_payload(self):
        save = self.configure_import()
        parse = self.mock(metrics, 'build_multi_concept_quarterly_history',
                          wraps=metrics.build_multi_concept_quarterly_history)
        summaries = financials.import_universe('expanded_500', production_refresh=True)
        self.download.assert_called_once()
        self.assertEqual(save.call_count, 4)  # revenue + net income, two securities
        self.assertTrue(all(s['errors'] == 0 for s in summaries))
        self.assertTrue(all(c.args[0] is self.download.return_value for c in parse.call_args_list))

    def test_http_failure_makes_production_import_fail(self):
        save = self.configure_import()
        self.download.side_effect = requests.HTTPError('fixture failure')
        with self.assertRaisesRegex(RuntimeError, 'Production financial SEC refresh failed'):
            financials.import_universe('expanded_500', production_refresh=True)
        self.download.assert_called_once()
        save.assert_not_called()

    def test_import_database_failure_propagates_in_production(self):
        save = self.configure_import()
        save.side_effect = RuntimeError('fixture write failure')
        with self.assertRaisesRegex(RuntimeError, 'Production financial SEC refresh failed'):
            financials.import_universe('expanded_500', production_refresh=True)

    def test_manual_import_retains_cached_and_best_effort_behavior(self):
        save = self.configure_import()
        save.side_effect = RuntimeError('fixture write failure')
        result = financials.import_universe('expanded_500')
        self.assertGreater(result[0]['errors'], 0)
        self.download.assert_not_called()


class SubmissionTests(OfflineTest):
    def setUp(self):
        super().setUp()
        self.cached = self.mock(submissions, 'load_json', return_value=main_json('new'))
        self.download = self.mock(submissions, 'get_sec_json', return_value=main_json('new'))
        self.save = self.mock(submissions, 'save_json')

    def test_default_main_cache_hit(self):
        self.assertEqual(submissions.get_company_submissions(1), main_json('new'))
        self.download.assert_not_called()

    def test_default_history_cache_hit(self):
        self.cached.return_value = columnar('old')
        self.assertEqual(submissions.get_historical_submissions('history.json'), columnar('old'))
        self.download.assert_not_called()

    def test_production_main_refresh_once_and_unchanged_success(self):
        loader = submissions.ProductionSubmissions()
        for cik in (1, CIK):
            self.assertEqual(loader(cik, {'new':{DAY}})[0]['accessionNumber'], 'new')
        self.download.assert_called_once()
        self.assertIn('content unchanged', self.output.getvalue())

    def test_new_main_reveals_new_shard(self):
        self.cached.return_value = None
        self.download.side_effect = [main_json(shards=[shard('new-file.json')]), columnar('new')]
        result = submissions.ProductionSubmissions()(1, {'new':{DAY}})
        self.assertEqual(result[0]['accessionNumber'], 'new')
        self.assertEqual(self.download.call_count, 2)
        self.assertTrue(self.download.call_args_list[1].args[0].endswith('/new-file.json'))

    def test_existing_sufficient_shard_not_refreshed(self):
        self.download.return_value = main_json(shards=[shard()])
        self.cached.return_value = columnar('new')
        result = submissions.ProductionSubmissions()(1, {'new':{DAY}})
        self.assertEqual(result[0]['accessionNumber'], 'new')
        self.download.assert_called_once()

    def test_only_matching_cached_shard_refreshed_for_missing_accession(self):
        old = shard('unrelated.json', '2020-01-01', '2020-12-31')
        self.cached.return_value = columnar('other')
        self.download.side_effect = [main_json(shards=[old,shard()]), columnar('new')]
        result = submissions.ProductionSubmissions()(1, {'new':{DAY}})
        self.assertIn('new', [r['accessionNumber'] for r in result])
        self.assertEqual(self.download.call_count, 2)
        self.assertTrue(self.download.call_args_list[1].args[0].endswith('/history.json'))
        self.assertFalse(any('unrelated' in str(c) for c in self.cached.call_args_list))

    def test_newly_downloaded_shard_is_not_downloaded_twice(self):
        self.cached.return_value = None
        self.download.side_effect = [main_json(shards=[shard()]), columnar('other')]
        with self.assertRaisesRegex(ValueError, 'unresolved accessions new'):
            submissions.ProductionSubmissions()(1, {'new':{DAY}})
        self.assertEqual(self.download.call_count, 2)

    def test_missing_accession_fails_after_bounded_recovery(self):
        self.cached.return_value = columnar('other')
        self.download.side_effect = [main_json(shards=[shard()]), columnar('other')]
        with self.assertRaisesRegex(ValueError, 'Incomplete production submissions'):
            submissions.ProductionSubmissions()(1, {'new':{DAY}})
        self.assertEqual(self.download.call_count, 2)

    def test_main_http_failure_remembered(self):
        self.download.side_effect = requests.Timeout('fixture')
        loader = submissions.ProductionSubmissions()
        with self.assertRaises(requests.Timeout): loader(1, {'new':{DAY}})
        with self.assertRaises(RuntimeError): loader(1, {'new':{DAY}})
        self.download.assert_called_once()
        self.save.assert_not_called()

    def configure_import(self):
        self.mock(filings, 'get_target_issuers', return_value=[issuer()])
        self.mock(filings, 'get_target_accessions', return_value={'new':{DAY}})
        return self.mock(filings, 'save_filing', return_value=True)

    def test_production_filing_import_success_without_new_content(self):
        save = self.configure_import()
        result = filings.import_universe('expanded_500', production_refresh=True)
        self.assertEqual(result[0]['matched'], 1)
        self.download.assert_called_once()
        save.assert_called_once()

    def test_production_unresolved_accession_fails_importer(self):
        save = self.configure_import()
        self.download.return_value = main_json()
        with self.assertRaisesRegex(RuntimeError, 'Production filing SEC refresh failed'):
            filings.import_universe('expanded_500', production_refresh=True)
        save.assert_not_called()

    def test_production_http_failure_fails_importer(self):
        self.configure_import()
        self.download.side_effect = requests.Timeout('fixture')
        with self.assertRaisesRegex(RuntimeError, 'Production filing SEC refresh failed'):
            filings.import_universe('expanded_500', production_refresh=True)

    def test_production_missing_acceptance_fails_importer(self):
        save = self.configure_import()
        data = main_json('new')
        data['filings']['recent']['acceptanceDateTime'] = [None]
        self.download.return_value = data
        with self.assertRaisesRegex(RuntimeError, 'Production filing SEC refresh failed'):
            filings.import_universe('expanded_500', production_refresh=True)
        save.assert_not_called()

    def test_manual_filings_remain_best_effort(self):
        self.configure_import()
        reader = self.mock(filings, 'get_submission_records', side_effect=ValueError('fixture'))
        self.assertEqual(filings.import_universe('expanded_500')[0]['missing'], 1)
        self.assertFalse(reader.call_args.kwargs['refresh'])
        self.download.assert_not_called()

    def test_legacy_explicit_refresh_still_refreshes_history(self):
        main = self.mock(submissions, 'get_company_submissions', return_value=main_json(shards=[shard()]))
        history = self.mock(submissions, 'get_historical_submissions', return_value=columnar('old'))
        submissions.get_submission_records(1, refresh=True)
        main.assert_called_once_with(1, refresh=True)
        history.assert_called_once_with('history.json', refresh=True)

    def test_history_download_failure_fails_production(self):
        self.configure_import()
        self.cached.return_value = None
        self.download.side_effect = [main_json(shards=[shard()]), requests.Timeout('fixture')]
        with self.assertRaisesRegex(RuntimeError, 'Production filing SEC refresh failed'):
            filings.import_universe('expanded_500', production_refresh=True)

    def test_malformed_main_cannot_report_success(self):
        self.configure_import()
        self.download.return_value = {'cik':1, 'filings':{}}
        with self.assertRaisesRegex(RuntimeError, 'Production filing SEC refresh failed'):
            filings.import_universe('expanded_500', production_refresh=True)

    def test_default_records_use_cached_main_and_history(self):
        self.cached.side_effect = [main_json(shards=[shard()]), columnar('old')]
        self.assertEqual(submissions.get_submission_records(1)[0]['accessionNumber'], 'old')
        self.download.assert_not_called()

    def test_late_recovered_accession_still_rejected_by_paper_rules(self):
        from src.paper_trading.paper_execution import EASTERN, freshness_reason
        data = main_json('old')
        data['filings']['recent']['filingDate'] = ['2026-09-17']
        data['filings']['recent']['acceptanceDateTime'] = ['2026-09-17T08:00:00']
        self.download.return_value = data
        recovered = submissions.ProductionSubmissions()(1, {'old':{DAY-timedelta(days=1)}})[0]
        now = datetime(2026,9,18,18,tzinfo=EASTERN)
        source = dict(accession_number='old', company_id=1, filing_company_id=1,
                      filed_date=DAY-timedelta(days=1), filing_date=DAY-timedelta(days=1),
                      acceptance_datetime=filings.parse_acceptance_datetime(recovered['acceptanceDateTime']))
        row = dict(entry_date=DAY-timedelta(days=1), period_end=date(2026,6,30))
        self.assertIsNotNone(freshness_reason(row,[source],now-timedelta(days=5),now,
                                              [DAY-timedelta(days=1),DAY]))
        # Even a delayed/rebuilt event labelled today cannot pass the first-session check.
        row['entry_date'] = DAY
        self.assertIsNotNone(freshness_reason(row,[source],now-timedelta(days=5),now,
                                              [DAY-timedelta(days=1),DAY]))


class HttpTests(OfflineTest):
    def setUp(self):
        super().setUp()
        self.mock(http, '_last_request_at', new=None)
        self.sleep = self.mock(http.time, 'sleep')
        self.mock(http.time, 'monotonic', return_value=100)
        self.get = self.mock(http.requests, 'get')

    def response(self, status=200, retry_after=None):
        response = Mock(status_code=status, headers={} if retry_after is None else {'Retry-After':retry_after})
        if status >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(response=response)
        response.json.return_value = {'ok': True}
        return response

    def test_pacing_and_user_agent_preserved(self):
        self.get.return_value = self.response()
        http.get_sec_json('https://example.invalid/fixture')
        http.get_sec_json('https://example.invalid/fixture')
        self.sleep.assert_called_with(http.MIN_REQUEST_INTERVAL)
        self.assertIs(self.get.call_args.kwargs['headers'], http.SEC_HEADERS)

    def test_429_retries(self):
        self.get.side_effect = [self.response(429),self.response()]
        self.assertEqual(http.get_sec_json('fixture'), {'ok':True})
        self.assertEqual(self.get.call_count, 2)
        self.assertIn(((1.0,), {}), self.sleep.call_args_list)

    def test_5xx_retries(self):
        self.get.side_effect = [self.response(503),self.response()]
        http.get_sec_json('fixture')
        self.assertEqual(self.get.call_count, 2)

    def test_network_errors_retry(self):
        for error in (requests.Timeout,requests.ConnectionError):
            self.get.reset_mock(side_effect=True)
            self.get.side_effect = [error('fixture'),self.response()]
            http.get_sec_json('fixture')
            self.assertEqual(self.get.call_count,2)

    def test_attempt_bound(self):
        self.get.side_effect = requests.Timeout('fixture')
        with self.assertRaises(requests.Timeout): http.get_sec_json('fixture')
        self.assertEqual(self.get.call_count,http.MAX_ATTEMPTS)

    def test_permanent_4xx_not_retried(self):
        for status in (400,401,403,404):
            with self.subTest(status=status):
                self.get.reset_mock()
                self.get.return_value = self.response(status)
                with self.assertRaises(requests.HTTPError): http.get_sec_json('fixture')
                self.get.assert_called_once()

    def test_retry_after_respected(self):
        self.get.side_effect = [self.response(429,'5'), self.response()]
        http.get_sec_json('fixture')
        self.assertIn(((5.0,), {}), self.sleep.call_args_list)

    def test_long_retry_after_fails_instead_of_retrying_early(self):
        self.get.return_value = self.response(429,'120')
        with self.assertRaises(requests.HTTPError): http.get_sec_json('fixture')
        self.get.assert_called_once()
        self.sleep.assert_not_called()

    def test_malformed_json_not_retried(self):
        self.get.return_value = self.response()
        self.get.return_value.json.side_effect = ValueError('invalid JSON')
        with self.assertRaises(ValueError): http.get_sec_json('fixture')
        self.get.assert_called_once()

    def test_transient_http_attempts_bounded(self):
        for status in (429,503):
            with self.subTest(status=status):
                self.get.reset_mock()
                self.get.return_value = self.response(status)
                with self.assertRaises(requests.HTTPError): http.get_sec_json('fixture')
                self.assertEqual(self.get.call_count,http.MAX_ATTEMPTS)


class OrchestratorTests(OfflineTest):
    def configure(self, codes):
        calls = self.mock(daily.subprocess, 'run', side_effect=[Mock(returncode=c) for c in codes])
        self.mock(daily, 'start_daily_log', return_value={'path':'offline-fixture'})
        self.mock(daily, 'stop_daily_log')
        self.prices = self.mock(daily, 'refresh_prices')
        self.rebuild = self.mock(daily, 'rebuild_events')
        self.paper = self.mock(daily, 'run_paper_system')
        self.success = self.mock(daily, 'send_success_notification')
        self.failure = self.mock(daily, 'send_failure_notification')
        return calls

    def test_financial_failure_aborts_and_no_success(self):
        calls = self.configure([1])
        with self.assertRaisesRegex(RuntimeError,'import_universe_financials failed'): daily.main()
        calls.assert_called_once()
        self.paper.assert_not_called(); self.prices.assert_not_called(); self.rebuild.assert_not_called()
        self.success.assert_not_called(); self.failure.assert_called_once()

    def test_submissions_failure_aborts_and_no_success(self):
        calls = self.configure([0,1])
        with self.assertRaisesRegex(RuntimeError,'import_universe_filings failed'): daily.main()
        self.assertEqual(calls.call_count,2)
        self.paper.assert_not_called(); self.prices.assert_not_called(); self.rebuild.assert_not_called()
        self.success.assert_not_called(); self.failure.assert_called_once()

    def test_successful_refreshes_continue_in_order_with_production_flags(self):
        calls = self.configure([0,0])
        ordered = Mock()
        for name,mock in [('sec',calls),('prices',self.prices),('events',self.rebuild),('paper',self.paper),('success',self.success)]:
            ordered.attach_mock(mock,name)
        daily.main()
        self.assertEqual([c[0] for c in ordered.mock_calls], ['sec','sec','prices','events','paper','success'])
        for call in calls.call_args_list:
            self.assertEqual(call.args[0][-2:], ['expanded_500','--production-refresh'])
        self.failure.assert_not_called()

    def test_cli_flags_and_failure_propagation(self):
        for module in (financials,filings):
            with self.subTest(module=module.__name__), \
                 patch.object(module, 'import_universe', side_effect=RuntimeError('production failure')) as run, \
                 patch.object(sys, 'argv', ['importer','expanded_500','--production-refresh']):
                with self.assertRaises(RuntimeError): module.main()
                run.assert_called_once_with('expanded_500',production_refresh=True)

    def test_cli_defaults_remain_cache_first(self):
        for module in (financials,filings):
            with self.subTest(module=module.__name__), \
                 patch.object(module, 'import_universe') as run, \
                 patch.object(sys,'argv',['importer','expanded_500']):
                module.main()
                run.assert_called_once_with('expanded_500',production_refresh=False)


if __name__ == '__main__':
    unittest.main()
