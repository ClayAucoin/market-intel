import requests

from src.company_repository import get_company_by_ticker
from src.database import get_connection
from src.sec.sec_client import SEC_HEADERS


def get_latest_filing(ticker, form):
    company = get_company_by_ticker(ticker)

    if company is None:
        raise ValueError(f"Ticker not found: {ticker}")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    accession_number,
                    primary_document,
                    filing_date
                FROM filings
                WHERE company_id = %s
                  AND form = %s
                ORDER BY filing_date DESC,
                         acceptance_datetime DESC
                LIMIT 1;
                """,
                (company["id"], form),
            )

            row = cursor.fetchone()

    if row is None:
        raise ValueError(f"No {form} filing found for {ticker}")

    return {
        "id": row[0],
        "cik": company["cik"],
        "ticker": company["ticker"],
        "company_name": company["company_name"],
        "accession_number": row[1],
        "primary_document": row[2],
        "filing_date": row[3],
    }


def build_filing_url(filing):
    cik = str(int(filing["cik"]))
    accession_no_dashes = filing["accession_number"].replace("-", "")

    return (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik}/{accession_no_dashes}/"
        f"{filing['primary_document']}"
    )


def download_filing(ticker, form):
    filing = get_latest_filing(ticker, form)

    url = build_filing_url(filing)

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    filing["url"] = url
    filing["html"] = response.text

    return filing


def build_filing_index_url(filing):
    cik = str(int(filing["cik"]))
    accession_no_dashes = filing["accession_number"].replace("-", "")

    return (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik}/{accession_no_dashes}/"
        f"{filing['accession_number']}-index.html"
    )


if __name__ == "__main__":
    filing = download_filing("DELL", "8-K")

    print("Company:", filing["company_name"])
    print("Filing date:", filing["filing_date"])
    print("Accession:", filing["accession_number"])
    print("URL:", filing["url"])
    print("Downloaded characters:", len(filing["html"]))
    print("Index URL:", build_filing_index_url(filing))