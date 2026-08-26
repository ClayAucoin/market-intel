from datetime import (
    datetime,
)
from zoneinfo import ZoneInfo

from src.database import (
    get_connection,
)

from src.sec_submissions import (
    get_submission_records,
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


def get_target_issuers():
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

                WHERE
                    ff.accession_number
                    IS NOT NULL

                GROUP BY
                    c.id,
                    c.cik,
                    c.company_name

                ORDER BY
                    c.company_name;
                """
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


def get_target_accessions(
    company_id,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    accession_number

                FROM financial_facts

                WHERE company_id = %s
                  AND accession_number
                      IS NOT NULL

                ORDER BY
                    accession_number;
                """,
                (
                    company_id,
                ),
            )

            rows = cursor.fetchall()

    return {
        row[0]
        for row in rows
    }


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


def import_issuer_filings(
    issuer,
):
    target_accessions = (
        get_target_accessions(
            issuer["company_id"]
        )
    )

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
        issuer["cik"],
        start_date=issuer[
            "earliest"
        ],
        end_date=issuer[
            "latest"
        ],
        refresh=False,
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


def main():
    issuers = get_target_issuers()

    results = []

    print()
    print(
        "MARKET INTEL "
        "UNIVERSE FILING IMPORT"
    )

    print("=" * 72)

    for issuer in issuers:
        try:
            result = (
                import_issuer_filings(
                    issuer
                )
            )

        except Exception as error:
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

    for result in results:
        print(
            f"{result['cik']:<12}"
            f"{result['target']:>10}"
            f"{result['matched']:>10}"
            f"{result['missing']:>10}  "
            f"{result['company_name']}"
        )


if __name__ == "__main__":
    main()