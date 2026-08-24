import requests

from src.database import get_connection
from src.filing_parser import html_to_text
from src.sec_client import SEC_HEADERS


def get_exhibit_by_id(exhibit_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    fe.id,
                    fe.exhibit_type,
                    fe.document_name,
                    fe.description,
                    fe.document_url,

                    f.id AS filing_id,
                    f.form,
                    f.filing_date,
                    f.accession_number,

                    c.id AS company_id,
                    c.cik,
                    c.ticker,
                    c.company_name

                FROM filing_exhibits fe

                JOIN filings f
                    ON f.id = fe.filing_id

                JOIN companies c
                    ON c.id = f.company_id

                WHERE fe.id = %s;
                """,
                (exhibit_id,),
            )

            row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"Exhibit ID {exhibit_id} not found."
        )

    return {
        "exhibit_id": row[0],
        "exhibit_type": row[1],
        "document_name": row[2],
        "description": row[3],
        "document_url": row[4],

        "filing_id": row[5],
        "form": row[6],
        "filing_date": row[7],
        "accession_number": row[8],

        "company_id": row[9],
        "cik": row[10],
        "ticker": row[11],
        "company_name": row[12],
    }


def download_exhibit_text(exhibit_id):
    document = get_exhibit_by_id(exhibit_id)

    response = requests.get(
        document["document_url"],
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    document["text"] = html_to_text(
        response.text
    )

    return document


if __name__ == "__main__":
    document = download_exhibit_text(
        28
    )

    print("Company:", document["company_name"])
    print("Ticker:", document["ticker"])
    print("Form:", document["form"])
    print("Exhibit:", document["exhibit_type"])
    print("Date:", document["filing_date"])
    print("Description:", document["description"])
    print("Characters:", len(document["text"]))

    print()
    print("=" * 70)
    print()

    print(document["text"][:3000])