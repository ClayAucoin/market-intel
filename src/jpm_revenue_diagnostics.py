from src.company_repository import (
    get_company_by_ticker,
)

from src.xbrl_client import (
    get_company_facts,
)


TICKER = "JPM"


SEARCH_TERMS = [
    "revenue",
    "interestincome",
    "interestanddividend",
    "noninterestincome",
    "investmentbanking",
    "fees",
]


def find_matching_concepts(
    facts,
):
    us_gaap = (
        facts
        .get("facts", {})
        .get("us-gaap", {})
    )

    results = []

    for concept_name, concept_data in (
        us_gaap.items()
    ):
        normalized = (
            concept_name.lower()
        )

        if not any(
            term in normalized
            for term in SEARCH_TERMS
        ):
            continue

        units = (
            concept_data
            .get("units", {})
        )

        usd_values = units.get(
            "USD",
            []
        )

        if not usd_values:
            continue

        dates = [
            value.get("end")
            for value in usd_values
            if value.get("end")
        ]

        forms = sorted(
            {
                value.get("form")
                for value in usd_values
                if value.get("form")
            }
        )

        results.append(
            {
                "concept":
                    concept_name,

                "label":
                    concept_data.get(
                        "label"
                    ),

                "records":
                    len(usd_values),

                "earliest":
                    min(dates)
                    if dates
                    else None,

                "latest":
                    max(dates)
                    if dates
                    else None,

                "forms":
                    forms,
            }
        )

    return sorted(
        results,
        key=lambda item: (
            item["latest"] or "",
            item["records"],
        ),
        reverse=True,
    )


def main():
    company = (
        get_company_by_ticker(
            TICKER
        )
    )

    if company is None:
        raise ValueError(
            f"{TICKER} not found."
        )

    facts = get_company_facts(
        company["cik"]
    )

    matches = find_matching_concepts(
        facts
    )

    print()
    print(
        "JPM REVENUE CONCEPT "
        "DIAGNOSTICS"
    )

    print("=" * 125)

    print(
        f"{'Concept':<58}"
        f"{'Records':>9}"
        f"{'Earliest':>13}"
        f"{'Latest':>13}  "
        f"{'Forms'}"
    )

    print("-" * 125)

    for item in matches:
        print(
            f"{item['concept']:<58}"
            f"{item['records']:>9}"
            f"{str(item['earliest']):>13}"
            f"{str(item['latest']):>13}  "
            f"{', '.join(item['forms'])}"
        )

        print(
            f"  Label: "
            f"{item['label']}"
        )


if __name__ == "__main__":
    main()