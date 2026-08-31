import sys

from datetime import date

from src.universe.company_universe import (
    get_company,
)

from src.sec.xbrl_client import (
    get_company_facts,
)

from src.time_split_statistics import DEFAULT_UNIVERSE

TICKERS = [
    "BRK-B",
    "V",
]


SEARCH_TERMS = [
    "weightedaveragenumberof",
    "dilutedshares",
    "sharesoutstanding",
    "netincomeloss",
    "profitloss",
]


def period_days(record):
    start = record.get("start")
    end = record.get("end")

    if not start or not end:
        return None

    try:
        start_date = date.fromisoformat(
            start
        )

        end_date = date.fromisoformat(
            end
        )

    except ValueError:
        return None

    return (
        end_date
        - start_date
    ).days + 1


def find_concepts(facts):
    namespaces = facts.get(
        "facts",
        {}
    )

    results = []

    for namespace, concepts in (
        namespaces.items()
    ):
        for concept_name, concept_data in (
            concepts.items()
        ):
            searchable = (
                f"{concept_name} "
                f"{concept_data.get('label', '')} "
                f"{concept_data.get('description', '')}"
            ).lower()

            if not any(
                term in searchable
                for term in SEARCH_TERMS
            ):
                continue

            results.append(
                {
                    "namespace":
                        namespace,

                    "concept":
                        concept_name,

                    "label":
                        concept_data.get(
                            "label"
                        ),

                    "units":
                        concept_data.get(
                            "units",
                            {},
                        ),
                }
            )

    return results


def print_latest_records(
    unit_name,
    values,
):
    recent = sorted(
        values,
        key=lambda item: (
            item.get("end") or "",
            item.get("filed") or "",
        ),
    )[-16:]

    print(
        f"  Unit: {unit_name}"
    )

    print(
        f"  Records: {len(values)}"
    )

    print(
        "  Latest raw records:"
    )

    for value in recent:
        print(
            "   ",
            "FY:",
            value.get("fy"),
            "| FP:",
            value.get("fp"),
            "| Form:",
            value.get("form"),
            "| Start:",
            value.get("start"),
            "| End:",
            value.get("end"),
            "| Days:",
            period_days(value),
            "| Value:",
            value.get("val"),
            "| Filed:",
            value.get("filed"),
            "| Accn:",
            value.get("accn"),
        )


def diagnose(
    ticker,
    universe_name=DEFAULT_UNIVERSE,
):
    company = get_company(
        ticker,
        universe_name,
    )

    if company is None:
        raise ValueError(
            f"{ticker} not found in "
            f"{universe_name}"
        )

    facts = get_company_facts(
        company["cik"]
    )

    concepts = find_concepts(
        facts
    )

    print()
    print("=" * 130)

    print(
        f"{ticker} - "
        f"{company['company_name']}"
    )

    print(
        "CIK:",
        company["cik"],
    )

    print(
        "Matching concepts:",
        len(concepts),
    )

    for item in concepts:
        print()
        print(
            f"{item['namespace']}:"
            f"{item['concept']}"
        )

        print(
            "  Label:",
            item["label"],
        )

        for unit_name, values in (
            item["units"].items()
        ):
            print_latest_records(
                unit_name,
                values,
            )


def main():
    universe_name = (
        sys.argv[1]
        if len(sys.argv) >= 2
        else DEFAULT_UNIVERSE
    )

    print()
    print(
        "EPS DERIVATION DIAGNOSTICS"
    )

    print(
        "Universe:",
        universe_name,
    )

    for ticker in TICKERS:
        diagnose(
            ticker,
            universe_name,
        )


if __name__ == "__main__":
    main()