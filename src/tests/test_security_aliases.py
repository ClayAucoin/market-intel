from src.data.security_aliases import (
    get_symbol,
)


TESTS = [
    (
        "AAPL",
        "tiingo",
    ),
    (
        "DELL",
        "tiingo",
    ),
    (
        "JPM",
        "tiingo",
    ),
]


def main():
    print()
    print(
        "SECURITY ALIAS TEST"
    )

    print("=" * 50)

    for ticker, source in TESTS:
        symbol = get_symbol(
            ticker,
            source,
        )

        print(
            f"{ticker:<10}"
            f"{source:<12}"
            f"{symbol}"
        )


if __name__ == "__main__":
    main()