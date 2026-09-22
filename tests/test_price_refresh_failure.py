"""Offline price-stage tests: no DB, API, production jobs or notifications."""
import contextlib
import io
import json
import traceback
import types
import unittest
from unittest.mock import Mock, patch

import psycopg
import requests

notifier = types.ModuleType("src.notifications.notifier")
notifier.send_notification = Mock(side_effect=AssertionError("External notification forbidden"))
with patch("dotenv.load_dotenv"), patch.dict("sys.modules", {"src.notifications.notifier": notifier}):
    from src.prices import import_universe_prices as prices
    from src import run_daily_market_intel as daily


class PriceRefreshTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.output = io.StringIO()
        self.stack.enter_context(contextlib.redirect_stdout(self.output))
        self.stack.enter_context(patch("requests.get", side_effect=AssertionError("API forbidden")))
        self.stack.enter_context(patch("psycopg.connect", side_effect=AssertionError("DB forbidden")))

    def mock(self, target, name, **kwargs):
        return self.stack.enter_context(patch.object(target, name, **kwargs))

    def import_results(self, errors):
        self.mock(prices, "get_symbols", return_value=list(errors))
        self.mock(prices, "import_symbol", side_effect=list(errors.values()))
        return prices.import_universe_prices("expanded_500", refresh=True)

    def configure_daily(self, results):
        self.importer = self.mock(daily, "import_universe_prices", return_value=results)
        self.sec = self.mock(daily, "run_module")
        self.rebuild = self.mock(daily, "rebuild_events")
        self.paper = self.mock(daily, "run_paper_system")
        self.success = self.mock(daily, "send_success_notification")
        self.failure = self.mock(daily, "send_failure_notification")
        self.mock(daily, "start_daily_log", return_value={"path": "offline-log"})
        self.mock(daily, "stop_daily_log")

    def test_all_success_continues(self):
        self.configure_daily([{"symbol": "FE", "status": "OK", "records": 1}])
        ordered = Mock()
        for name in ("sec", "importer", "rebuild", "paper", "success"):
            ordered.attach_mock(getattr(self, name), name)
        daily.main()
        self.assertEqual([call[0] for call in ordered.mock_calls],
                         ["sec", "importer", "rebuild", "paper", "success"])
        self.importer.assert_called_once_with(universe_name="expanded_500", refresh=True)
        self.failure.assert_not_called()

    def test_no_new_data_continues(self):
        self.configure_daily([{"symbol": "FE", "status": "NO NEW DATA", "records": 0}])
        daily.main()
        self.rebuild.assert_called_once()
        self.paper.assert_called_once()
        self.success.assert_called_once()
        self.failure.assert_not_called()

    def test_one_error_fails_price_stage(self):
        results = self.import_results({"FE": requests.ReadTimeout("private payload")})
        self.configure_daily(results)
        with self.assertRaisesRegex(RuntimeError, "FE: ReadTimeout.*timed out"):
            daily.refresh_prices()

    def test_multiple_errors_block_downstream_and_success(self):
        response = requests.Response()
        response.status_code = 503
        results = self.import_results({
            "FE": requests.HTTPError("private payload", response=response),
            "SPY": ValueError("private configuration"),
        })
        self.configure_daily(results)
        with self.assertRaises(RuntimeError) as caught:
            daily.main()
        message = str(caught.exception)
        self.assertIn("2 symbol(s)", message)
        self.assertIn("FE: HTTPError", message)
        self.assertIn("http_status=503", message)
        self.assertIn("SPY: ValueError", message)
        self.assertIn(message, self.output.getvalue())
        self.rebuild.assert_not_called()
        self.paper.assert_not_called()
        self.success.assert_not_called()
        self.failure.assert_called_once_with(caught.exception, "offline-log")

    def test_error_result_retains_safe_diagnostics(self):
        results = self.import_results({"FE": psycopg.errors.UniqueViolation("private SQL")})
        result = results[0]
        self.assertEqual(result["symbol"], "FE")
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["records"], 0)
        self.assertEqual(result["error_type"], "UniqueViolation")
        self.assertEqual(result["sqlstate"], "23505")
        self.assertIn("database operation failed", result["error_message"])
        self.assertEqual(result["error_context"], "tiingo price import; refresh=True")

    def test_secrets_absent_from_results_logs_aggregate_and_notification(self):
        # Synthetic secrets cover URL userinfo/query, headers, DSNs, JSON,
        # multiline text and arbitrary unlabeled payloads (no regex guessing).
        secrets = ["fake-url-password", "fake-api-key", "fake-bearer-token",
                   "fake-db-password", "fake-oauth-token", "fake-unlabeled-secret"]
        raw = ("https://user:fake-url-password@example.test?api_key=fake-api-key\n"
               "Authorization: Bearer fake-bearer-token\n"
               "postgresql://user:fake-db-password@host/db\n"
               '{"refresh_token":"fake-oauth-token"}\nfake-unlabeled-secret')
        response = requests.Response()
        response.status_code = 401
        response._content = raw.encode()
        response.url = raw
        response.headers["Authorization"] = raw
        error = requests.HTTPError(raw, response=response)
        error.__cause__ = ValueError(raw)
        results = self.import_results({"FE": error})
        format_failure_notification = daily.send_failure_notification
        self.configure_daily(results)
        # Exercise notification formatting while mocking the actual sender.
        self.failure.side_effect = format_failure_notification
        sender = self.mock(daily, "send_notification")
        with self.assertRaises(RuntimeError) as caught:
            daily.main()
        visible = (json.dumps(results) + self.output.getvalue() + str(caught.exception)
                   + "".join(traceback.format_exception(caught.exception))
                   + str(sender.call_args))
        for secret in secrets:
            self.assertNotIn(secret, visible)
        self.assertIn("HTTPError", visible)
        self.assertIn("401", visible)

    def test_empty_response_is_not_error_and_does_not_save(self):
        self.mock(prices, "get_provider_symbol", return_value="FE")
        self.mock(prices, "get_import_start_date", return_value="2026-09-22")
        fetch = self.mock(prices, "get_historical_prices", return_value=[])
        save = self.mock(prices, "save_daily_prices")
        result = prices.import_symbol("FE", refresh=True)
        self.assertEqual(result["status"], "NO NEW DATA")
        fetch.assert_called_once_with("FE", start_date="2026-09-22", refresh=True,
                                      use_cache=False, save_cache=False)
        save.assert_not_called()

    def test_current_prices_do_not_turn_exception_into_no_new_data(self):
        self.mock(prices, "get_symbols", return_value=["FE"])
        self.mock(prices, "get_provider_symbol", return_value="FE")
        self.mock(prices, "get_import_start_date", return_value="2026-09-22")
        self.mock(prices, "get_historical_prices", side_effect=requests.ReadTimeout("private"))
        save = self.mock(prices, "save_daily_prices")
        result = prices.import_universe_prices("expanded_500", refresh=True)[0]
        self.assertEqual(result["status"], "ERROR")
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
