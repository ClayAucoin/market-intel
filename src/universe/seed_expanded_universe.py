from src.universe.analysis_universe import (
    add_security_to_universe,
    create_universe,
)


UNIVERSE_NAME = "expanded_50"


COMPANIES = [
    # Technology
    {"ticker": "AAPL", "sector": "Technology"},
    {"ticker": "MSFT", "sector": "Technology"},
    {"ticker": "DELL", "sector": "Technology"},
    {"ticker": "NVDA", "sector": "Technology"},
    {"ticker": "AMD", "sector": "Technology"},
    {"ticker": "ORCL", "sector": "Technology"},
    {"ticker": "CRM", "sector": "Technology"},
    {"ticker": "AVGO", "sector": "Technology"},

    # Communication Services
    {"ticker": "GOOGL", "sector": "Communication Services"},
    {"ticker": "META", "sector": "Communication Services"},
    {"ticker": "NFLX", "sector": "Communication Services"},
    {"ticker": "DIS", "sector": "Communication Services"},

    # Financials
    {"ticker": "JPM", "sector": "Financials"},
    {"ticker": "BAC", "sector": "Financials"},
    {"ticker": "GS", "sector": "Financials"},
    {"ticker": "V", "sector": "Financials"},
    {"ticker": "MA", "sector": "Financials"},
    {"ticker": "BRK-B", "sector": "Financials"},

    # Healthcare
    {"ticker": "UNH", "sector": "Healthcare"},
    {"ticker": "JNJ", "sector": "Healthcare"},
    {"ticker": "LLY", "sector": "Healthcare"},
    {"ticker": "PFE", "sector": "Healthcare"},
    {"ticker": "ABBV", "sector": "Healthcare"},

    # Consumer Discretionary
    {"ticker": "HD", "sector": "Consumer Discretionary"},
    {"ticker": "AMZN", "sector": "Consumer Discretionary"},
    {"ticker": "TSLA", "sector": "Consumer Discretionary"},
    {"ticker": "MCD", "sector": "Consumer Discretionary"},
    {"ticker": "NKE", "sector": "Consumer Discretionary"},

    # Consumer Staples
    {"ticker": "WMT", "sector": "Consumer Staples"},
    {"ticker": "COST", "sector": "Consumer Staples"},
    {"ticker": "PG", "sector": "Consumer Staples"},
    {"ticker": "KO", "sector": "Consumer Staples"},
    {"ticker": "PEP", "sector": "Consumer Staples"},

    # Industrials
    {"ticker": "CAT", "sector": "Industrials"},
    {"ticker": "GE", "sector": "Industrials"},
    {"ticker": "BA", "sector": "Industrials"},
    {"ticker": "UPS", "sector": "Industrials"},
    {"ticker": "HON", "sector": "Industrials"},
    {"ticker": "RTX", "sector": "Industrials"},

    # Energy
    {"ticker": "XOM", "sector": "Energy"},
    {"ticker": "CVX", "sector": "Energy"},
    {"ticker": "COP", "sector": "Energy"},
    {"ticker": "SLB", "sector": "Energy"},

    # Materials
    {"ticker": "LIN", "sector": "Materials"},
    {"ticker": "NEM", "sector": "Materials"},

    # Utilities
    {"ticker": "NEE", "sector": "Utilities"},
    {"ticker": "DUK", "sector": "Utilities"},
    {"ticker": "SO", "sector": "Utilities"},

    # Real Estate
    {"ticker": "AMT", "sector": "Real Estate"},
    {"ticker": "PLD", "sector": "Real Estate"},
]


def seed():
    create_universe(
        UNIVERSE_NAME,
        (
            "Expanded 50-company market-intel "
            "research universe with diversified "
            "sector coverage."
        ),
    )

    added = 0
    failed = []

    for company in COMPANIES:
        ticker = company["ticker"]

        try:
            add_security_to_universe(
                UNIVERSE_NAME,
                ticker,
                sector=company["sector"],
            )

            print(
                f"Added {ticker:<6} "
                f"({company['sector']})"
            )

            added += 1

        except Exception as error:
            print(
                f"ERROR {ticker}: {error}"
            )

            failed.append(
                {
                    "ticker": ticker,
                    "error": str(error),
                }
            )

    print()
    print("=" * 70)

    print(
        "expanded_50 seed completed."
    )

    print(
        "Requested:",
        len(COMPANIES),
    )

    print(
        "Added:",
        added,
    )

    print(
        "Failed:",
        len(failed),
    )

    if failed:
        print()
        print(
            "Failures:"
        )

        for item in failed:
            print(
                f"  {item['ticker']}: "
                f"{item['error']}"
            )


if __name__ == "__main__":
    seed()