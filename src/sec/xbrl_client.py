import json
from datetime import date
from pathlib import Path

import requests

from src.company_repository import (
    get_company_by_ticker,
)

from src.sec.sec_client import SEC_HEADERS


CACHE_DIR = Path(
    "data/cache/sec/companyfacts"
)


def get_cache_path(cik):
    cik = str(cik).zfill(10)

    return (
        CACHE_DIR
        / f"CIK{cik}.json"
    )


def load_cached_company_facts(cik):
    cache_path = get_cache_path(
        cik
    )

    if not cache_path.exists():
        return None

    with cache_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_cached_company_facts(
    cik,
    data,
):
    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_path = get_cache_path(
        cik
    )

    with cache_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
        )


def download_company_facts(cik):
    cik = str(cik).zfill(10)

    url = (
        "https://data.sec.gov/api/xbrl/"
        f"companyfacts/CIK{cik}.json"
    )

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    save_cached_company_facts(
        cik,
        data,
    )

    return data


def get_company_facts(
    cik,
    refresh=False,
):
    cik = str(cik).zfill(10)

    if not refresh:
        cached = (
            load_cached_company_facts(
                cik
            )
        )

        if cached is not None:
            return cached

    return download_company_facts(
        cik
    )


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

    return (
        concept
        .get("units", {})
        .get(unit, [])
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

        days = period_days(
            value
        )

        if days is None:
            continue

        #
        # Standalone quarters are
        # approximately three months.
        #
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

    #
    # Later filings can repeat prior
    # quarterly values.
    #
    # Keep the earliest filing for each
    # actual period so backtests use the
    # date the information first became
    # public.
    #
    unique = {}

    for value in quarterly:
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


if __name__ == "__main__":
    company = (
        get_company_by_ticker(
            "DELL"
        )
    )

    facts = get_company_facts(
        company["cik"]
    )

    print(
        "Company:",
        facts["entityName"],
    )

    print(
        "CIK:",
        facts["cik"],
    )

    print()
    print(
        "Available taxonomies:"
    )

    for taxonomy in facts["facts"]:
        print(
            taxonomy
        )