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
    "eps",
    "diluted",
    "incomeper",
    "share",
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

    namespaces = facts.get(
        "facts",
        {}
    )

    print()
    print(
        "VISA ALL-NAMESPACE EPS DIAGNOSTIC"
    )

    print(
        f"CIK: {cik}"
    )

    print()

    print(
        "Namespaces:"
    )

    for namespace in sorted(
        namespaces.keys()
    ):
        print(
            f"  {namespace}"
        )

    print()
    print("=" * 170)

    print(
        f"{'Namespace':<25}"
        f"{'Concept':<75}"
        f"{'Unit':<18}"
        f"{'Rows':>8}"
        f"{'Latest End':>14}"
        f"{'Latest Filed':>14}"
        f"{'Form':>10}"
    )

    print("-" * 170)

    found = 0

    for namespace in sorted(
        namespaces.keys()
    ):
        concepts = namespaces[
            namespace
        ]

        for concept, data in sorted(
            concepts.items()
        ):
            if not matches(
                concept
            ):
                continue

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
                    f"{namespace:<25}"
                    f"{concept:<75}"
                    f"{unit:<18}"
                    f"{len(rows):>8}"
                    f"{str(latest.get('end') or '-'):>14}"
                    f"{str(latest.get('filed') or '-'):>14}"
                    f"{str(latest.get('form') or '-'):>10}"
                )

                found += 1

    print()
    print(
        "Matching concept/unit combinations:",
        found,
    )


if __name__ == "__main__":
    main()