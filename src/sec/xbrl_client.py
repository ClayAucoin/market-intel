import json
from datetime import date
from pathlib import Path

from src.data.company_repository import (
    get_company_by_ticker,
)

from src.sec.sec_http import get_sec_json


CACHE_DIR = Path(
    "data/cache/sec/companyfacts"
)


DEFAULT_TAXONOMIES = [
    "us-gaap",
    "ifrs-full",
]


QUARTERLY_FORMS = {
    "10-Q",
    "10-Q/A",
    "6-K",
    "6-K/A",
}


ANNUAL_FORMS = {
    "10-K",
    "10-K/A",
    "20-F",
    "20-F/A",
    "40-F",
    "40-F/A",
}


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

    data = get_sec_json(url)

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


class ProductionCompanyFacts:
    """One refreshed payload (or remembered failure) per CIK per invocation."""
    def __init__(self):
        self.payloads = {}
        self.failures = {}

    def __call__(self, cik):
        cik = str(cik).zfill(10)
        if cik in self.failures:
            raise RuntimeError(f"Company Facts production refresh already failed for CIK {cik}")
        if cik not in self.payloads:
            try:
                try:
                    previous = load_cached_company_facts(cik)
                except (OSError, ValueError):
                    previous = None
                data = get_company_facts(cik, refresh=True)
                if (not isinstance(data, dict) or not isinstance(data.get("facts"), dict)
                        or str(data.get("cik", "")).zfill(10) != cik):
                    raise ValueError(f"Invalid Company Facts payload for CIK {cik}")
                self.payloads[cik] = data
                content = "unchanged" if previous == data else "changed/new"
                print(f"Company Facts HTTP refresh succeeded: CIK {cik}; content {content}")
            except Exception:
                self.failures[cik] = True
                raise
        return self.payloads[cik]


def find_concept(
    facts,
    concept_name,
    taxonomies=None,
):
    if taxonomies is None:
        taxonomies = DEFAULT_TAXONOMIES

    all_facts = facts.get(
        "facts",
        {},
    )

    for taxonomy in taxonomies:
        taxonomy_facts = (
            all_facts.get(
                taxonomy,
                {},
            )
        )

        concept = (
            taxonomy_facts.get(
                concept_name
            )
        )

        if concept is not None:
            return {
                "taxonomy":
                    taxonomy,

                "concept":
                    concept,
            }

    return None


def get_available_units(
    facts,
    concept_name,
    taxonomies=None,
):
    result = find_concept(
        facts,
        concept_name,
        taxonomies,
    )

    if result is None:
        return []

    return list(
        result[
            "concept"
        ]
        .get(
            "units",
            {},
        )
        .keys()
    )


def get_concept_values(
    facts,
    concept_name,
    unit="USD",
    taxonomies=None,
):
    result = find_concept(
        facts,
        concept_name,
        taxonomies,
    )

    if result is None:
        return []

    concept = result[
        "concept"
    ]

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
    taxonomies=None,
):
    values = get_concept_values(
        facts,
        concept_name,
        unit,
        taxonomies,
    )

    quarterly = []

    for value in values:
        if (
            value.get("form")
            not in QUARTERLY_FORMS
        ):
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
                "form": value.get("form"),
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
            or (
                value.get("filed")
                is not None
                and (
                    current.get("filed")
                    is None
                    or value["filed"]
                    < current["filed"]
                )
            )
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
