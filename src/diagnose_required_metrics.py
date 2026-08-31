import sys

from src.universe.company_universe import (
    get_company,
)

from src.financials.financial_metrics import (
    FINANCIAL_METRICS,
    get_metric_history,
)

from src.sec.xbrl_client import (
    get_company_facts,
)

from src.time_split_statistics import DEFAULT_UNIVERSE


TICKERS = [
    "BRK-B",
    "GS",
    "V",
]


SEARCH_TERMS = {
    "revenue": [
        "revenue",
        "sales",
        "interestincome",
        "noninterestincome",
    ],

    "net_income": [
        "netincome",
        "profitloss",
        "profit",
        "income",
    ],

    "diluted_eps": [
        "earningspershare",
        "eps",
    ],
}


def get_required_failures(
    ticker,
):
    failures = []

    for metric_name, config in (
        FINANCIAL_METRICS.items()
    ):
        if config.get("availability") != "core":
            continue

        result = get_metric_history(
            ticker,
            metric_name,
        )

        if not result["history"]:
            failures.append(
                metric_name
            )

    return failures


def find_candidate_concepts(
    facts,
    metric_name,
):
    terms = SEARCH_TERMS[
        metric_name
    ]

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
            for term in terms
        ):
            continue

        units = (
            concept_data
            .get("units", {})
        )

        candidate_units = []

        for unit_name, values in (
            units.items()
        ):
            if not values:
                continue

            dates = [
                item.get("end")
                for item in values
                if item.get("end")
            ]

            forms = sorted(
                {
                    item.get("form")
                    for item in values
                    if item.get("form")
                }
            )

            candidate_units.append(
                {
                    "unit":
                        unit_name,

                    "records":
                        len(values),

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

        if not candidate_units:
            continue

        results.append(
            {
                "concept":
                    concept_name,

                "label":
                    concept_data.get(
                        "label"
                    ),

                "units":
                    candidate_units,
            }
        )

    return results


def print_candidates(
    facts,
    metric_name,
):
    candidates = (
        find_candidate_concepts(
            facts,
            metric_name,
        )
    )

    print()
    print(
        f"Candidate concepts for "
        f"{metric_name}"
    )

    print("-" * 120)

    if not candidates:
        print(
            "No matching concepts found."
        )

        return

    for candidate in candidates:
        print(
            candidate["concept"]
        )

        print(
            "  Label:",
            candidate["label"],
        )

        for unit in candidate[
            "units"
        ]:
            print(
                "  "
                f"Unit: {unit['unit']} | "
                f"Records: "
                f"{unit['records']} | "
                f"Earliest: "
                f"{unit['earliest']} | "
                f"Latest: "
                f"{unit['latest']} | "
                f"Forms: "
                f"{', '.join(unit['forms'])}"
            )

        print()


def diagnose_ticker(
    ticker,
    universe_name=DEFAULT_UNIVERSE,
):
    company = get_company(
        ticker,
        universe_name,
    )

    if company is None:
        raise ValueError(
            f"{ticker} not found "
            f"in {universe_name}"
        )

    print()
    print("=" * 120)

    print(
        f"{ticker} - "
        f"{company['company_name']}"
    )

    print(
        f"Sector: "
        f"{company['sector']}"
    )

    print(
        f"CIK: "
        f"{company['cik']}"
    )

    failures = (
        get_required_failures(
            ticker
        )
    )

    print()
    print(
        "Missing required metrics:",
        (
            ", ".join(failures)
            if failures
            else "None"
        ),
    )

    if not failures:
        return

    facts = get_company_facts(
        company["cik"]
    )

    for metric_name in failures:
        print_candidates(
            facts,
            metric_name,
        )


def main():
    universe_name = (
        sys.argv[1]
        if len(sys.argv) >= 2
        else DEFAULT_UNIVERSE
    )

    print()
    print(
        "REQUIRED METRIC "
        "DIAGNOSTICS"
    )

    print(
        "Universe:",
        universe_name,
    )

    for ticker in TICKERS:
        diagnose_ticker(
            ticker,
            universe_name,
        )


if __name__ == "__main__":
    main()