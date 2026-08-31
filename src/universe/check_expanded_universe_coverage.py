from src.database import get_connection


NEW_TICKERS = [
    "NVDA",
    "AMD",
    "ORCL",
    "CRM",
    "AVGO",

    "META",
    "NFLX",
    "DIS",

    "BAC",
    "GS",
    "V",
    "MA",

    "JNJ",
    "LLY",
    "PFE",
    "ABBV",

    "AMZN",
    "TSLA",
    "MCD",
    "NKE",

    "COST",
    "PG",
    "KO",
    "PEP",

    "GE",
    "BA",
    "UPS",
    "HON",

    "CVX",
    "COP",
    "SLB",

    "LIN",
    "NEM",

    "NEE",
    "DUK",

    "AMT",
    "PLD",

    "BRK.B",
]


def find_security(
    ticker,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.ticker,
                    s.exchange,
                    c.cik,
                    c.company_name

                FROM securities s

                JOIN companies c
                    ON c.id =
                       s.company_id

                WHERE UPPER(s.ticker) =
                      UPPER(%s)

                ORDER BY
                    s.is_primary DESC,
                    s.id

                LIMIT 1;
                """,
                (
                    ticker,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "security_id": row[0],
        "ticker": row[1],
        "exchange": row[2],
        "cik": row[3],
        "company_name": row[4],
    }


def main():
    print()
    print(
        "EXPANDED UNIVERSE "
        "SECURITY COVERAGE"
    )

    print("=" * 100)

    print(
        f"{'Requested':<12}"
        f"{'Resolved':<12}"
        f"{'CIK':<12}"
        f"{'Exchange':<12}"
        f"{'Company'}"
    )

    print("-" * 100)

    found = 0
    missing = []

    for ticker in NEW_TICKERS:
        security = find_security(
            ticker
        )

        if security is None:
            missing.append(
                ticker
            )

            print(
                f"{ticker:<12}"
                f"{'MISSING':<12}"
                f"{'-':<12}"
                f"{'-':<12}"
                f"-"
            )

            continue

        found += 1

        print(
            f"{ticker:<12}"
            f"{security['ticker']:<12}"
            f"{security['cik']:<12}"
            f"{str(security['exchange']):<12}"
            f"{security['company_name']}"
        )

    print()
    print("=" * 100)

    print(
        "Requested:",
        len(NEW_TICKERS),
    )

    print(
        "Resolved:",
        found,
    )

    print(
        "Missing:",
        len(missing),
    )

    if missing:
        print()
        print(
            "Missing tickers:"
        )

        for ticker in missing:
            print(
                f"  {ticker}"
            )


if __name__ == "__main__":
    main()