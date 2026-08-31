from src.database import get_connection
from src.sec.exhibit_repository import save_exhibits
from src.sec.exhibit_parser import (
    get_filing_documents_by_accession,
)


def get_recent_filings(ticker, form="8-K", limit=25):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    f.id,
                    f.accession_number,
                    f.filing_date
                FROM filings f
                JOIN companies c
                    ON c.id = f.company_id
                WHERE UPPER(c.ticker) = UPPER(%s)
                  AND f.form = %s
                ORDER BY
                    f.filing_date DESC,
                    f.acceptance_datetime DESC
                LIMIT %s;
                """,
                (ticker, form, limit),
            )

            return cursor.fetchall()


def import_recent_exhibits(ticker, form="8-K", limit=25):
    filings = get_recent_filings(
        ticker,
        form,
        limit,
    )

    print(
        f"Found {len(filings)} recent "
        f"{form} filings for {ticker}."
    )

    for index, filing_row in enumerate(filings, start=1):
        filing_id = filing_row[0]
        accession_number = filing_row[1]
        filing_date = filing_row[2]

        print(
            f"[{index}/{len(filings)}] "
            f"{filing_date} "
            f"{accession_number}"
        )

        filing, documents = get_filing_documents_by_accession(
            ticker,
            accession_number,
        )

        save_exhibits(
            filing_id,
            documents,
        )


if __name__ == "__main__":
    import_recent_exhibits(
        "DELL",
        "8-K",
        25,
    )