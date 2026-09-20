import argparse
import sys

from src.sec.production_requirements import get_production_requirements
from src.sec import production_report as reporting

from datetime import (
    datetime,
)
from zoneinfo import ZoneInfo

from src.universe.company_universe import (
    DEFAULT_UNIVERSE,
)

from src.database import (
    get_connection,
)

from src.sec.sec_submissions import (
    get_submission_records,
    ProductionSubmissions,
)


EASTERN = ZoneInfo(
    "America/New_York"
)


def parse_date(value):
    if not value:
        return None

    return datetime.strptime(
        value,
        "%Y-%m-%d",
    ).date()


def parse_acceptance_datetime(
    value,
):
    if not value:
        return None

    #
    # SEC acceptance timestamps represent
    # the EDGAR acceptance clock time.
    #
    # Keep the first YYYY-MM-DDTHH:MM:SS
    # portion and explicitly interpret it
    # as Eastern time.
    #
    text = value[:19]

    parsed = datetime.strptime(
        text,
        "%Y-%m-%dT%H:%M:%S",
    )

    return parsed.replace(
        tzinfo=EASTERN
    )


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


def get_target_issuers(
    universe_name,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.id,
                    c.cik,
                    c.company_name,

                    MIN(ff.filed_date),
                    MAX(ff.filed_date),

                    COUNT(
                        DISTINCT
                        ff.accession_number
                    )

                FROM financial_facts ff

                JOIN companies c
                    ON c.id =
                       ff.company_id

                JOIN analysis_universe_members aum
                    ON aum.security_id =
                       ff.security_id

                JOIN analysis_universes au
                    ON au.id =
                       aum.universe_id

                WHERE
                    au.name = %s

                    AND ff.accession_number
                        IS NOT NULL

                GROUP BY
                    c.id,
                    c.cik,
                    c.company_name

                ORDER BY
                    c.company_name;
                """,
                (
                    universe_name,
                ),
            )

            rows = cursor.fetchall()

    return [
        {
            "company_id": row[0],
            "cik": row[1],
            "company_name": row[2],
            "earliest": row[3],
            "latest": row[4],
            "accessions": row[5],
        }
        for row in rows
    ]


def get_production_issuers(universe_name):
    # Match the Company Facts call graph even when an issuer has no metric rows.
    from src.financials.financial_metrics import (
        get_company_by_ticker, get_issuer_history_by_ticker,
    )
    from src.universe.company_universe import get_companies

    issuers = {}
    for security in get_companies(universe_name):
        ticker = security["ticker"]
        history = get_issuer_history_by_ticker(ticker)
        if not history:
            company = get_company_by_ticker(ticker)
            if company is None:
                raise ValueError("Production security lacks issuer identity")
            history = [dict(company_id=company["id"], cik=company["cik"],
                            company_name=company["company_name"])]
        for issuer in history:
            issuers[issuer["company_id"]] = {**issuer, "accessions": 0}
    return list(issuers.values())


def get_target_accessions(
    company_id,
    universe_name,
    include_dates=False,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    ff.accession_number, ff.filed_date

                FROM financial_facts ff

                JOIN analysis_universe_members aum
                    ON aum.security_id =
                       ff.security_id

                JOIN analysis_universes au
                    ON au.id =
                       aum.universe_id

                WHERE
                    ff.company_id = %s

                    AND au.name = %s

                    AND ff.accession_number
                        IS NOT NULL

                ORDER BY
                    ff.accession_number;
                """,
                (
                    company_id,
                    universe_name,
                ),
            )

            rows = cursor.fetchall()

    if include_dates:
        dates = {}
        for accession, filed_date in rows:
            dates.setdefault(accession, set()).add(filed_date)
        return dates
    return {row[0] for row in rows}


def build_filing_url(
    cik,
    accession_number,
    primary_document,
):
    if not primary_document:
        return None

    numeric_cik = str(
        int(cik)
    )

    accession_path = (
        accession_number
        .replace("-", "")
    )

    return (
        "https://www.sec.gov/"
        "Archives/edgar/data/"
        f"{numeric_cik}/"
        f"{accession_path}/"
        f"{primary_document}"
    )


def save_filing(
    company_id,
    cik,
    record,
):
    accession_number = record.get(
        "accessionNumber"
    )

    filing_date = parse_date(
        record.get(
            "filingDate"
        )
    )

    report_date = parse_date(
        record.get(
            "reportDate"
        )
    )

    acceptance_datetime = (
        parse_acceptance_datetime(
            record.get(
                "acceptanceDateTime"
            )
        )
    )

    form = (
        record.get("form")
        or "UNKNOWN"
    )

    primary_document = (
        record.get(
            "primaryDocument"
        )
    )

    description = (
        record.get(
            "primaryDocDescription"
        )
    )

    filing_url = build_filing_url(
        cik,
        accession_number,
        primary_document,
    )

    if filing_date is None:
        return False

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO filings (
                    company_id,
                    accession_number,
                    form,
                    filing_date,
                    report_date,
                    acceptance_datetime,
                    primary_document,
                    primary_doc_description,
                    filing_url
                )

                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )

                ON CONFLICT (
                    accession_number
                )

                DO UPDATE SET
                    company_id =
                        EXCLUDED.company_id,

                    form =
                        EXCLUDED.form,

                    filing_date =
                        EXCLUDED.filing_date,

                    report_date =
                        EXCLUDED.report_date,

                    acceptance_datetime =
                        EXCLUDED.acceptance_datetime,

                    primary_document =
                        EXCLUDED.primary_document,

                    primary_doc_description =
                        EXCLUDED.primary_doc_description,

                    filing_url =
                        EXCLUDED.filing_url;
                """,
                (
                    company_id,
                    accession_number,
                    form,
                    filing_date,
                    report_date,
                    acceptance_datetime,
                    primary_document,
                    description,
                    filing_url,
                ),
            )

    return True


def valid_filing_metadata(record):
    """Validate before optional persistence; absent metadata is a coverage gap."""
    try:
        if (not record.get("accessionNumber") or parse_date(record.get("filingDate")) is None
                or parse_acceptance_datetime(record.get("acceptanceDateTime")) is None):
            return False
        parse_date(record.get("reportDate"))
    except (ValueError, TypeError):
        return False
    return True


def import_production_issuer_filings(issuer, universe_name, submissions_loader):
    required, stored, gaps = get_production_requirements(issuer["company_id"], universe_name)
    # Together these sets cover the fact-linked accessions read by the
    # requirements query, including every metric and non-current source.
    targets = set(required) | set(stored) | set(gaps)
    covered = set(stored)
    counts = dict(targeted=len(targets), available=0, reused=len(stored), persisted=0,
                  unresolved=len(targets - covered), complete=False)

    def report_coverage():
        counts["unresolved"] = len(targets - covered)
        reporting.filing_coverage(issuer["cik"], counts, targets - covered - set(required))

    report_coverage()
    # Only mandatory missing metadata can trigger historical-shard recovery.
    records = submissions_loader(issuer["cik"],
                                 {a: dates for a, dates in required.items() if a not in stored})
    available = {r["accessionNumber"]: r for r in records
                 if r.get("accessionNumber") in targets and valid_filing_metadata(r)}
    counts["available"] = len(available)
    reporting.unresolved(issuer["cik"], set(required) - covered)
    report_coverage()
    for accession, record in sorted(available.items()):
        if accession in covered:
            continue  # Reuse valid stored identity/timing without sparse overwrites.
        if not save_filing(issuer["company_id"], issuer["cik"], record):
            raise ValueError(f"Validated fact-linked filing was not saved: {accession}")
        covered.add(accession)
        counts["persisted"] += 1
        reporting.unresolved(issuer["cik"], set(required) - covered)
        report_coverage()

    missing = set(required) - covered
    if missing:
        raise ValueError(f"Required filing metadata incomplete: {', '.join(sorted(missing))}")
    counts["complete"] = True
    report_coverage()
    print(f"CIK {issuer['cik']}: required {len(required)}; fact-linked {len(targets)}; "
          f"persisted {counts['persisted']}; reused {counts['reused']}; "
          f"non-current coverage gaps {counts['unresolved']}")
    return dict(company_name=issuer["company_name"], cik=issuer["cik"],
                target=len(required), matched=len(required), missing=0)


def import_issuer_filings(
    issuer,
    universe_name,
    submissions_loader=None,
):
    if submissions_loader is not None:
        return import_production_issuer_filings(issuer, universe_name, submissions_loader)
    target_accessions = get_target_accessions(issuer["company_id"], universe_name)

    print()
    print(
        issuer["company_name"]
    )

    print(
        f"CIK: {issuer['cik']}"
    )

    print(
        f"Target accessions: "
        f"{len(target_accessions)}"
    )

    records = get_submission_records(
        issuer["cik"], start_date=issuer["earliest"], end_date=issuer["latest"], refresh=False,
    )

    records_by_accession = {
        record.get(
            "accessionNumber"
        ): record
        for record in records
        if record.get(
            "accessionNumber"
        )
    }

    matched = 0
    missing = []

    for accession in sorted(
        target_accessions
    ):
        record = records_by_accession.get(
            accession
        )

        if record is None:
            missing.append(
                accession
            )
            continue

        if save_filing(
            issuer["company_id"],
            issuer["cik"],
            record,
        ):
            matched += 1

    print(
        f"Matched: {matched}"
    )

    print(
        f"Missing: {len(missing)}"
    )

    if missing:
        print(
            "Missing accessions:"
        )

        for accession in missing:
            print(
                f"  {accession}"
            )

    return {
        "company_name":
            issuer["company_name"],

        "cik":
            issuer["cik"],

        "target":
            len(target_accessions),

        "matched":
            matched,

        "missing":
            len(missing),
    }


def import_universe(universe_name, production_refresh=False):
    submissions_loader = ProductionSubmissions() if production_refresh else None
    failures = 0

    issuers = (get_production_issuers(universe_name) if production_refresh
               else get_target_issuers(universe_name))

    if not issuers:
        raise ValueError(
            f"No filing targets found "
            f"for universe: "
            f"{universe_name}"
        )

    results = []

    print()
    print(
        "MARKET INTEL "
        "UNIVERSE FILING IMPORT"
    )

    print(
        "Universe:",
        universe_name,
    )

    print("=" * 72)

    for issuer in issuers:
        try:
            result = (
                import_issuer_filings(
                    issuer,
                    universe_name,
                    submissions_loader=submissions_loader,
                )
            )

        except Exception as error:
            reporting.failure("submissions", error, cik=issuer["cik"])
            failures += 1
            print(
                f"ERROR: {error}"
            )

            result = {
                "company_name":
                    issuer[
                        "company_name"
                    ],

                "cik":
                    issuer["cik"],

                "target":
                    issuer[
                        "accessions"
                    ],

                "matched":
                    0,

                "missing":
                    issuer[
                        "accessions"
                    ],
            }

        results.append(
            result
        )

    print()
    print("=" * 72)

    print(
        "IMPORT SUMMARY"
    )

    print()

    print(
        f"{'CIK':<12}"
        f"{'Target':>10}"
        f"{'Matched':>10}"
        f"{'Missing':>10}  "
        f"{'Company'}"
    )

    print("-" * 72)

    total_target = 0
    total_matched = 0
    total_missing = 0

    for result in results:
        print(
            f"{result['cik']:<12}"
            f"{result['target']:>10}"
            f"{result['matched']:>10}"
            f"{result['missing']:>10}  "
            f"{result['company_name']}"
        )

        total_target += (
            result["target"]
        )

        total_matched += (
            result["matched"]
        )

        total_missing += (
            result["missing"]
        )

    print("-" * 72)

    print(
        f"{'TOTAL':<12}"
        f"{total_target:>10}"
        f"{total_matched:>10}"
        f"{total_missing:>10}"
    )

    reporting.result("filing_import", {"target": total_target, "matched": total_matched, "missing": total_missing})
    if production_refresh and (failures or total_missing):
        raise RuntimeError(f"Production filing SEC refresh failed: {failures} issuer errors; "
                           f"{total_missing} unresolved accessions")
    if production_refresh:
        print(f"Production filing SEC refresh successful: {len(submissions_loader.main)} CIKs retrieved")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("universe", nargs="?", default=DEFAULT_UNIVERSE)
    parser.add_argument("--production-refresh", action="store_true")
    args = parser.parse_args()
    if args.production_refresh:
        reporting.run_reported(args.universe,
                               lambda: import_universe(args.universe, production_refresh=True),
                               mode="production-refresh-filings-only")
    else:
        import_universe(args.universe, production_refresh=False)


if __name__ == "__main__":
    main()
