"""Offline SEC freshness tests: every network, database and side-effect boundary is mocked."""
from contextlib import ExitStack, redirect_stdout
from datetime import date, datetime, timedelta
from io import StringIO
import json
from pathlib import Path
import tempfile
import sys
import types
import unittest
from unittest.mock import Mock, patch

import requests

notifier = types.ModuleType('src.notifications.notifier')
notifier.send_notification = Mock(side_effect=AssertionError('Notification forbidden'))
previous_notifier = sys.modules.get('src.notifications.notifier')
sys.modules['src.notifications.notifier'] = notifier
with patch('dotenv.load_dotenv'):
    from src.sec import xbrl_client as xbrl, sec_submissions as submissions, sec_http as http
    from src.financials import financial_metrics as metrics, import_universe_financials as financials
    from src.sec import import_universe_filings as filings
    from src import run_daily_market_intel as daily
    from src.sec import production_report as reporting

if previous_notifier is None:
    sys.modules.pop('src.notifications.notifier', None)
else:
    sys.modules['src.notifications.notifier'] = previous_notifier

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
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.stack.enter_context(patch.object(reporting, "REPORT_DIR", Path(directory)))
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
        self.mock(filings, 'get_production_issuers', return_value=[issuer()])
        self.mock(filings, 'get_target_accessions', return_value={'new':{DAY}})
        self.mock(filings, 'get_production_requirements', return_value=({'new':{DAY}}, {}, []))
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
        self.mock(http, '_blocked_until', new=0.0)
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
        with self.assertRaisesRegex(RuntimeError,'run_production_refresh failed'): daily.main()
        calls.assert_called_once()
        self.paper.assert_not_called(); self.prices.assert_not_called(); self.rebuild.assert_not_called()
        self.success.assert_not_called(); self.failure.assert_called_once()

    def test_submissions_failure_aborts_and_no_success(self):
        calls = self.configure([1])
        with self.assertRaisesRegex(RuntimeError,'run_production_refresh failed'): daily.main()
        self.assertEqual(calls.call_count,1)
        self.paper.assert_not_called(); self.prices.assert_not_called(); self.rebuild.assert_not_called()
        self.success.assert_not_called(); self.failure.assert_called_once()

    def test_successful_refreshes_continue_in_order_with_production_flags(self):
        calls = self.configure([0,0])
        ordered = Mock()
        for name,mock in [('sec',calls),('prices',self.prices),('events',self.rebuild),('paper',self.paper),('success',self.success)]:
            ordered.attach_mock(mock,name)
        daily.main()
        self.assertEqual([c[0] for c in ordered.mock_calls], ['sec','prices','events','paper','success'])
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




class CacheReplacementTests(OfflineTest):
    def setUp(self):
        super().setUp()
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.mock(xbrl, 'CACHE_DIR', new=self.directory / 'facts')
        self.mock(submissions, 'CACHE_DIR', new=self.directory / 'submissions')

    def resources(self):
        return [
            (xbrl, xbrl.get_cache_path(1), facts(), lambda: xbrl.get_company_facts(1, refresh=True)),
            (submissions, submissions.get_main_cache_path(1), main_json('new'),
             lambda: submissions.get_company_submissions(1, refresh=True)),
            (submissions, submissions.get_history_cache_path('history.json'), columnar('new'),
             lambda: submissions.get_historical_submissions('history.json', refresh=True)),
        ]

    def test_successful_replacement_real_cache_read_and_write(self):
        from src.sec.json_cache import atomic_json
        for module, path, valid, refresh in self.resources():
            with self.subTest(path=path), patch.object(module, 'get_sec_json', return_value=valid):
                atomic_json(path, {'previous': True})
                refresh()
                self.assertEqual(json.loads(path.read_text()), valid)
                self.assertEqual(list(path.parent.glob('*.tmp')), [])
        self.assertEqual(xbrl.get_company_facts(1), facts())
        self.assertEqual(submissions.get_company_submissions(1), main_json('new'))
        self.assertEqual(submissions.get_historical_submissions('history.json'), columnar('new'))

    def test_invalid_resources_and_invalid_json_preserve_cache(self):
        from src.sec.json_cache import atomic_json
        for module, path, valid, refresh in self.resources():
            atomic_json(path, valid)
            previous = path.read_bytes()
            for invalid in ({}, [], {'cik': 2, 'facts': {}},
                            {'cik': 1, 'facts': {'us-gaap': []}},
                            {'accessionNumber': ['new'], 'filingDate': []}):
                with self.subTest(path=path, invalid=invalid), \
                     patch.object(module, 'get_sec_json', return_value=invalid):
                    with self.assertRaises(ValueError): refresh()
                    self.assertEqual(path.read_bytes(), previous)
            with patch.object(module, 'get_sec_json', side_effect=ValueError('Invalid JSON')):
                with self.assertRaises(ValueError): refresh()
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual(list(path.parent.glob('*.tmp')), [])

    def test_malformed_submissions_dates_preserve_cache(self):
        from src.sec.json_cache import atomic_json
        for payload, refresh, path in (
                (main_json('new'), lambda: submissions.get_company_submissions(1, refresh=True),
                 submissions.get_main_cache_path(1)),
                (columnar('new'), lambda: submissions.get_historical_submissions('history.json', refresh=True),
                 submissions.get_history_cache_path('history.json'))):
            atomic_json(path, payload)
            previous = path.read_bytes()
            columns = payload['filings']['recent'] if 'filings' in payload else payload
            columns['filingDate'] = ['not a date']
            with patch.object(submissions, 'get_sec_json', return_value=payload):
                with self.assertRaises(ValueError): refresh()
            self.assertEqual(path.read_bytes(), previous)

    def test_partial_serialization_and_replace_failure_preserve_old_bytes(self):
        from src.sec import json_cache
        for module, path, valid, refresh in self.resources():
            json_cache.atomic_json(path, valid)
            previous = path.read_bytes()
            def partial(data, handle, **kwargs):
                handle.write('{"partial":')
                raise OSError('simulated full disk')
            for boundary, error in [('json.dump', partial), ('os.fsync', OSError('fsync failed')),
                                    ('os.replace', OSError('replace failed'))]:
                with self.subTest(path=path, boundary=boundary), \
                     patch.object(module, 'get_sec_json', return_value=valid), \
                     patch('src.sec.json_cache.' + boundary, side_effect=error):
                    with self.assertRaises(OSError): refresh()
                    self.assertEqual(path.read_bytes(), previous)
                    self.assertEqual(list(path.parent.glob('*.tmp')), [])


class RequirementTests(OfflineTest):
    def setUp(self):
        super().setUp()
        from src.sec import production_requirements
        self.requirements = production_requirements
        self.now = datetime(2026, 9, 18, 18, tzinfo=filings.EASTERN)
        self.cutover = self.now - timedelta(days=30)

    def row(self, **changes):
        return dict(dict(accession_number='new', company_id=1, metric='revenue',
                         filed_date=DAY, period_end=date(2026, 6, 30), filing_company_id=None,
                         filing_date=None, acceptance_datetime=None), **changes)

    def select(self, rows, sessions=None):
        return self.requirements.select_requirements(rows, self.now, self.cutover, sessions)

    def test_ancient_unresolved_is_warning_current_is_required(self):
        old = self.row(accession_number='ancient', filed_date=date(2005, 8, 1),
                       period_end=date(2005, 6, 30))
        required, stored, warnings = self.select([old, self.row()])
        self.assertEqual(required, {'new': {DAY}})
        self.assertEqual(stored, {})
        self.assertEqual(warnings, ['ancient'])

    def test_old_unresolved_does_not_block_real_import_current_does(self):
        old = self.row(accession_number='ancient', filed_date=date(2005, 8, 1),
                       period_end=date(2005, 6, 30))
        self.mock(filings, 'get_production_issuers', return_value=[issuer()])
        requirements = self.mock(filings, 'get_production_requirements', return_value=self.select([old]))
        self.mock(submissions, 'get_sec_json', return_value=main_json())
        self.mock(submissions, 'load_json', return_value=None)
        self.mock(submissions, 'save_json')
        save = self.mock(filings, 'save_filing')
        self.assertEqual(filings.import_universe('expanded_500', production_refresh=True)[0]['missing'], 0)
        save.assert_not_called()
        requirements.return_value = self.select([old, self.row()])
        with self.assertRaisesRegex(RuntimeError, 'Production filing SEC refresh failed'):
            filings.import_universe('expanded_500', production_refresh=True)

    def test_valid_stored_metadata_never_rediscovers_history(self):
        row = self.row(filing_company_id=1, filing_date=DAY,
                       acceptance_datetime=self.now.replace(hour=8))
        self.mock(filings, 'get_production_requirements', return_value=self.select([row]))
        self.mock(submissions, 'get_sec_json', return_value=main_json(shards=[shard()]))
        self.mock(submissions, 'load_json', return_value=None)
        self.mock(submissions, 'save_json')
        history = self.mock(submissions, 'get_historical_submissions')
        save = self.mock(filings, 'save_filing')
        result = filings.import_issuer_filings(issuer(), 'expanded_500', submissions.ProductionSubmissions())
        self.assertEqual(result['matched'], 1)
        save.assert_not_called()
        history.assert_not_called()

    def test_unknown_source_date_or_period_fails_closed(self):
        for fields in ({'filed_date': None}, {'period_end': None}, {'accession_number': None}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.select([self.row(**fields)])

    def test_conflicting_identity_cannot_be_dismissed_as_old(self):
        row = self.row(filed_date=date(2005, 8, 1), period_end=date(2005, 6, 30),
                       filing_company_id=2, filing_date=DAY,
                       acceptance_datetime=self.now.replace(hour=8))
        self.assertIn('new', self.select([row])[0])

    def test_nonrevenue_and_stale_period_not_current_required(self):
        self.assertEqual(self.select([self.row(metric='gross_profit')])[0], {})
        self.assertEqual(self.select([self.row(period_end=date(2005, 6, 30))])[0], {})

    def test_cutover_future_acceptance_and_entry_window_preserved(self):
        for accepted in (self.cutover-timedelta(seconds=1), self.now+timedelta(seconds=1),
                         self.now-timedelta(days=10)):
            with self.subTest(accepted=accepted):
                row = self.row(filing_company_id=1, filing_date=DAY, acceptance_datetime=accepted)
                self.assertEqual(self.select([row])[0], {})

    def test_prior_session_excludes_late_recovery_without_guessing_calendar(self):
        row = self.row(filed_date=DAY-timedelta(days=3))
        self.assertIn('new', self.select([row], sessions=None)[0])
        self.assertEqual(self.select([row], sessions=[DAY-timedelta(days=1)])[0], {})

    def test_previous_day_missing_acceptance_can_be_current(self):
        self.assertIn('new', self.select([self.row(filed_date=DAY-timedelta(days=1))])[0])


class AdditionalImporterTests(OfflineTest):
    configure_import = CompanyFactsTests.configure_import

    def setUp(self):
        super().setUp()
        self.cached = self.mock(xbrl, "load_cached_company_facts", return_value=facts())
        self.download = self.mock(xbrl, "get_sec_json", return_value=facts())
        self.save = self.mock(xbrl, "save_cached_company_facts")

    def test_all_metrics_legitimately_absent_is_successful_refresh(self):
        save = self.configure_import()
        self.download.return_value = {'cik': 1, 'facts': {}}
        results = financials.import_universe('expanded_500', production_refresh=True)
        self.assertEqual([r['errors'] for r in results], [0, 0])
        self.assertEqual([r['skipped'] for r in results], [6, 6])
        self.download.assert_called_once()
        save.assert_not_called()

    def test_repeated_invocation_refreshes_again(self):
        self.configure_import()
        for _ in range(2):
            financials.import_universe('expanded_500', production_refresh=True)
        self.assertEqual(self.download.call_count, 2)

    def test_submissions_production_issuer_call_graph_deduplicates_securities(self):
        self.configure_import()
        self.mock(filings, 'get_production_requirements', return_value=({}, {}, []))
        self.mock(submissions, 'load_json', return_value=None)
        self.mock(submissions, 'save_json')
        download = self.mock(submissions, 'get_sec_json', return_value=main_json())
        self.stack.enter_context(patch('src.universe.company_universe.get_companies',
                                      return_value=[{'ticker': 'AAA'}, {'ticker': 'BBB'}]))
        for _ in range(2):
            result = filings.import_universe('expanded_500', production_refresh=True)
            self.assertEqual(len(result), 1)
        self.assertEqual(download.call_count, 2)


class AdditionalHttpTests(OfflineTest):
    response = HttpTests.response

    def setUp(self):
        super().setUp()
        self.mock(http, "_last_request_at", new=None)
        self.mock(http, "_blocked_until", new=0.0)
        self.sleep = self.mock(http.time, "sleep")
        self.mock(http.time, "monotonic", return_value=100)
        self.get = self.mock(http.requests, "get")

    def test_different_resource_cannot_bypass_long_shared_cooldown(self):
        self.get.return_value = self.response(429, '120')
        with self.assertRaises(requests.HTTPError): http.get_sec_json('resource-A')
        with self.assertRaisesRegex(requests.HTTPError, 'shared cooldown'):
            http.get_sec_json('resource-B')
        self.get.assert_called_once()
        self.sleep.assert_not_called()
        self.mock(http.time, 'monotonic', return_value=221)
        self.get.return_value = self.response()
        http.get_sec_json('resource-B')
        self.assertEqual(self.get.call_count, 2)


class ReportingTests(OfflineTest):
    def test_running_then_pass_with_aggregate_counters_no_payloads(self):
        with reporting.RunReport('fixture') as run:
            initial = json.loads(run.path.read_text())
            self.assertEqual(initial['status'], 'RUNNING')
            self.assertEqual(initial['freshness'], 'FAIL')
            reporting.resource('company_facts', 1, 'attempted')
            reporting.resource('company_facts', CIK, 'attempted')
            reporting.resource('company_facts', 1, 'succeeded')
            reporting.add('http_requests', 3)
            reporting.add('retries', 2)
        data = json.loads(run.path.read_text())
        self.assertEqual((data['status'], data['freshness']), ('PASS', 'PASS'))
        self.assertEqual(data['company_facts']['attempted'], 1)
        self.assertEqual(data['counters']['http_requests'], 3)
        self.assertEqual(data['counters']['retries'], 2)
        self.assertIsNotNone(data['end_timestamp'])
        self.assertNotIn('facts', data)
        self.assertNotIn('payloads', data)

    def test_running_then_fail_and_exception_not_swallowed(self):
        with self.assertRaises(RuntimeError):
            with reporting.RunReport('fixture') as run:
                raise RuntimeError('sensitive sentinel should not be copied')
        data = json.loads(run.path.read_text())
        self.assertEqual((data['status'], data['freshness']), ('FAIL', 'FAIL'))
        self.assertNotIn('sensitive sentinel', run.path.read_text())

    def test_interruption_cannot_resemble_pass(self):
        run = reporting.RunReport('fixture')
        run.__enter__()
        # Simulate process loss before __exit__, without leaving context in this test.
        reporting._active.reset(run.token)
        data = json.loads(run.path.read_text())
        self.assertEqual(data['status'], 'RUNNING')
        self.assertEqual(data['freshness'], 'FAIL')
        self.assertIsNone(data['end_timestamp'])

    def test_final_report_write_failure_leaves_running_and_propagates(self):
        with self.assertRaises(OSError):
            with reporting.RunReport('fixture') as run:
                self.mock(reporting, 'atomic_json', side_effect=OSError('disk fixture'))
        self.assertEqual(json.loads(run.path.read_text())['status'], 'RUNNING')
        self.assertNotIn('SEC PASS', self.output.getvalue())
        self.assertIsNone(reporting._active.get())

    def test_initial_report_failure_prevents_imports(self):
        from src.sec import run_production_refresh as runner
        imports = self.mock(runner, 'import_financials')
        self.mock(reporting, 'atomic_json', side_effect=OSError('disk fixture'))
        with self.assertRaises(OSError): runner.refresh('fixture')
        imports.assert_not_called()

    def test_combined_runner_one_report_and_stop_after_financial_failure(self):
        from src.sec import run_production_refresh as runner
        financial = self.mock(runner, 'import_financials', side_effect=RuntimeError('fixture'))
        filing = self.mock(runner, 'import_filings')
        with self.assertRaises(RuntimeError): runner.refresh('fixture')
        financial.assert_called_once_with('fixture', production_refresh=True)
        filing.assert_not_called()
        paths = list(reporting.REPORT_DIR.glob('*.json'))
        self.assertEqual(len(paths), 1)
        self.assertEqual(json.loads(paths[0].read_text())['status'], 'FAIL')

    def test_repeated_runs_have_isolated_counts_and_ids(self):
        with reporting.RunReport('fixture') as first:
            reporting.add('http_requests', 9)
        with reporting.RunReport('fixture') as second:
            pass
        self.assertNotEqual(first.path, second.path)
        self.assertEqual(second.data['counters']['http_requests'], 0)

    def test_actual_cli_failure_exit_status_is_nonzero_offline(self):
        import subprocess
        code = '''
import sys
from pathlib import Path
from unittest.mock import patch
with patch('dotenv.load_dotenv'), patch('requests.sessions.Session.request', side_effect=AssertionError('network forbidden')), patch('psycopg.connect', side_effect=AssertionError('DB forbidden')):
    from src.sec import run_production_refresh as runner, production_report as reporting
    reporting.REPORT_DIR = Path(sys.argv[1])
    sys.argv = ['refresh', 'fixture', '--production-refresh']
    with patch.object(runner, 'import_financials', side_effect=RuntimeError('offline fixture')):
        runner.main()
'''
        completed = subprocess.run([sys.executable, '-c', code, str(reporting.REPORT_DIR)],
                                   capture_output=True, text=True, timeout=10)
        self.assertNotEqual(completed.returncode, 0)
        reports = list(reporting.REPORT_DIR.glob('*.json'))
        self.assertEqual(len(reports), 1)
        self.assertEqual(json.loads(reports[0].read_text())['status'], 'FAIL')


class FinalCoverageTests(OfflineTest):
    def test_combined_real_import_call_graph_and_http_report(self):
        from src.sec import run_production_refresh as runner
        directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.mock(xbrl, 'CACHE_DIR', new=directory / 'facts')
        self.mock(submissions, 'CACHE_DIR', new=directory / 'submissions')
        self.mock(http, '_last_request_at', new=None)
        self.mock(http, '_blocked_until', new=0.0)
        self.mock(http.time, 'sleep')
        self.mock(financials, 'get_companies', return_value=[{'ticker':'AAA'}, {'ticker':'BBB'}])
        self.stack.enter_context(patch('src.universe.company_universe.get_companies',
                                      return_value=[{'ticker':'AAA'}, {'ticker':'BBB'}]))
        self.mock(metrics, 'get_company_by_ticker', return_value={'id':1, 'cik':CIK, 'company_name':'Test'})
        self.mock(metrics, 'get_issuer_history_by_ticker', return_value=[issuer()])
        self.mock(metrics, 'get_company', return_value=None)
        self.mock(financials, 'save_financial_history', return_value=1)
        self.mock(filings, 'get_production_requirements', return_value=({}, {}, []))
        def respond(url, **kwargs):
            return Mock(status_code=200, headers={}, json=Mock(
                return_value=facts() if 'companyfacts' in url else main_json()))
        get = self.mock(http.requests, 'get', side_effect=respond)
        runner.refresh('fixture')
        runner.refresh('fixture')
        self.assertEqual(get.call_count, 4)
        reports = [json.loads(p.read_text()) for p in reporting.REPORT_DIR.glob('*.json')]
        self.assertEqual(len(reports), 2)
        for report in reports:
            self.assertEqual(report['status'], 'PASS')
            self.assertEqual(report['counters']['http_requests'], 2)
            self.assertEqual(report['counters']['successful_requests'], 2)
            self.assertEqual(report['company_facts'], {'attempted':1, 'succeeded':1, 'failed':0})
            self.assertEqual(report['submissions'], {'attempted':1, 'succeeded':1, 'failed':0})
            self.assertEqual(report['financial_import']['imported'], 4)
            self.assertNotIn('Revenues', json.dumps(report))
        self.assertEqual(sorted(r['counters']['unchanged_payloads'] for r in reports), [0, 2])

    def test_malformed_current_revenue_fails_before_silent_parser_omission(self):
        from src.sec.production_requirements import validate_revenue_sources
        now = datetime(2026, 9, 18, 18, tzinfo=filings.EASTERN)
        for field in ('accn', 'start', 'end', 'filed'):
            payload = facts()
            del payload['facts']['us-gaap']['Revenues']['units']['USD'][0][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_revenue_sources(payload, ['Revenues'], 'USD', now)
        validate_revenue_sources({'facts': {}}, ['Revenues'], 'USD', now)

    def test_readiness_query_rejects_ambiguous_current_provenance_offline(self):
        from src.sec import production_requirements as requirements
        now = datetime.now(filings.EASTERN)
        row = dict(security_id=1, company_id=1, metric='revenue', accession_number='new',
                   period_end=now.date()-timedelta(days=60), filed_date=now.date(),
                   filing_company_id=None, filing_date=None, acceptance_datetime=None)
        cursor = Mock()
        cursor.fetchone.side_effect = [dict(prospective_cutover_at=now-timedelta(days=30)), {'sources': 2}]
        cursor.fetchall.return_value = [row]
        connection = Mock()
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        context = Mock(__enter__=Mock(return_value=connection), __exit__=Mock(return_value=False))
        self.mock(requirements, 'get_connection', return_value=context)
        self.mock(requirements, 'observed_sessions', return_value=None)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            requirements.get_production_requirements(1, 'fixture')
        for call in cursor.execute.call_args_list:
            self.assertTrue(call.args[0].strip().startswith('SELECT'))
            self.assertNotIn('created_at', call.args[0])
            self.assertNotIn('updated_at', call.args[0])

    def test_unresolved_report_has_accessions_and_cik_even_after_network_failure(self):
        self.mock(submissions, 'load_json', return_value=None)
        self.mock(submissions, 'get_sec_json', side_effect=requests.Timeout('fixture'))
        with self.assertRaises(requests.Timeout):
            with reporting.RunReport('fixture') as run:
                submissions.ProductionSubmissions()(CIK, {'new': {DAY}})
        data = json.loads(run.path.read_text())
        self.assertEqual(data['counters']['current_required_unresolved'], 1)
        self.assertEqual(data['current_required_unresolved_accessions'], [{'cik': CIK, 'accession': 'new'}])
        self.assertEqual(data['submissions']['failed'], 1)

    def test_partially_stored_ancient_filing_is_nonfatal(self):
        from src.sec.production_requirements import select_requirements
        now = datetime(2026, 9, 18, 18, tzinfo=filings.EASTERN)
        row = dict(company_id=1, metric='revenue', accession_number='ancient',
                   period_end=date(2005, 6, 30), filed_date=date(2005, 8, 1),
                   filing_company_id=1, filing_date=date(2005, 8, 1), acceptance_datetime=None)
        required, _, warnings = select_requirements([row], now, now-timedelta(days=30))
        self.assertEqual(required, {})
        self.assertEqual(warnings, ['ancient'])
        row['filing_date'] = DAY
        self.assertIn('ancient', select_requirements([row], now, now-timedelta(days=30))[0])

    def test_report_pending_requirements_cannot_pass_without_exception(self):
        with self.assertRaisesRegex(RuntimeError, 'incomplete production'):
            with reporting.RunReport('fixture') as run:
                reporting.unresolved(CIK, ['missing'])
        self.assertEqual(json.loads(run.path.read_text())['status'], 'FAIL')

    def test_stage_only_success_is_not_overall_freshness(self):
        with reporting.RunReport('fixture', mode='production-refresh-financials-only') as run:
            pass
        data = json.loads(run.path.read_text())
        self.assertEqual(data['status'], 'PASS')
        self.assertEqual(data['freshness'], 'FAIL')

    def test_retry_and_network_counters_use_actual_http_boundary(self):
        self.mock(http, '_last_request_at', new=None)
        self.mock(http, '_blocked_until', new=0.0)
        self.mock(http.time, 'sleep')
        response429 = Mock(status_code=429, headers={})
        response429.raise_for_status.side_effect = requests.HTTPError(response=response429)
        response503 = Mock(status_code=503, headers={})
        response503.raise_for_status.side_effect = requests.HTTPError(response=response503)
        get = self.mock(http.requests, 'get', side_effect=[response429, response503, requests.Timeout('fixture')])
        with self.assertRaises(requests.Timeout):
            with reporting.RunReport('fixture') as run:
                http.get_sec_json('fixture')
        data = json.loads(run.path.read_text())['counters']
        self.assertEqual(get.call_count, 3)
        for key, value in {'http_requests':3, 'retries':2, 'responses_429':1,
                           'responses_5xx':1, 'network_failures':1}.items():
            self.assertEqual(data[key], value)

    def test_permanent_response_still_remembers_server_cooldown(self):
        self.mock(http, '_last_request_at', new=None)
        self.mock(http, '_blocked_until', new=0.0)
        self.mock(http.time, 'sleep')
        response = Mock(status_code=403, headers={'Retry-After':'120'})
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        get = self.mock(http.requests, 'get', return_value=response)
        for resource in ('A', 'B'):
            with self.assertRaises(requests.HTTPError): http.get_sec_json(resource)
        get.assert_called_once()


class FactLinkedPersistenceTests(OfflineTest):
    """Real classifier, submissions/cache, upsert and report; only I/O is replaced."""
    def setUp(self):
        super().setUp()
        from src.sec import production_requirements
        from src.backtesting import build_backtest_events
        from src.analysis import event_timing
        self.requirements = production_requirements
        self.builder = build_backtest_events
        self.now = datetime(2026, 9, 18, 18, tzinfo=filings.EASTERN)
        self.cutover = None
        self.rows = []
        self.saved = {}
        self.writes = []
        self.save_error = None
        self.current = None
        self.payload = main_json()
        directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.mock(submissions, 'CACHE_DIR', new=directory)
        self.mock(filings, 'get_production_issuers', return_value=[issuer()])
        self.mock(production_requirements, 'datetime').now.return_value = self.now
        self.mock(production_requirements, 'observed_sessions', return_value=None)
        from unittest.mock import MagicMock
        context = MagicMock()
        connection = context.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = self.execute
        cursor.fetchone.side_effect = lambda: self.current[0] if self.current else None
        cursor.fetchall.side_effect = lambda: self.current
        for module in (filings, production_requirements, build_backtest_events, event_timing):
            self.mock(module, 'get_connection', return_value=context)
        self.mock(http, '_last_request_at', new=None)
        self.mock(http, '_blocked_until', new=0.0)
        self.mock(http.time, 'sleep')
        self.get = self.mock(http.requests, 'get', side_effect=self.respond)

    def fact(self, accession, metric='revenue', filed=DAY, period=date(2026, 6, 30), security=1):
        row = dict(company_id=1, security_id=security, metric=metric, accession_number=accession,
                   filed_date=filed, period_end=period)
        self.rows.append(row)
        return row

    def recent(self, *accessions, shards=()):
        self.payload = main_json(*accessions, shards=shards)
        data = self.payload['filings']['recent']
        data.update(form=['10-Q']*len(accessions), reportDate=['2026-06-30']*len(accessions),
                    primaryDocument=['quarter.htm']*len(accessions))

    def respond(self, url, **kwargs):
        if '/CIK' not in url:
            raise AssertionError('Unexpected historical request')
        return Mock(status_code=200, headers={}, json=Mock(return_value=self.payload))

    def execute(self, query, parameters=()):
        query = ' '.join(query.split())
        if query.startswith('SELECT prospective_cutover_at'):
            self.current = [dict(prospective_cutover_at=self.cutover)]
        elif query.startswith('SELECT DISTINCT ff.security_id'):
            self.current = []
            for row in self.rows:
                stored = self.saved.get(row['accession_number'], {})
                self.current.append(dict(row, filing_company_id=stored.get('company_id'),
                                         filing_date=stored.get('filing_date'),
                                         acceptance_datetime=stored.get('acceptance_datetime')))
        elif query.startswith('SELECT COUNT(*) AS sources'):
            self.current = [dict(sources=sum(r['security_id'] == parameters[0]
                                            and r['period_end'] == parameters[1]
                                            and r['metric'] == 'revenue' for r in self.rows))]
        elif query.startswith('INSERT INTO filings'):
            if self.save_error:
                raise self.save_error
            self.writes.append(parameters)
            keys = ('company_id', 'accession_number', 'form', 'filing_date', 'report_date',
                    'acceptance_datetime', 'primary_document', 'primary_doc_description', 'filing_url')
            self.saved[parameters[1]] = dict(zip(keys, parameters))
        elif query.startswith('SELECT filing_date, acceptance_datetime, form FROM filings'):
            row = self.saved.get(parameters[0])
            self.current = [(row['filing_date'], row['acceptance_datetime'], row['form'])] if row else []
        elif query.startswith('SELECT trade_date FROM daily_prices'):
            self.current = [(DAY,)] if parameters[1] <= DAY <= parameters[2] else []
        else:
            raise AssertionError('Unexpected SQL in offline fixture')

    def run_refresh(self):
        with reporting.RunReport('fixture') as self.report:
            result = filings.import_universe('fixture', production_refresh=True)
        return result, json.loads(self.report.path.read_text())

    def test_null_cutover_persists_fact_sources_without_broad_mirror(self):
        self.fact('new')
        self.fact('missing-recent', security=2)
        self.recent('new', 'unrelated-8k', shards=[shard()])
        results, report = self.run_refresh()
        self.assertEqual(results[0]['target'], 0)
        self.assertEqual(set(self.saved), {'new'})
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['freshness'], 'PASS')
        self.assertEqual(report['cutover'], dict(state='DISABLED', timestamp=None, observed_timestamps=[None]))
        self.assertEqual(report['report_version'], 2)
        self.assertEqual(report['filing_coverage'], dict(targeted=2, available=1, reused=0,
                         persisted=1, unresolved=1, issuers_complete=1, issuers_attempted=1, status='GAPS'))
        self.assertEqual(report['non_current_fact_linked_gaps'], [dict(cik=CIK, accession='missing-recent')])
        self.assertNotIn('historical_unresolved_warnings', json.dumps(report))
        self.assertEqual(report['counters']['targeted_recovery_attempts'], 0)
        self.get.assert_called_once()
        self.assertIn('cutover DISABLED | fact-coverage GAPS persisted 1 gaps 1', self.output.getvalue())
        # The untouched event builder can now find the source and compute its entry.
        self.assertEqual(self.builder.get_entry_date('AAA', self.rows[0]), DAY)
        self.assertIsNotNone(self.saved['new']['acceptance_datetime'].tzinfo)
        self.assertTrue(self.saved['new']['filing_url'].endswith('/quarter.htm'))

    def test_enabled_cutover_persists_required_and_non_required(self):
        self.cutover = self.now-timedelta(days=30)
        self.fact('required')
        self.fact('non-required', metric='net_income')
        self.recent('required', 'non-required')
        results, report = self.run_refresh()
        self.assertEqual(results[0]['target'], 1)
        self.assertEqual(set(self.saved), {'required', 'non-required'})
        self.assertEqual(report['cutover']['state'], 'ENABLED')
        self.assertEqual(report['cutover']['timestamp'], self.cutover.isoformat())
        self.assertEqual(report['filing_coverage']['persisted'], 2)
        from src.paper_trading.paper_execution import freshness_reason
        source = dict(self.saved['required'], filed_date=DAY, filing_company_id=1)
        self.assertEqual(self.builder.get_entry_date('AAA', self.rows[0]), DAY)
        self.assertIsNone(freshness_reason(dict(entry_date=DAY, period_end=date(2026,6,30)),
                                          [source], self.cutover, self.now, [DAY]))
        self.assertEqual(report['filing_coverage']['status'], 'COMPLETE')
        self.assertEqual(report['counters']['current_required_unresolved'], 0)
        self.assertEqual(report['counters']['targeted_recovery_attempts'], 0)

    def test_non_required_gap_is_nonfatal_and_never_recovers_history(self):
        self.cutover = self.now-timedelta(days=30)
        self.fact('old', filed=date(2005, 8, 1), period=date(2005, 6, 30))
        self.fact('recent-non-revenue', metric='net_income')
        self.recent(shards=[shard(), shard('old.json', '2005-01-01', '2005-12-31')])
        _, report = self.run_refresh()
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['counters']['non_current_fact_linked_gaps'], 2)
        self.assertEqual(report['counters']['historical_shards_downloaded'], 0)
        self.get.assert_called_once()
        self.assertEqual(self.writes, [])

    def test_required_gap_blocks_pass(self):
        self.cutover = self.now-timedelta(days=30)
        self.fact('required')
        self.recent()
        with self.assertRaisesRegex(RuntimeError, 'Production filing SEC refresh failed'):
            self.run_refresh()
        report = json.loads(self.report.path.read_text())
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['counters']['current_required_unresolved'], 1)
        self.assertEqual(report['current_required_unresolved_accessions'], [dict(cik=CIK, accession='required')])
        self.assertEqual(report['filing_coverage']['status'], 'INCOMPLETE')

    def test_history_recovery_only_for_required_but_returned_fact_sources_are_saved(self):
        self.cutover = self.now-timedelta(days=30)
        self.fact('required')
        self.fact('non-required', metric='net_income')
        self.fact('absent-non-required', metric='gross_profit')
        self.recent(shards=[shard(), shard('unrelated.json', '2000-01-01', '2000-12-31')])
        main = self.payload
        self.get.side_effect = [Mock(status_code=200, headers={}, json=Mock(return_value=main)),
                               Mock(status_code=200, headers={}, json=Mock(return_value=columnar('required', 'non-required')))]
        _, report = self.run_refresh()
        self.assertEqual(set(self.saved), {'required', 'non-required'})
        self.assertEqual(self.get.call_count, 2)
        self.assertTrue(self.get.call_args_list[1].args[0].endswith('/history.json'))
        self.assertEqual(report['counters']['targeted_recovery_attempts'], 1)
        self.assertEqual(report['counters']['targeted_recovery_resolved'], 1)
        self.assertEqual(report['counters']['non_current_fact_linked_gaps'], 1)

    def test_existing_valid_metadata_is_reused_even_when_not_recent(self):
        self.fact('new')
        self.recent('new')
        self.run_refresh()
        self.recent()
        _, report = self.run_refresh()
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(report['filing_coverage']['reused'], 1)
        self.assertEqual(report['filing_coverage']['persisted'], 0)
        self.assertEqual(report['filing_coverage']['available'], 0)
        self.assertEqual(report['filing_coverage']['unresolved'], 0)
        self.assertEqual(self.get.call_count, 2)  # Once per invocation, not a stale refresh.

    def test_partial_stored_metadata_is_upserted_from_available_source(self):
        self.fact('partial')
        self.saved['partial'] = dict(company_id=1, filing_date=DAY, acceptance_datetime=None)
        self.recent('partial')
        _, report = self.run_refresh()
        self.assertEqual(report['filing_coverage']['persisted'], 1)
        self.assertEqual(report['filing_coverage']['reused'], 0)
        self.assertEqual(report['filing_coverage']['unresolved'], 0)
        self.assertIsNotNone(self.saved['partial']['acceptance_datetime'])
        # Repeated identical refresh reuses the repaired metadata.
        _, report = self.run_refresh()
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(report['filing_coverage']['reused'], 1)
        self.assertEqual(report['counters']['unchanged_payloads'], 1)

    def test_duplicate_security_facts_do_not_duplicate_persistence(self):
        self.fact('shared')
        self.fact('shared', security=2)
        self.recent('shared')
        _, report = self.run_refresh()
        self.assertEqual(report['filing_coverage']['targeted'], 1)
        self.assertEqual(len(self.writes), 1)
        self.get.assert_called_once()

    def test_invalid_optional_metadata_warns_without_persistence(self):
        self.fact('optional', metric='net_income')
        self.recent('optional')
        self.payload['filings']['recent']['acceptanceDateTime'] = [None]
        _, report = self.run_refresh()
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['filing_coverage']['available'], 0)
        self.assertEqual(report['counters']['non_current_fact_linked_gaps'], 1)
        self.assertEqual(self.writes, [])

    def test_invalid_required_metadata_blocks_pass(self):
        self.cutover = self.now-timedelta(days=30)
        self.fact('required')
        self.recent('required')
        self.payload['filings']['recent']['acceptanceDateTime'] = [None]
        with self.assertRaises(RuntimeError): self.run_refresh()
        self.assertEqual(json.loads(self.report.path.read_text())['status'], 'FAIL')
        self.assertEqual(self.writes, [])

    def test_write_failure_is_not_hidden_as_optional_coverage_warning(self):
        self.fact('optional', metric='net_income')
        self.recent('optional')
        self.save_error = RuntimeError('offline simulated write error')
        with self.assertRaises(RuntimeError): self.run_refresh()
        report = json.loads(self.report.path.read_text())
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['filing_coverage']['persisted'], 0)
        self.assertEqual(report['filing_coverage']['status'], 'INCOMPLETE')

    def test_late_recovered_metadata_does_not_allow_catchup_commitment(self):
        from src.paper_trading.paper_execution import freshness_reason
        self.cutover = self.now-timedelta(days=30)
        self.fact('late', filed=DAY-timedelta(days=2))
        self.recent('late')
        self.mock(self.requirements, 'observed_sessions', return_value=[DAY-timedelta(days=1)])
        data = self.payload['filings']['recent']
        data['filingDate'] = ['2026-09-16']
        data['acceptanceDateTime'] = ['2026-09-16T08:00:00']
        results, report = self.run_refresh()
        self.assertEqual(results[0]['target'], 0)
        self.assertEqual(report['filing_coverage']['persisted'], 1)
        source = dict(self.saved['late'], filed_date=DAY-timedelta(days=2), filing_company_id=1)
        reason = freshness_reason(dict(entry_date=DAY, period_end=date(2026,6,30)), [source],
                                  self.cutover, self.now, [DAY-timedelta(days=2), DAY-timedelta(days=1), DAY])
        self.assertEqual(reason, 'Today is not the first unambiguous observed SPY session.')


if __name__ == '__main__':
    unittest.main()
