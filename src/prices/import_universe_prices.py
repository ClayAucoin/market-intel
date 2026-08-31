import sys

from datetime import timedelta

from src.company_universe import (
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

from src.security_aliases import (
    get_symbol,
)


BENCHMARK = "SPY"

START_DATE = "2018-01-01"

PRICE_SOURCE = "tiingo"


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
            print(
                f"ERROR importing "
                f"{symbol}: {error}"
            )

            result = {
                "symbol": symbol,
                "provider_symbol": None,
                "records": 0,
                "status": "ERROR",
            }

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