from src.analysis_universe import (
    get_member,
    get_universe,
    get_tickers as get_analysis_tickers,
)


DEFAULT_UNIVERSE = (
    "proof_of_concept_10"
)


def get_companies(
    universe_name=DEFAULT_UNIVERSE,
):
    return get_universe(
        universe_name
    )


def get_tickers(
    universe_name=DEFAULT_UNIVERSE,
):
    return get_analysis_tickers(
        universe_name
    )


def get_company(
    ticker,
    universe_name=DEFAULT_UNIVERSE,
):
    return get_member(
        universe_name,
        ticker,
    )


if __name__ == "__main__":
    companies = get_companies()

    print()
    print(
        f"MARKET INTEL UNIVERSE: "
        f"{DEFAULT_UNIVERSE}"
    )

    print("=" * 80)

    print(
        f"{'Ticker':<10}"
        f"{'Company':<32}"
        f"{'Sector'}"
    )

    print("-" * 80)

    for company in companies:
        print(
            f"{company['ticker']:<10}"
            f"{company['company_name']:<32}"
            f"{company['sector']}"
        )

    print()
    print(
        "Companies:",
        len(companies),
    )