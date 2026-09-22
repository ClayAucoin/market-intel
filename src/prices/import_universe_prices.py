import sys
import re

import requests
import psycopg

from datetime import timedelta

from src.universe.company_universe import (
    DEFAULT_UNIVERSE,
    get_tickers,
)

from src.prices.price_client import (
    get_historical_prices,
)

from src.prices.price_repository import (
    get_latest_price_date,
    save_daily_prices,
)

from src.data.security_aliases import (
    get_symbol,
)


BENCHMARK = "SPY"

START_DATE = "2018-01-01"

PRICE_SOURCE = "tiingo"


def safe_price_error(error):
    """Allowlisted diagnostics only: never copy exception text or payloads.

    Network/DB messages can contain URLs, headers, DSNs and credentials.
    Keep the exception category and structured codes, as SEC reports do.
    """
    message = "Price import failed; raw exception text withheld."
    if isinstance(error, requests.exceptions.Timeout):
        message = "Price provider request timed out."
    elif isinstance(error, requests.exceptions.HTTPError):
        message = "Price provider returned an unsuccessful HTTP response."
    elif isinstance(error, requests.exceptions.ConnectionError):
        message = "Could not connect to the price provider."
    elif isinstance(error, requests.exceptions.JSONDecodeError):
        message = "Price provider returned invalid JSON."
    elif isinstance(error, psycopg.Error):
        message = "Price import database operation failed."
    elif isinstance(error, (ValueError, KeyError, TypeError)):
        message = "Invalid price configuration, response format or record data."
    details = {"error_type": type(error).__name__, "error_message": message}
    if isinstance(error, requests.exceptions.HTTPError):
        status = getattr(error.response, "status_code", None)
        if type(status) is int and 100 <= status <= 599:
            details["http_status"] = status
    if isinstance(error, psycopg.Error):
        code = error.sqlstate
        if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code):
            details["sqlstate"] = code
    return details


def format_price_error(result):
    details = f"{result['symbol']}: {result['error_type']}: {result['error_message']}"
    for key in ("http_status", "sqlstate"):
        if key in result:
            details += f" {key}={result[key]}"
    return details


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


def get_symbols(
    universe_name,
):
    symbols = get_tickers(
        universe_name
    )

    if BENCHMARK not in symbols:
        symbols.append(
            BENCHMARK
        )

    return symbols


def get_provider_symbol(
    symbol,
):
    if symbol == BENCHMARK:
        return symbol

    return get_symbol(
        symbol,
        PRICE_SOURCE,
    )


def get_import_start_date(
    symbol,
    refresh,
):
    if not refresh:
        return START_DATE

    latest_date = (
        get_latest_price_date(
            symbol
        )
    )

    if latest_date is None:
        return START_DATE

    next_date = (
        latest_date
        + timedelta(
            days=1
        )
    )

    return next_date.isoformat()


def import_symbol(
    symbol,
    refresh=False,
):
    provider_symbol = (
        get_provider_symbol(
            symbol
        )
    )

    start_date = (
        get_import_start_date(
            symbol,
            refresh,
        )
    )

    print()

    if provider_symbol == symbol:
        print(
            f"Importing {symbol} prices..."
        )

    else:
        print(
            f"Importing {symbol} prices "
            f"using {PRICE_SOURCE} symbol "
            f"{provider_symbol}..."
        )

    print(
        f"Start date: {start_date}"
    )

    if refresh:
        prices = get_historical_prices(
            provider_symbol,
            start_date=start_date,
            refresh=True,
            use_cache=False,
            save_cache=False,
        )

    else:
        prices = get_historical_prices(
            provider_symbol,
            start_date=start_date,
            refresh=False,
            use_cache=True,
            save_cache=True,
        )

    count = len(prices)

    if count == 0:
        print(
            f"No new price data returned "
            f"for {symbol}."
        )

        return {
            "symbol": symbol,
            "provider_symbol":
                provider_symbol,
            "records": 0,
            "status": "NO NEW DATA",
        }

    save_daily_prices(
        symbol,
        prices,
    )

    return {
        "symbol": symbol,
        "provider_symbol":
            provider_symbol,
        "records": count,
        "status": "OK",
    }


def import_universe_prices(
    universe_name=None,
    refresh=False,
):
    if universe_name is None:
        universe_name = (
            get_universe_name()
        )

    symbols = get_symbols(
        universe_name
    )

    results = []

    print()
    print(
        "MARKET INTEL UNIVERSE "
        "PRICE IMPORT"
    )

    print(
        "Universe:",
        universe_name,
    )

    print(
        "Refresh:",
        refresh,
    )

    print("=" * 72)

    for symbol in symbols:
        try:
            result = import_symbol(
                symbol,
                refresh=refresh,
            )

        except Exception as error:
            result = {
                "symbol": symbol,
                "provider_symbol": None,
                "records": 0,
                "status": "ERROR",
                "error_context": f"{PRICE_SOURCE} price import; refresh={refresh}",
                **safe_price_error(error),
            }
            print(f"ERROR importing {format_price_error(result)} "
                  f"({result['error_context']})")

        results.append(
            result
        )

    print()
    print("=" * 72)

    print(
        "PRICE IMPORT SUMMARY"
    )

    print()

    print(
        f"{'Symbol':<10}"
        f"{'Provider':<12}"
        f"{'Records':>12}"
        f"{'Status':>16}"
    )

    print("-" * 50)

    total_records = 0
    errors = 0

    for result in results:
        provider = (
            result["provider_symbol"]
            if result["provider_symbol"]
            else "-"
        )

        print(
            f"{result['symbol']:<10}"
            f"{provider:<12}"
            f"{result['records']:>12}"
            f"{result['status']:>16}"
        )

        total_records += (
            result["records"]
        )

        if (
            result["status"]
            == "ERROR"
        ):
            errors += 1

    print("-" * 50)

    print(
        f"{'TOTAL':<22}"
        f"{total_records:>12}"
    )

    print()

    print(
        "Symbols:",
        len(results),
    )

    print(
        "Errors:",
        errors,
    )

    return results


if __name__ == "__main__":
    import_universe_prices()
