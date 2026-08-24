import os

import requests
from dotenv import load_dotenv


load_dotenv()


SEC_HEADERS = {
    "User-Agent": os.getenv("SEC_USER_AGENT"),
    "Accept-Encoding": "gzip, deflate",
}


def get_company(cik):
    cik = str(cik).zfill(10)

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    company = get_company("320193")

    print("CIK:", company["cik"])
    print("Company:", company["name"])
    print("Tickers:", company["tickers"])
    print("Exchanges:", company["exchanges"])


def get_company_tickers():
    url = "https://www.sec.gov/files/company_tickers_exchange.json"

    response = requests.get(
        url,
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()