import requests

from src.database import get_connection
from src.sec.filing_parser import html_to_text
from src.sec.sec_client import SEC_HEADERS


def get_latest_exhibit(ticker, exhibit_type):
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
                    f.filing_date,
                    c.company_name
                FROM filing_exhibits fe
                JOIN filings f
                    ON f.id = fe.filing_id
                JOIN companies c
                    ON c.id = f.company_id
                WHERE UPPER(c.ticker) = UPPER(%s)
                  AND UPPER(fe.exhibit_type) = UPPER(%s)
                ORDER BY
                    f.filing_date DESC,
                    fe.sequence
                LIMIT 1;
                """,
                (ticker, exhibit_type),
            )

            row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"No {exhibit_type} exhibit found for {ticker}"
        )

    return {
        "id": row[0],
        "exhibit_type": row[1],
        "document_name": row[2],
        "description": row[3],
        "document_url": row[4],
        "filing_date": row[5],
        "company_name": row[6],
    }


def download_exhibit(ticker, exhibit_type):
    exhibit = get_latest_exhibit(
        ticker,
        exhibit_type,
    )

    response = requests.get(
        exhibit["document_url"],
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    exhibit["html"] = response.text
    exhibit["text"] = html_to_text(response.text)

    return exhibit


if __name__ == "__main__":
    exhibit = download_exhibit(
        "DELL",
        "EX-99.1",
    )

    print("Company:", exhibit["company_name"])
    print("Filing date:", exhibit["filing_date"])
    print("Type:", exhibit["exhibit_type"])
    print("Description:", exhibit["description"])
    print("URL:", exhibit["document_url"])
    print("Characters:", len(exhibit["text"]))

    print()
    print("=" * 70)
    print()

    print(exhibit["text"][:5000])