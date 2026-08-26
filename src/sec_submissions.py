import json
from datetime import date
from pathlib import Path

import requests

from src.sec_client import SEC_HEADERS


BASE_URL = (
    "https://data.sec.gov/submissions"
)

CACHE_DIR = Path(
    "data/cache/sec/submissions"
)


def get_main_cache_path(cik):
    cik = str(cik).zfill(10)

    return (
        CACHE_DIR
        / f"CIK{cik}.json"
    )


def get_history_cache_path(
    filename,
):
    return (
        CACHE_DIR
        / filename
    )


def save_json(
    path,
    data,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
        )


def load_json(path):
    if not path.exists():
        return None

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def download_json(
    url,
    cache_path,
):
    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    save_json(
        cache_path,
        data,
    )

    return data


def get_company_submissions(
    cik,
    refresh=False,
):
    cik = str(cik).zfill(10)

    cache_path = (
        get_main_cache_path(
            cik
        )
    )

    if not refresh:
        cached = load_json(
            cache_path
        )

        if cached is not None:
            return cached

    print(
        f"Downloading SEC submissions "
        f"for CIK {cik}..."
    )

    url = (
        f"{BASE_URL}/"
        f"CIK{cik}.json"
    )

    return download_json(
        url,
        cache_path,
    )


def get_historical_submissions(
    filename,
    refresh=False,
):
    cache_path = (
        get_history_cache_path(
            filename
        )
    )

    if not refresh:
        cached = load_json(
            cache_path
        )

        if cached is not None:
            return cached

    print(
        f"Downloading SEC history "
        f"{filename}..."
    )

    url = (
        f"{BASE_URL}/"
        f"{filename}"
    )

    return download_json(
        url,
        cache_path,
    )


def parse_date(value):
    if not value:
        return None

    return date.fromisoformat(
        value
    )


def ranges_overlap(
    first_start,
    first_end,
    second_start,
    second_end,
):
    if (
        first_start is None
        or first_end is None
        or second_start is None
        or second_end is None
    ):
        return True

    return not (
        first_end < second_start
        or first_start > second_end
    )


def columnar_to_records(
    data,
):
    accession_numbers = (
        data.get(
            "accessionNumber",
            []
        )
    )

    records = []

    for index in range(
        len(accession_numbers)
    ):
        record = {}

        for key, values in (
            data.items()
        ):
            if not isinstance(
                values,
                list,
            ):
                continue

            if index >= len(values):
                record[key] = None
                continue

            record[key] = (
                values[index]
            )

        records.append(
            record
        )

    return records


def get_submission_records(
    cik,
    start_date=None,
    end_date=None,
    refresh=False,
):
    data = get_company_submissions(
        cik,
        refresh=refresh,
    )

    filings = data.get(
        "filings",
        {}
    )

    recent = filings.get(
        "recent",
        {}
    )

    records = (
        columnar_to_records(
            recent
        )
    )

    history_files = filings.get(
        "files",
        []
    )

    for history_file in history_files:
        filename = (
            history_file.get(
                "name"
            )
        )

        if not filename:
            continue

        file_start = parse_date(
            history_file.get(
                "filingFrom"
            )
        )

        file_end = parse_date(
            history_file.get(
                "filingTo"
            )
        )

        if not ranges_overlap(
            file_start,
            file_end,
            start_date,
            end_date,
        ):
            continue

        history_data = (
            get_historical_submissions(
                filename,
                refresh=refresh,
            )
        )

        #
        # Historical files themselves are
        # columnar filing records rather than
        # another full company wrapper.
        #
        history_records = (
            columnar_to_records(
                history_data
            )
        )

        records.extend(
            history_records
        )

    #
    # Deduplicate by accession number.
    #
    unique = {}

    for record in records:
        accession = (
            record.get(
                "accessionNumber"
            )
        )

        if not accession:
            continue

        unique[accession] = record

    return list(
        unique.values()
    )