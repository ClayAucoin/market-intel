from src.company_repository import (
    get_company_by_ticker,
)

from src.financial_history import (
    build_quarterly_history,
)

from src.xbrl_client import (
    get_company_facts,
)


TICKER = "AAPL"


REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]


def find_revenue_concept(facts):
    us_gaap = (
        facts
        .get("facts", {})
        .get("us-gaap", {})
    )

    for concept_name in REVENUE_CONCEPTS:
        if concept_name in us_gaap:
            return concept_name

    return None


def main():
    company = get_company_by_ticker(
        TICKER
    )

    if company is None:
        raise ValueError(
            f"{TICKER} was not found "
            "in the companies table."
        )

    print()
    print(
        f"Testing {TICKER}"
    )
    print("=" * 70)

    print(
        "Company:",
        company["company_name"],
    )

    print(
        "CIK:",
        company["cik"],
    )

    print()

    facts = get_company_facts(
        company["cik"]
    )

    revenue_concept = (
        find_revenue_concept(
            facts
        )
    )

    if revenue_concept is None:
        raise ValueError(
            "No supported revenue concept "
            f"found for {TICKER}."
        )

    print(
        "Revenue concept:",
        revenue_concept,
    )

    history = build_quarterly_history(
        facts,
        revenue_concept,
        "USD",
    )

    print()
    print(
        f"Quarterly records: "
        f"{len(history)}"
    )

    print()

    print(
        f"{'Period End':<14}"
        f"{'FY':>8}"
        f"{'FP':>8}"
        f"{'Revenue':>18}"
        f"{'Source':>12}"
    )

    print("-" * 60)

    for item in history[-16:]:
        source = (
            "DERIVED"
            if item["derived"]
            else "REPORTED"
        )

        revenue_billions = (
            item["value"]
            / 1_000_000_000
        )

        print(
            f"{item['end']:<14}"
            f"{str(item['fy']):>8}"
            f"{str(item['fp']):>8}"
            f"${revenue_billions:>14.3f}B"
            f"{source:>12}"
        )


if __name__ == "__main__":
    main()