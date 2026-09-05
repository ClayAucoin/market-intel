from datetime import date

from src.database import get_connection

from src.prices.price_client import (
    get_historical_prices,
)

from src.prices.price_repository import (
    save_daily_prices,
)


INDEX_NAME = "S&P 500"

PRICE_SOURCE = "tiingo"


#
# These symbols need individual validation before
# we trust Tiingo's historical data for them.
#
PROBLEM_TICKERS = {
    "CA",
    "CSRA",
    "DISCA",
    "FRC",
    "HFC",
    "INFO",
    "KORS",
    "MON",
    "NFX",
    "SIVB",
    "VIAC",
    "WRK",
}


def get_missing_price_securities():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.ticker
                FROM index_membership_history imh
                JOIN securities s
                  ON s.id = imh.security_id
                LEFT JOIN daily_prices dp
                  ON UPPER(dp.symbol) =
                     UPPER(s.ticker)
                WHERE imh.index_name = %s
                GROUP BY
                    s.id,
                    s.ticker
                HAVING COUNT(dp.id) = 0
                ORDER BY s.ticker;
                """,
                (
                    INDEX_NAME,
                ),
            )

            return cursor.fetchall()


def get_membership_runs(
    security_id,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    effective_from,
                    effective_to
                FROM index_membership_history
                WHERE index_name = %s
                  AND security_id = %s
                ORDER BY effective_from;
                """,
                (
                    INDEX_NAME,
                    security_id,
                ),
            )

            return cursor.fetchall()


def import_membership_run(
    ticker,
    start_date,
    end_date,
):
    if start_date is None:
        return 0

    if end_date is None:
        end_date = date.today()

    print(
        f"  Membership: "
        f"{start_date} to {end_date}"
    )

    prices = get_historical_prices(
        ticker,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        refresh=True,
        use_cache=False,
        save_cache=False,
    )

    if not prices:
        print(
            "  No price data returned."
        )

        return 0

    save_daily_prices(
        ticker,
        prices,
    )

    return len(prices)


def import_security(
    security_id,
    ticker,
):
    print()
    print("=" * 72)

    print(
        f"Importing historical prices "
        f"for {ticker}"
    )

    print(
        f"Security ID: {security_id}"
    )

    runs = get_membership_runs(
        security_id
    )

    total_records = 0

    for start_date, end_date in runs:
        count = import_membership_run(
            ticker,
            start_date,
            end_date,
        )

        total_records += count

    return total_records


def main():
    securities = (
        get_missing_price_securities()
    )

    safe = []

    skipped = []

    for security_id, ticker in securities:
        if ticker in PROBLEM_TICKERS:
            skipped.append(
                (
                    security_id,
                    ticker,
                )
            )

        else:
            safe.append(
                (
                    security_id,
                    ticker,
                )
            )

    print()
    print(
        "HISTORICAL S&P 500 PRICE IMPORT"
    )

    print("=" * 72)

    print(
        "Missing-price securities:",
        len(securities),
    )

    print(
        "Import candidates:",
        len(safe),
    )

    print(
        "Manual-review skipped:",
        len(skipped),
    )

    results = []

    for security_id, ticker in safe:
        try:
            records = import_security(
                security_id,
                ticker,
            )

            status = (
                "OK"
                if records > 0
                else "NO DATA"
            )

        except Exception as error:
            print(
                f"ERROR importing "
                f"{ticker}: {error}"
            )

            records = 0

            status = "ERROR"

        results.append(
            {
                "ticker": ticker,
                "records": records,
                "status": status,
            }
        )

    print()
    print("=" * 72)

    print(
        "HISTORICAL PRICE IMPORT SUMMARY"
    )

    print()

    print(
        f"{'Ticker':<10}"
        f"{'Records':>12}"
        f"{'Status':>16}"
    )

    print("-" * 38)

    total_records = 0

    ok_count = 0

    no_data_count = 0

    error_count = 0

    for result in results:
        print(
            f"{result['ticker']:<10}"
            f"{result['records']:>12,}"
            f"{result['status']:>16}"
        )

        total_records += (
            result["records"]
        )

        if result["status"] == "OK":
            ok_count += 1

        elif result["status"] == "NO DATA":
            no_data_count += 1

        elif result["status"] == "ERROR":
            error_count += 1

    print("-" * 38)

    print(
        f"{'TOTAL':<10}"
        f"{total_records:>12,}"
    )

    print()

    print(
        "Successful:",
        ok_count,
    )

    print(
        "No data:",
        no_data_count,
    )

    print(
        "Errors:",
        error_count,
    )

    print()

    print(
        "MANUAL-REVIEW TICKERS"
    )

    for _, ticker in skipped:
        print(
            ticker
        )


if __name__ == "__main__":
    main()