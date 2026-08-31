from src.company_repository import save_companies
from src.sec.sec_client import get_company_tickers


def import_company_universe():
    data = get_company_tickers()

    fields = data["fields"]
    rows = data["data"]

    print("SEC fields:", fields)
    print(f"SEC rows received: {len(rows):,}")

    companies = []

    for row in rows:
        cik, company_name, ticker, exchange = row

        companies.append(
            (
                str(cik).zfill(10),
                ticker,
                company_name,
                exchange,
            )
        )

    save_companies(companies)


if __name__ == "__main__":
    import_company_universe()