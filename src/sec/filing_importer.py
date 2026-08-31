from src.company_repository import get_company_by_ticker
from src.sec.filing_repository import save_filings
from src.sec.sec_client import get_company


def parse_recent_filings(sec_data):
    recent = sec_data["filings"]["recent"]

    filings = []

    count = len(recent["accessionNumber"])

    for i in range(count):
        filings.append(
            {
                "accession_number": recent["accessionNumber"][i],
                "form": recent["form"][i],
                "filing_date": recent["filingDate"][i],
                "report_date": recent["reportDate"][i] or None,
                "acceptance_datetime": recent["acceptanceDateTime"][i] or None,
                "primary_document": recent["primaryDocument"][i],
                "primary_doc_description": (
                    recent["primaryDocDescription"][i]
                    if "primaryDocDescription" in recent
                    else None
                ),
            }
        )

    return filings


def import_filings(ticker):
    company = get_company_by_ticker(ticker)

    if company is None:
        raise ValueError(f"Ticker not found: {ticker}")

    print(
        f"Fetching filings for "
        f"{company['ticker']} - {company['company_name']}"
    )

    sec_data = get_company(company["cik"])

    filings = parse_recent_filings(sec_data)

    save_filings(company["id"], filings)

    return filings


if __name__ == "__main__":
    import_filings("DELL")