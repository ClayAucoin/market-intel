from src.price_client import (
    get_historical_prices,
)

from src.price_repository import (
    save_daily_prices,
)


SYMBOLS = [
    "DELL",
    "SPY",
]


def import_prices():
    for symbol in SYMBOLS:
        print()
        print(
            f"Importing {symbol} prices..."
        )

        prices = get_historical_prices(
            symbol,
            start_date="2018-01-01",
            refresh=False,
        )

        save_daily_prices(
            symbol,
            prices,
        )


if __name__ == "__main__":
    import_prices()