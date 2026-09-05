from src.database import get_connection

from src.financials.import_universe_financials import (
    import_company_metrics,
)


INDEX_NAME = "S&P 500"


def get_missing_tickers():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    s.ticker

                FROM index_membership_history imh

                JOIN securities s
                    ON s.id = imh.security_id

                LEFT JOIN financial_facts ff
                    ON ff.security_id = s.id

                WHERE imh.index_name = %s
                  AND ff.id IS NULL

                ORDER BY s.ticker;
                """,
                (
                    INDEX_NAME,
                ),
            )

            rows = cursor.fetchall()

    return [
        row[0]
        for row in rows
    ]


def main():
    tickers = get_missing_tickers()

    print()
    print(
        "HISTORICAL S&P 500 "
        "FINANCIAL IMPORT"
    )

    print("=" * 70)

    print(
        "Missing securities:",
        len(tickers),
    )

    summaries = []

    for ticker in tickers:
        try:
            result = import_company_metrics(
                ticker
            )

        except Exception as error:
            print()
            print(
                f"ERROR importing "
                f"{ticker}: {error}"
            )

            result = {
                "ticker": ticker,
                "imported": 0,
                "skipped": 0,
                "error": str(error),
            }

        summaries.append(
            result
        )

    print()
    print("=" * 70)
    print("IMPORT SUMMARY")
    print()

    total_records = 0
    total_skipped = 0
    errors = []

    for result in summaries:
        total_records += (
            result["imported"]
        )

        total_skipped += (
            result["skipped"]
        )

        if result.get("error"):
            errors.append(
                (
                    result["ticker"],
                    result["error"],
                )
            )

    print(
        "Companies processed:",
        len(summaries),
    )

    print(
        "Records imported:",
        total_records,
    )

    print(
        "Metrics skipped:",
        total_skipped,
    )

    print(
        "Errors:",
        len(errors),
    )

    if errors:
        print()
        print("ERRORS")
        print("=" * 70)

        for ticker, error in errors:
            print(
                f"{ticker}: {error}"
            )


if __name__ == "__main__":
    main()