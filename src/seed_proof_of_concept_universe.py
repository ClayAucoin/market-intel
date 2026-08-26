from src.analysis_universe import (
    add_security_to_universe,
    create_universe,
)


UNIVERSE_NAME = (
    "proof_of_concept_10"
)


COMPANIES = [
    {
        "ticker": "DELL",
        "sector": "Technology",
    },
    {
        "ticker": "AAPL",
        "sector": "Technology",
    },
    {
        "ticker": "MSFT",
        "sector": "Technology",
    },
    {
        "ticker": "JPM",
        "sector": "Financials",
    },
    {
        "ticker": "UNH",
        "sector": "Healthcare",
    },
    {
        "ticker": "CAT",
        "sector": "Industrials",
    },
    {
        "ticker": "WMT",
        "sector": "Consumer Staples",
    },
    {
        "ticker": "HD",
        "sector": "Consumer Discretionary",
    },
    {
        "ticker": "XOM",
        "sector": "Energy",
    },
    {
        "ticker": "GOOGL",
        "sector": "Communication Services",
    },
]


def seed():
    create_universe(
        UNIVERSE_NAME,
        (
            "Original 10-company "
            "market-intel proof of concept."
        ),
    )

    for company in COMPANIES:
        add_security_to_universe(
            UNIVERSE_NAME,
            company["ticker"],
            sector=
                company["sector"],
        )

        print(
            f"Added "
            f"{company['ticker']} "
            f"({company['sector']})"
        )

    print()
    print(
        "proof_of_concept_10 "
        "seed completed successfully."
    )


if __name__ == "__main__":
    seed()