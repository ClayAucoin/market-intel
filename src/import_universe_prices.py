import sys

from src.company_universe import (
    DEFAULT_UNIVERSE,
    get_tickers,
)

from src.price_client import (
    get_historical_prices,
)

from src.price_repository import (
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


def import_symbol(
    symbol,
    refresh=False,
):
    provider_symbol = (
        get_provider_symbol(
            symbol
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

    prices = get_historical_prices(
        provider_symbol,
        start_date=START_DATE,
        refresh=refresh,
    )

    count = len(prices)

    if count == 0:
        print(
            f"No price data returned "
            f"for {symbol}."
        )

        return {
            "symbol": symbol,
            "provider_symbol":
                provider_symbol,
            "records": 0,
            "status": "EMPTY",
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
        f"{'Status':>12}"
    )

    print("-" * 48)

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
            f"{result['status']:>12}"
        )

        total_records += (
            result["records"]
        )

        if (
            result["status"]
            != "OK"
        ):
            errors += 1

    print("-" * 48)

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