from datetime import date

from src.company_repository import (
    get_company_by_ticker,
)

from src.xbrl_client import (
    get_company_facts,
    get_concept_values,
    get_quarterly_values,
)


def period_days(value):
    start = value.get("start")
    end = value.get("end")

    if not start or not end:
        return None

    start_date = date.fromisoformat(
        start
    )

    end_date = date.fromisoformat(
        end
    )

    return (
        end_date
        - start_date
    ).days + 1


def get_annual_values(
    facts,
    concept_name,
    unit="USD",
):
    values = get_concept_values(
        facts,
        concept_name,
        unit,
    )

    annual = []

    for value in values:
        if value.get("form") != "10-K":
            continue

        days = period_days(
            value
        )

        if days is None:
            continue

        if not 330 <= days <= 385:
            continue

        annual.append(
            {
                "fy": value.get("fy"),
                "start": value.get("start"),
                "end": value.get("end"),
                "value": value.get("val"),
                "filed": value.get("filed"),
                "accn": value.get("accn"),
                "days": days,
                "concept": concept_name,
            }
        )

    unique = {}

    for value in annual:
        key = (
            value["start"],
            value["end"],
        )

        current = unique.get(
            key
        )

        if (
            current is None
            or value["filed"]
            < current["filed"]
        ):
            unique[key] = value

    return sorted(
        unique.values(),
        key=lambda item:
            item["end"],
    )


def get_reported_quarterly_values(
    facts,
    concept_name,
    unit="USD",
):
    values = get_quarterly_values(
        facts,
        concept_name,
        unit,
    )

    return [
        {
            **value,
            "concept": concept_name,
        }
        for value in values
    ]


def concept_priority(
    concept_name,
    concept_names,
):
    try:
        return concept_names.index(
            concept_name
        )
    except ValueError:
        return len(concept_names)


def choose_period_value(
    current,
    candidate,
    concept_names,
):
    if current is None:
        return candidate

    current_filed = current.get(
        "filed"
    )

    candidate_filed = candidate.get(
        "filed"
    )

    #
    # For backtesting, prefer the value
    # that became public first.
    #
    if (
        candidate_filed is not None
        and (
            current_filed is None
            or candidate_filed
            < current_filed
        )
    ):
        return candidate

    if (
        current_filed is not None
        and candidate_filed is not None
        and candidate_filed
        > current_filed
    ):
        return current

    #
    # If filing dates are equal or missing,
    # use our configured concept preference.
    #
    current_priority = concept_priority(
        current.get("concept"),
        concept_names,
    )

    candidate_priority = concept_priority(
        candidate.get("concept"),
        concept_names,
    )

    if candidate_priority < current_priority:
        return candidate

    return current


def merge_period_values(
    values,
    concept_names,
):
    merged = {}

    for value in values:
        key = (
            value.get("start"),
            value.get("end"),
        )

        merged[key] = choose_period_value(
            merged.get(key),
            value,
            concept_names,
        )

    return sorted(
        merged.values(),
        key=lambda item:
            item["end"],
    )


def normalize_derived_value(
    value,
    unit,
):
    if unit == "USD/shares":
        return round(
            value,
            4,
        )

    return value


def build_multi_concept_quarterly_history(
    facts,
    concept_names,
    unit="USD",
):
    if not concept_names:
        return []

    reported_quarters = []
    annual_values = []

    for concept_name in concept_names:
        reported_quarters.extend(
            get_reported_quarterly_values(
                facts,
                concept_name,
                unit,
            )
        )

        annual_values.extend(
            get_annual_values(
                facts,
                concept_name,
                unit,
            )
        )

    #
    # Merge equivalent periods across
    # all compatible XBRL concepts.
    #
    quarters = merge_period_values(
        reported_quarters,
        concept_names,
    )

    annual = merge_period_values(
        annual_values,
        concept_names,
    )

    result = []

    for quarter in quarters:
        result.append(
            {
                **quarter,
                "derived": False,
            }
        )

    #
    # Derive Q4 only after concepts have
    # been stitched together. This allows
    # Q1/Q2/Q3 to come from one concept
    # while the annual value comes from
    # another compatible concept.
    #
    for year in annual:
        year_start = date.fromisoformat(
            year["start"]
        )

        year_end = date.fromisoformat(
            year["end"]
        )

        year_quarters = []

        for quarter in quarters:
            quarter_start = (
                date.fromisoformat(
                    quarter["start"]
                )
            )

            quarter_end = (
                date.fromisoformat(
                    quarter["end"]
                )
            )

            if (
                quarter_start >= year_start
                and quarter_end <= year_end
            ):
                year_quarters.append(
                    quarter
                )

        year_quarters = sorted(
            year_quarters,
            key=lambda item:
                item["start"],
        )

        if len(year_quarters) != 3:
            continue

        q4_value = (
            year["value"]
            - sum(
                quarter["value"]
                for quarter in year_quarters
            )
        )

        #
        # Preserve the existing behavior:
        # suspicious/non-positive derived
        # values are not emitted.
        #
        if q4_value <= 0:
            continue

        q4_value = normalize_derived_value(
            q4_value,
            unit,
        )

        result.append(
            {
                "fy": year["fy"],
                "fp": "Q4",
                "start": None,
                "end": year["end"],
                "value": q4_value,
                "filed": year["filed"],
                "accn": year["accn"],
                "days": None,
                "derived": True,

                #
                # The annual fact is the
                # source used to derive Q4.
                #
                "concept":
                    year["concept"],
            }
        )

    #
    # Final deduplication also protects
    # against a reported period and derived
    # period landing on the same end date.
    #
    final = {}

    for item in result:
        key = item["end"]

        current = final.get(
            key
        )

        if current is None:
            final[key] = item
            continue

        #
        # Prefer a directly reported quarter
        # over a derived quarter.
        #
        if (
            current.get("derived")
            and not item.get("derived")
        ):
            final[key] = item
            continue

        if (
            not current.get("derived")
            and item.get("derived")
        ):
            continue

        final[key] = choose_period_value(
            current,
            item,
            concept_names,
        )

    return sorted(
        final.values(),
        key=lambda item:
            item["end"],
    )


def build_quarterly_history(
    facts,
    concept_name,
    unit="USD",
):
    #
    # Backward-compatible wrapper for
    # existing callers that use one concept.
    #
    return (
        build_multi_concept_quarterly_history(
            facts,
            [
                concept_name,
            ],
            unit,
        )
    )


if __name__ == "__main__":
    company = get_company_by_ticker(
        "DELL"
    )

    facts = get_company_facts(
        company["cik"]
    )

    history = build_quarterly_history(
        facts,
        "Revenues",
    )

    print(
        f"{company['ticker']} "
        "quarterly revenue"
    )

    print()

    for item in history[-16:]:
        source = (
            "DERIVED"
            if item["derived"]
            else "REPORTED"
        )

        print(
            item["end"],
            "| FY:",
            item["fy"],
            "| FP:",
            item["fp"],
            "| Revenue:",
            (
                f"${item['value'] / 1_000_000_000:.3f}B"
            ),
            "|",
            source,
            "| Concept:",
            item["concept"],
            "| Filed:",
            item["filed"],
        )