import sys

from datetime import date

from src.universe.company_universe import (
    get_company,
)

from src.xbrl_client import (
    get_company_facts,
)

from src.time_split_statistics import DEFAULT_UNIVERSE


TESTS = [
    {
        "ticker": "BRK-B",
        "metric": "diluted_eps",
        "terms": [
            "earningspershare",
            "diluted",
            "eps",
        ],
    },
    {
        "ticker": "V",
        "metric": "diluted_eps",
        "terms": [
            "earningspershare",
            "diluted",
            "eps",
        ],
    },
    {
        "ticker": "GS",
        "metric": "revenue",
        "terms": [
            "revenuesnetofinterestexpense",
            "revenue",
        ],
    },
]


def period_days(value):
    start = value.get("start")
    end = value.get("end")

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


def get_all_namespaces(facts):
    return (
        facts
        .get("facts", {})
    )


def find_concepts(
    facts,
    terms,
):
    namespaces = (
        get_all_namespaces(
            facts
        )
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
                term.lower()
                in searchable
                for term in terms
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

                    "description":
                        concept_data.get(
                            "description"
                        ),

                    "units":
                        concept_data.get(
                            "units",
                            {},
                        ),
                }
            )

    return results


def summarize_unit_values(
    values,
):
    dates = [
        value.get("end")
        for value in values
        if value.get("end")
    ]

    forms = sorted(
        {
            value.get("form")
            for value in values
            if value.get("form")
        }
    )

    durations = []

    for value in values:
        days = period_days(
            value
        )

        if days is not None:
            durations.append(
                days
            )

    return {
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

        "min_days":
            min(durations)
            if durations
            else None,

        "max_days":
            max(durations)
            if durations
            else None,
    }


def print_concept(
    result,
):
    print()
    print(
        f"{result['namespace']}:"
        f"{result['concept']}"
    )

    print(
        "  Label:",
        result["label"],
    )

    if result["description"]:
        print(
            "  Description:",
            result["description"],
        )

    for unit_name, values in (
        result["units"].items()
    ):
        summary = (
            summarize_unit_values(
                values
            )
        )

        print(
            f"  Unit: {unit_name}"
        )

        print(
            "    Records:",
            summary["records"],
        )

        print(
            "    Earliest:",
            summary["earliest"],
        )

        print(
            "    Latest:",
            summary["latest"],
        )

        print(
            "    Forms:",
            ", ".join(
                summary["forms"]
            ),
        )

        print(
            "    Duration range:",
            summary["min_days"],
            "to",
            summary["max_days"],
        )

        #
        # Show the latest 12 raw values
        # so we can inspect FY/FP/start/end.
        #
        recent = sorted(
            values,
            key=lambda item:
                (
                    item.get("end")
                    or "",
                    item.get("filed")
                    or "",
                ),
        )[-12:]

        print(
            "    Latest raw records:"
        )

        for value in recent:
            print(
                "     ",
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
    test,
    universe_name=DEFAULT_UNIVERSE,
):
    ticker = test[
        "ticker"
    ]

    metric = test[
        "metric"
    ]

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

    results = find_concepts(
        facts,
        test["terms"],
    )

    print()
    print("=" * 130)

    print(
        ticker,
        "-",
        company["company_name"],
    )

    print(
        "Metric:",
        metric,
    )

    print(
        "CIK:",
        company["cik"],
    )

    print(
        "Namespaces:",
        ", ".join(
            sorted(
                get_all_namespaces(
                    facts
                ).keys()
            )
        ),
    )

    print(
        "Matching concepts:",
        len(results),
    )

    for result in results:
        print_concept(
            result
        )


def main():
    universe_name = (
        sys.argv[1]
        if len(sys.argv) >= 2
        else DEFAULT_UNIVERSE
    )

    print()
    print(
        "DEEP REQUIRED-METRIC "
        "DIAGNOSTICS"
    )

    print(
        "Universe:",
        universe_name,
    )

    for test in TESTS:
        diagnose(
            test,
            universe_name,
        )


if __name__ == "__main__":
    main()