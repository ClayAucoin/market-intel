import json
from datetime import date
from pathlib import Path

from src.sec.sec_http import get_sec_json


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
    data = get_sec_json(url)

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


class ProductionSubmissions:
    """Refresh main JSON once; recover only history shards needed by accessions."""
    def __init__(self):
        self.main = {}
        self.failures = set()
        self.history = {}
        self.downloaded_history = set()

    def _main(self, cik):
        cik = str(cik).zfill(10)
        if cik in self.failures:
            raise RuntimeError(f"Submissions production refresh already failed for CIK {cik}")
        if cik not in self.main:
            try:
                try:
                    previous = load_json(get_main_cache_path(cik))
                except (OSError, ValueError):
                    previous = None
                data = get_company_submissions(cik, refresh=True)
                if (not isinstance(data, dict) or str(data.get("cik", "")).zfill(10) != cik
                        or not isinstance(data.get("filings"), dict)
                        or not isinstance(data["filings"].get("recent"), dict)
                        or not isinstance(data["filings"]["recent"].get("accessionNumber"), list)
                        or not isinstance(data["filings"].get("files", []), list)):
                    raise ValueError(f"Invalid submissions payload for CIK {cik}")
                self.main[cik] = data
                content = "unchanged" if previous == data else "changed/new"
                print(f"Submissions HTTP refresh succeeded: CIK {cik}; content {content}")
            except Exception:
                self.failures.add(cik)
                raise
        return self.main[cik]

    def _history(self, filename, refresh=False):
        if refresh or filename not in self.history:
            data = None if refresh else load_json(get_history_cache_path(filename))
            if data is None:
                data = get_historical_submissions(filename, refresh=True)
                self.downloaded_history.add(filename)
            if not isinstance(data, dict) or not isinstance(data.get("accessionNumber"), list):
                raise ValueError(f"Invalid historical submissions payload: {filename}")
            self.history[filename] = data
        return self.history[filename]

    def __call__(self, cik, required_dates):
        """required_dates maps each accession to its known fact filing dates."""
        filings = self._main(cik)["filings"]
        records = {r["accessionNumber"]: r for r in columnar_to_records(filings["recent"])
                   if r.get("accessionNumber")}

        def relevant(shard):
            start = parse_date(shard.get("filingFrom"))
            end = parse_date(shard.get("filingTo"))
            return any(ranges_overlap(start, end, filed, filed)
                       for accession, dates in required_dates.items() if accession not in records
                       for filed in (dates or {None}))

        def merge(data):
            for record in columnar_to_records(data):
                accession = record.get("accessionNumber")
                if accession:
                    # Fresh recent metadata takes precedence over repeated history.
                    records.setdefault(accession, record)

        shards = filings.get("files", [])
        for shard in shards:
            if shard.get("name") and relevant(shard):
                merge(self._history(shard["name"]))
        # Only still-missing accessions justify refreshing previously cached shards.
        for shard in shards:
            filename = shard.get("name")
            if filename and filename not in self.downloaded_history and relevant(shard):
                merge(self._history(filename, refresh=True))
        missing = set(required_dates) - records.keys()
        if missing:
            raise ValueError(f"Incomplete production submissions for CIK {cik}: "
                             f"unresolved accessions {', '.join(sorted(missing))}")
        return list(records.values())
