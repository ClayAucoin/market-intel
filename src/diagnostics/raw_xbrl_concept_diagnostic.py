from src.company_repository import (
    get_company_by_ticker,
)

from src.issuer_repository import (
    get_issuer_history_by_ticker,
)

from src.sec.xbrl_client import (
    get_company_facts,
)


TICKERS = [
    "DUK",
    "NEE",
    "V",
]


SEARCH_TERMS = [
    "revenue",
    "sales",
    "operatingrevenue",
    "earningspershare",
    "incomeper",
]


def get_current_cik(ticker):
    issuers = get_issuer_history_by_ticker(
        ticker
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
        ticker
    )

    if company is None:
        raise ValueError(
            f"Ticker not found: {ticker}"
        )

    return company["cik"]


def matches_search(concept):
    lowered = concept.lower()

    return any(
        term in lowered
        for term in SEARCH_TERMS
    )


def get_recent_unit_info(concept_data):
    units = concept_data.get(
        "units",
        {}
    )

    results = []

    for unit, facts in units.items():
        if not facts:
            continue

        ordered = sorted(
            facts,
            key=lambda fact: (
                fact.get("end") or "",
                fact.get("filed") or "",
            ),
            reverse=True,
        )

        latest = ordered[0]

        results.append(
            {
                "unit": unit,
                "count": len(facts),
                "latest_end":
                    latest.get("end"),
                "latest_filed":
                    latest.get("filed"),
                "latest_value":
                    latest.get("val"),
                "form":
                    latest.get("form"),
            }
        )

    return results


def print_ticker_concepts(ticker):
    cik = get_current_cik(
        ticker
    )

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
        if matches_search(concept)
    ]

    matching.sort(
        key=lambda item:
            item[0].lower()
    )

    print()
    print("=" * 150)

    print(
        f"{ticker} | CIK {cik}"
    )

    print("=" * 150)

    print(
        f"{'Concept':<70}"
        f"{'Unit':<18}"
        f"{'Rows':>8}"
        f"{'Latest End':>14}"
        f"{'Latest Filed':>14}"
        f"{'Form':>10}"
    )

    print("-" * 150)

    for concept, data in matching:
        unit_info = get_recent_unit_info(
            data
        )

        if not unit_info:
            print(
                f"{concept:<70}"
                f"{'-':<18}"
                f"{0:>8}"
            )

            continue

        first = True

        for info in unit_info:
            display_concept = (
                concept
                if first
                else ""
            )

            print(
                f"{display_concept:<70}"
                f"{info['unit']:<18}"
                f"{info['count']:>8}"
                f"{str(info['latest_end'] or '-'):>14}"
                f"{str(info['latest_filed'] or '-'):>14}"
                f"{str(info['form'] or '-'):>10}"
            )

            first = False


def main():
    print()
    print(
        "RAW XBRL REVENUE / EPS CONCEPT DIAGNOSTIC"
    )

    for ticker in TICKERS:
        print_ticker_concepts(
            ticker
        )


if __name__ == "__main__":
    main()