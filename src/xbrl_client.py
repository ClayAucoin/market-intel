from datetime import date

import requests

from src.company_repository import get_company_by_ticker
from src.sec_client import SEC_HEADERS


def get_company_facts(cik):
    cik = str(cik).zfill(10)

    url = (
        "https://data.sec.gov/api/xbrl/"
        f"companyfacts/CIK{cik}.json"
    )

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def get_concept_values(
    facts,
    concept_name,
    unit="USD",
):
    concept = (
        facts
        .get("facts", {})
        .get("us-gaap", {})
        .get(concept_name)
    )

    if concept is None:
        return []

    return concept.get(
        "units",
        {}
    ).get(unit, [])


def period_days(value):
    start = value.get("start")
    end = value.get("end")

    if not start or not end:
        return None

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    return (end_date - start_date).days + 1


def get_quarterly_values(
    facts,
    concept_name,
    unit="USD",
):
    values = get_concept_values(
        facts,
        concept_name,
        unit,
    )

    quarterly = []

    for value in values:
        if value.get("form") != "10-Q":
            continue

        days = period_days(value)

        if days is None:
            continue

        # Normal standalone quarters are roughly 3 months.
        # Allow some flexibility for 52/53-week fiscal calendars.
        if not 70 <= days <= 110:
            continue

        quarterly.append(
            {
                "fy": value.get("fy"),
                "fp": value.get("fp"),
                "start": value.get("start"),
                "end": value.get("end"),
                "value": value.get("val"),
                "filed": value.get("filed"),
                "accn": value.get("accn"),
                "days": days,
            }
        )

    # The same reporting period can be repeated in later filings.
    # Keep the earliest filing for each actual start/end period,
    # representing when the value first became public.
    unique = {}

    for value in quarterly:
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


if __name__ == "__main__":
    company = get_company_by_ticker("DELL")

    facts = get_company_facts(
        company["cik"]
    )

    quarters = get_quarterly_values(
        facts,
        "Revenues",
    )

    print(
        f"{company['ticker']} quarterly revenue"
    )

    print()

    for quarter in quarters[-12:]:
        print(
            quarter["start"],
            "to",
            quarter["end"],
            "| FY:",
            quarter["fy"],
            "| FP:",
            quarter["fp"],
            "| Revenue:",
            f"${quarter['value'] / 1_000_000_000:.3f}B",
            "| Filed:",
            quarter["filed"],
        )