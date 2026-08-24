from datetime import date

from src.company_repository import get_company_by_ticker
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

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    return (end_date - start_date).days + 1


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

        days = period_days(value)

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
            }
        )

    unique = {}

    for value in annual:
        key = (
            value["start"],
            value["end"],
        )

        current = unique.get(key)

        if (
            current is None
            or value["filed"] < current["filed"]
        ):
            unique[key] = value

    return sorted(
        unique.values(),
        key=lambda item: item["end"],
    )


def normalize_derived_value(value, unit):
    if unit == "USD/shares":
        return round(value, 4)

    return value


def build_quarterly_history(
    facts,
    concept_name,
    unit="USD",
):
    quarters = get_quarterly_values(
        facts,
        concept_name,
        unit,
    )

    annual = get_annual_values(
        facts,
        concept_name,
        unit,
    )

    result = []

    for quarter in quarters:
        result.append(
            {
                **quarter,
                "derived": False,
            }
        )

    for year in annual:
        year_start = date.fromisoformat(
            year["start"]
        )

        year_end = date.fromisoformat(
            year["end"]
        )

        year_quarters = []

        for quarter in quarters:
            quarter_start = date.fromisoformat(
                quarter["start"]
            )

            quarter_end = date.fromisoformat(
                quarter["end"]
            )

            if (
                quarter_start >= year_start
                and quarter_end <= year_end
            ):
                year_quarters.append(quarter)

        year_quarters = sorted(
            year_quarters,
            key=lambda q: q["start"],
        )

        if len(year_quarters) != 3:
            continue

        q4_value = (
            year["value"]
            - sum(
                q["value"]
                for q in year_quarters
            )
        )

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
            }
        )

    return sorted(
        result,
        key=lambda item: item["end"],
    )


if __name__ == "__main__":
    company = get_company_by_ticker("DELL")

    facts = get_company_facts(
        company["cik"]
    )

    history = build_quarterly_history(
        facts,
        "Revenues",
    )

    print(
        f"{company['ticker']} quarterly revenue"
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
            f"${item['value'] / 1_000_000_000:.3f}B",
            "|",
            source,
            "| Filed:",
            item["filed"],
        )