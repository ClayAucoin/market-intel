COMPANIES = [
    {
        "ticker": "DELL",
        "name": "Dell Technologies",
        "sector": "Technology",
    },
    {
        "ticker": "AAPL",
        "name": "Apple",
        "sector": "Technology",
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft",
        "sector": "Technology",
    },
    {
        "ticker": "JPM",
        "name": "JPMorgan Chase",
        "sector": "Financials",
    },
    {
        "ticker": "UNH",
        "name": "UnitedHealth Group",
        "sector": "Healthcare",
    },
    {
        "ticker": "CAT",
        "name": "Caterpillar",
        "sector": "Industrials",
    },
    {
        "ticker": "WMT",
        "name": "Walmart",
        "sector": "Consumer Staples",
    },
    {
        "ticker": "HD",
        "name": "Home Depot",
        "sector": "Consumer Discretionary",
    },
    {
        "ticker": "XOM",
        "name": "Exxon Mobil",
        "sector": "Energy",
    },
    {
        "ticker": "GOOGL",
        "name": "Alphabet",
        "sector": "Communication Services",
    },
]


def get_companies():
    return COMPANIES.copy()


def get_tickers():
    return [
        company["ticker"]
        for company in COMPANIES
    ]


def get_company(ticker):
    ticker = ticker.upper()

    for company in COMPANIES:
        if company["ticker"] == ticker:
            return company.copy()

    return None


if __name__ == "__main__":
    print()
    print("MARKET INTEL TEST UNIVERSE")
    print("=" * 62)

    print(
        f"{'Ticker':<10}"
        f"{'Company':<28}"
        f"{'Sector'}"
    )

    print("-" * 62)

    for company in get_companies():
        print(
            f"{company['ticker']:<10}"
            f"{company['name']:<28}"
            f"{company['sector']}"
        )

    print()
    print(
        f"Companies: "
        f"{len(get_companies())}"
    )