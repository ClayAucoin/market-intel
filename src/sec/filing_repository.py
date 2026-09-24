from src.database import get_connection
from src.sec.acceptance_time import parse_submissions_acceptance


def save_filings(company_id, filings):
    rows = []

    for filing in filings:
        rows.append(
            (
                company_id,
                filing["accession_number"],
                filing["form"],
                filing["filing_date"],
                filing["report_date"],
                parse_submissions_acceptance(filing["acceptance_datetime"]),
                filing["primary_document"],
                filing["primary_doc_description"],
            )
        )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO filings (
                    company_id,
                    accession_number,
                    form,
                    filing_date,
                    report_date,
                    acceptance_datetime,
                    primary_document,
                    primary_doc_description
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)

                ON CONFLICT (accession_number)
                DO NOTHING;
                """,
                rows,
            )

    print(f"Processed {len(rows):,} filings.")