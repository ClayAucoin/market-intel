import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from src.sec.filing_document import (
    build_filing_index_url,
    get_latest_filing,
)
from src.sec.sec_client import SEC_HEADERS


def get_filing_documents(ticker, form):
    filing = get_latest_filing(ticker, form)

    index_url = build_filing_index_url(filing)

    response = requests.get(
        index_url,
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    documents = []

    table = soup.find("table", class_="tableFile")

    if table is None:
        raise ValueError("SEC document table not found.")

    rows = table.find_all("tr")

    for row in rows:
        columns = row.find_all("td")

        if len(columns) < 4:
            continue

        sequence = columns[0].get_text(strip=True)
        description = columns[1].get_text(" ", strip=True)

        link = columns[2].find("a")

        if link is None:
            continue

        document_name = link.get_text(strip=True)
        document_type = columns[3].get_text(strip=True)

        document_url = urljoin(
            index_url,
            link.get("href"),
        )

        documents.append(
            {
                "sequence": int(sequence) if sequence.isdigit() else None,
                "description": description,
                "document_name": document_name,
                "document_type": document_type,
                "document_url": document_url,
            }
        )

    return filing, documents


def get_filing_documents_by_accession(
    ticker,
    accession_number,
):
    from src.data.company_repository import get_company_by_ticker
    from src.database import get_connection

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
                  AND accession_number = %s
                LIMIT 1;
                """,
                (
                    company["id"],
                    accession_number,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"Filing not found: {accession_number}"
        )

    filing = {
        "id": row[0],
        "cik": company["cik"],
        "ticker": company["ticker"],
        "company_name": company["company_name"],
        "accession_number": row[1],
        "primary_document": row[2],
        "filing_date": row[3],
    }

    index_url = build_filing_index_url(filing)

    response = requests.get(
        index_url,
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    documents = []

    table = soup.find(
        "table",
        class_="tableFile",
    )

    if table is None:
        raise ValueError(
            "SEC document table not found."
        )

    rows = table.find_all("tr")

    for row in rows:
        columns = row.find_all("td")

        if len(columns) < 4:
            continue

        sequence = columns[0].get_text(
            strip=True
        )

        description = columns[1].get_text(
            " ",
            strip=True,
        )

        link = columns[2].find("a")

        if link is None:
            continue

        document_name = link.get_text(
            strip=True
        )

        document_type = columns[3].get_text(
            strip=True
        )

        document_url = urljoin(
            index_url,
            link.get("href"),
        )

        documents.append(
            {
                "sequence": (
                    int(sequence)
                    if sequence.isdigit()
                    else None
                ),
                "description": description,
                "document_name": document_name,
                "document_type": document_type,
                "document_url": document_url,
            }
        )

    return filing, documents


if __name__ == "__main__":
    filing, documents = get_filing_documents(
        "DELL",
        "8-K",
    )

    print(
        filing["ticker"],
        filing["filing_date"],
        filing["accession_number"],
    )

    print()

    for document in documents:
        print(
            document["sequence"],
            document["document_type"],
            document["document_name"],
            "-",
            document["description"],
        )