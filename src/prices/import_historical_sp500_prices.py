from datetime import date, timedelta

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
# We need 61 prior trading sessions for market
# context. 100 calendar days gives us enough
# room for weekends and holidays.
#
PRE_PADDING_DAYS = 100

#
# Backtests calculate returns 180 calendar days
# after entry. 190 calendar days gives us room
# for weekends and market holidays.
#
POST_PADDING_DAYS = 190


#
# These symbols were manually resolved or have
# ticker-history/provider issues. Do not fetch
# them automatically from Tiingo.
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


def get_historical_securities():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    s.id,
                    s.ticker

                FROM index_membership_history imh

                JOIN securities s
                  ON s.id = imh.security_id

                WHERE imh.index_name = %s

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


def import_price_range(
    ticker,
    start_date,
    end_date,
    label,
):
    if start_date is None:
        return 0

    if end_date is None:
        return 0

    today = date.today()

    if start_date > today:
        return 0

    if end_date > today:
        end_date = today

    if start_date > end_date:
        return 0

    print(
        f"  {label}: "
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

    print(
        f"  Downloaded: {len(prices)}"
    )

    return len(prices)


def import_membership_padding(
    ticker,
    membership_start,
    membership_end,
):
    total_records = 0

    #
    # Fetch enough history before membership
    # begins to calculate the 60-session
    # pre-entry market context.
    #
    pre_start = (
        membership_start
        - timedelta(
            days=PRE_PADDING_DAYS
        )
    )

    pre_end = (
        membership_start
        - timedelta(days=1)
    )

    total_records += import_price_range(
        ticker,
        pre_start,
        pre_end,
        "Pre-membership padding",
    )

    #
    # Open membership runs do not need
    # post-membership padding.
    #
    if membership_end is None:
        return total_records

    #
    # Fetch enough history after membership
    # ends to calculate the 180-day forward
    # return for an event occurring near the
    # end of membership.
    #
    post_start = (
        membership_end
        + timedelta(days=1)
    )

    post_end = (
        membership_end
        + timedelta(
            days=POST_PADDING_DAYS
        )
    )

    total_records += import_price_range(
        ticker,
        post_start,
        post_end,
        "Post-membership padding",
    )

    return total_records


def import_security(
    security_id,
    ticker,
):
    print()
    print("=" * 72)

    print(
        f"Padding historical prices "
        f"for {ticker}"
    )

    print(
        f"Security ID: {security_id}"
    )

    runs = get_membership_runs(
        security_id
    )

    total_records = 0

    for (
        membership_start,
        membership_end,
    ) in runs:
        print(
            f"  Membership: "
            f"{membership_start} to "
            f"{membership_end or 'OPEN'}"
        )

        count = import_membership_padding(
            ticker,
            membership_start,
            membership_end,
        )

        total_records += count

    return total_records


def main():
    securities = (
        get_historical_securities()
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
        "HISTORICAL S&P 500 PRICE PADDING"
    )

    print("=" * 72)

    print(
        "Historical securities:",
        len(securities),
    )

    print(
        "Automatic Tiingo securities:",
        len(safe),
    )

    print(
        "Manual-review skipped:",
        len(skipped),
    )

    print()

    print(
        "Pre-membership padding:",
        PRE_PADDING_DAYS,
        "calendar days",
    )

    print(
        "Post-membership padding:",
        POST_PADDING_DAYS,
        "calendar days",
    )

    results = []

    for security_id, ticker in safe:
        try:
            records = import_security(
                security_id,
                ticker,
            )

            status = "OK"

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
        "HISTORICAL PRICE PADDING SUMMARY"
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