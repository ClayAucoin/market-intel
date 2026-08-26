from src.company_universe import (
    get_tickers,
)

from src.price_client import (
    get_historical_prices,
)

from src.price_repository import (
    save_daily_prices,
)


BENCHMARK = "SPY"

START_DATE = "2018-01-01"


def get_symbols():
    symbols = get_tickers()

    if BENCHMARK not in symbols:
        symbols.append(
            BENCHMARK
        )

    return symbols


def import_symbol(symbol):
    print()
    print(
        f"Importing {symbol} prices..."
    )

    prices = get_historical_prices(
        symbol,
        start_date=START_DATE,
        refresh=False,
    )

    count = len(prices)

    if count == 0:
        print(
            f"No price data returned "
            f"for {symbol}."
        )

        return {
            "symbol": symbol,
            "records": 0,
            "status": "EMPTY",
        }

    save_daily_prices(
        symbol,
        prices,
    )

    return {
        "symbol": symbol,
        "records": count,
        "status": "OK",
    }


def import_universe_prices():
    symbols = get_symbols()

    results = []

    print()
    print(
        "MARKET INTEL UNIVERSE "
        "PRICE IMPORT"
    )

    print("=" * 60)

    for symbol in symbols:
        try:
            result = import_symbol(
                symbol
            )

        except Exception as error:
            print(
                f"ERROR importing "
                f"{symbol}: {error}"
            )

            result = {
                "symbol": symbol,
                "records": 0,
                "status": "ERROR",
            }

        results.append(
            result
        )

    print()
    print("=" * 60)

    print(
        "PRICE IMPORT SUMMARY"
    )

    print()

    print(
        f"{'Symbol':<10}"
        f"{'Records':>12}"
        f"{'Status':>12}"
    )

    print("-" * 34)

    total_records = 0
    errors = 0

    for result in results:
        print(
            f"{result['symbol']:<10}"
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

    print("-" * 34)

    print(
        f"{'TOTAL':<10}"
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


if __name__ == "__main__":
    import_universe_prices()