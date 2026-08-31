from src.company_repository import (
    get_company_by_ticker,
)

from src.issuer_repository import (
    get_issuer_history_by_ticker,
)

from src.sec.xbrl_client import (
    get_company_facts,
)


TICKER = "V"


SEARCH_TERMS = [
    "earningspershare",
    "incomeper",
    "diluted",
    "basicanddiluted",
    "commonshare",
]


def get_current_cik():
    issuers = get_issuer_history_by_ticker(
        TICKER
    )

    if issuers:
        current = [
            issuer
            for issuer in issuers
            if issuer.get("is_current")
        ]

        if current:
            return current[0]["cik"]

        return issuers[-1]["cik"]

    company = get_company_by_ticker(
        TICKER
    )

    if company is None:
        raise ValueError(
            f"Ticker not found: {TICKER}"
        )

    return company["cik"]


def matches(concept):
    lowered = concept.lower()

    return any(
        term in lowered
        for term in SEARCH_TERMS
    )


def main():
    cik = get_current_cik()

    facts = get_company_facts(
        cik
    )

    us_gaap = (
        facts
        .get("facts", {})
        .get("us-gaap", {})
    )

    matching = [
        (
            concept,
            data,
        )
        for concept, data
        in us_gaap.items()
        if matches(concept)
    ]

    matching.sort(
        key=lambda item:
            item[0].lower()
    )

    print()
    print(
        "VISA EPS CONCEPT DIAGNOSTIC"
    )

    print(
        f"CIK: {cik}"
    )

    print("=" * 150)

    print(
        f"{'Concept':<75}"
        f"{'Unit':<18}"
        f"{'Rows':>8}"
        f"{'Latest End':>14}"
        f"{'Latest Filed':>14}"
        f"{'Form':>10}"
    )

    print("-" * 150)

    for concept, data in matching:
        units = data.get(
            "units",
            {}
        )

        for unit, rows in units.items():
            if not rows:
                continue

            ordered = sorted(
                rows,
                key=lambda row: (
                    row.get("end") or "",
                    row.get("filed") or "",
                ),
                reverse=True,
            )

            latest = ordered[0]

            print(
                f"{concept:<75}"
                f"{unit:<18}"
                f"{len(rows):>8}"
                f"{str(latest.get('end') or '-'):>14}"
                f"{str(latest.get('filed') or '-'):>14}"
                f"{str(latest.get('form') or '-'):>10}"
            )


if __name__ == "__main__":
    main()