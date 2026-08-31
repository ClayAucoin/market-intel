import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()


TIINGO_API_KEY = os.getenv("TIINGO_API_KEY")

BASE_URL = "https://api.tiingo.com/tiingo/daily"

CACHE_DIR = Path("data/cache/prices")


def get_cache_path(symbol):
    symbol = symbol.upper()

    return CACHE_DIR / f"{symbol}.json"


def load_cached_prices(symbol):
    cache_path = get_cache_path(symbol)

    if not cache_path.exists():
        return None

    with cache_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_cached_prices(
    symbol,
    data,
):
    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_path = get_cache_path(symbol)

    with cache_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
        )


def fetch_prices_from_api(
    symbol,
    start_date=None,
    end_date=None,
):
    if not TIINGO_API_KEY:
        raise ValueError(
            "TIINGO_API_KEY is missing from .env"
        )

    symbol = symbol.upper()

    url = (
        f"{BASE_URL}/"
        f"{symbol}/prices"
    )

    headers = {
        "Authorization": (
            f"Token {TIINGO_API_KEY}"
        ),
    }

    params = {
        "format": "json",
        "resampleFreq": "daily",
    }

    if start_date:
        params["startDate"] = start_date

    if end_date:
        params["endDate"] = end_date

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError(
            "Unexpected Tiingo response format."
        )

    return data


def get_historical_prices(
    symbol,
    start_date=None,
    end_date=None,
    refresh=False,
    use_cache=True,
    save_cache=True,
):
    symbol = symbol.upper()

    if (
        use_cache
        and not refresh
    ):
        cached = load_cached_prices(
            symbol
        )

        if cached is not None:
            print(
                f"Loaded {symbol} prices "
                f"from cache."
            )

            return cached

    print(
        f"Downloading {symbol} "
        f"prices from Tiingo..."
    )

    data = fetch_prices_from_api(
        symbol,
        start_date=start_date,
        end_date=end_date,
    )

    if save_cache:
        save_cached_prices(
            symbol,
            data,
        )

        print(
            f"Saved {symbol} response "
            f"to cache."
        )

    return data


def print_price_summary(
    symbol,
    prices,
):
    print()
    print(
        f"{symbol} price records:",
        len(prices),
    )

    print()
    print("Most recent 5 records:")

    for price in prices[-5:]:
        print(
            price.get("date"),
            "| Open:",
            price.get("open"),
            "| High:",
            price.get("high"),
            "| Low:",
            price.get("low"),
            "| Close:",
            price.get("close"),
            "| Adj Close:",
            price.get("adjClose"),
            "| Volume:",
            price.get("volume"),
            "| Dividend:",
            price.get("divCash"),
            "| Split:",
            price.get("splitFactor"),
        )


if __name__ == "__main__":
    symbols = [
        "DELL",
        "SPY",
    ]

    for symbol in symbols:
        prices = get_historical_prices(
            symbol,
            start_date="2018-01-01",
            refresh=False,
        )

        print_price_summary(
            symbol,
            prices,
        )

        print()
        print("=" * 80)