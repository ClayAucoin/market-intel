from decimal import Decimal

from src.database import get_connection
from src.analysis.portfolio_history_stock_performance import (
    PORTFOLIO_NAME,
    build_history,
)


def get_portfolio_tickers():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (h.security_id)
                    h.security_id,
                    h.ticker
                FROM portfolio_snapshot_holdings h
                JOIN portfolio_snapshots s
                  ON s.id = h.snapshot_id
                WHERE s.portfolio_name = %s
                ORDER BY
                    h.security_id,
                    s.snapshot_month DESC;
                """,
                (
                    PORTFOLIO_NAME,
                ),
            )

            rows = cursor.fetchall()

    return sorted(
        row[1]
        for row in rows
    )


def percent_change(old_value, new_value):
    if (
        old_value is None
        or new_value is None
        or old_value == 0
    ):
        return None

    return (
        (
            Decimal(str(new_value))
            / Decimal(str(old_value))
        )
        - Decimal("1")
    ) * Decimal("100")


def get_first_held_index(rows):
    for index, row in enumerate(rows):
        if row["held"]:
            return index

    return None


def get_last_held_index(rows):
    for index in range(
        len(rows) - 1,
        -1,
        -1,
    ):
        if rows[index]["held"]:
            return index

    return None


def has_ownership_gap(rows):
    first_index = get_first_held_index(rows)
    last_index = get_last_held_index(rows)

    if (
        first_index is None
        or last_index is None
    ):
        return False

    for row in rows[
        first_index:last_index + 1
    ]:
        if not row["held"]:
            return True

    return False


def classify_history(rows):
    first_index = get_first_held_index(rows)
    last_index = get_last_held_index(rows)

    if first_index is None:
        return "Never Held"

    currently_held = rows[-1]["held"]

    gap = has_ownership_gap(rows)

    started_in_first_snapshot = (
        first_index == 0
    )

    if gap and currently_held:
        return "Re-added"

    if gap and not currently_held:
        return "Removed Again"

    if (
        started_in_first_snapshot
        and currently_held
    ):
        return "Continuous"

    if (
        started_in_first_snapshot
        and not currently_held
    ):
        return "Removed"

    if currently_held:
        return "Added Later"

    return "Added / Removed"


def get_post_removal_return(rows):
    """
    Uses the first snapshot where the stock is absent
    after previously being held as the proxy removal date.

    This does NOT assume the exact trade happened on that
    date. It only measures performance from the first
    snapshot where we know the stock was no longer held.
    """

    ever_held = False
    removal_index = None

    for index, row in enumerate(rows):
        if row["held"]:
            ever_held = True
            continue

        if ever_held:
            removal_index = index
            break

    if removal_index is None:
        return None
      
    if removal_index == len(rows) - 1:
        return None

    removal_price = rows[
        removal_index
    ]["adjusted_price"]

    if removal_price is None:
        return None

    latest_price = rows[-1][
        "adjusted_price"
    ]

    if latest_price is None:
        return None

    return percent_change(
        removal_price,
        latest_price,
    )


def get_return_since_first_held(rows):
    first_index = get_first_held_index(rows)

    if first_index is None:
        return None

    first_price = rows[
        first_index
    ]["adjusted_price"]

    latest_price = rows[-1][
        "adjusted_price"
    ]

    if (
        first_price is None
        or latest_price is None
    ):
        return None

    return percent_change(
        first_price,
        latest_price,
    )


def get_summary_row(ticker):
    actual_ticker, rows = build_history(
        ticker
    )

    first_index = get_first_held_index(
        rows
    )

    last_index = get_last_held_index(
        rows
    )

    if first_index is None:
        return None

    first_held = rows[
        first_index
    ]["month"]

    last_held = rows[
        last_index
    ]["month"]

    snapshots_held = sum(
        1
        for row in rows
        if row["held"]
    )

    return {
        "ticker": actual_ticker,
        "first_held": first_held,
        "last_held": last_held,
        "snapshots_held": snapshots_held,
        "current": rows[-1]["held"],
        "history": classify_history(
            rows
        ),
        "since_first_held": (
            get_return_since_first_held(
                rows
            )
        ),
        "post_removal": (
            get_post_removal_return(
                rows
            )
        ),
    }


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_summary(summary_rows):
    print()
    print(
        "HISTORICAL PORTFOLIO "
        "STOCK PERFORMANCE SUMMARY"
    )
    print("=" * 115)

    print(
        f"{'Ticker':<9}"
        f"{'First Held':<13}"
        f"{'Last Held':<13}"
        f"{'Months':>8}"
        f"{'Current':>10}"
        f"{'History':>20}"
        f"{'Since First':>15}"
        f"{'Post Removal':>16}"
    )

    print("-" * 115)

    for row in summary_rows:
        first_held = (
            row["first_held"]
            .strftime("%Y-%m")
        )

        last_held = (
            row["last_held"]
            .strftime("%Y-%m")
        )

        print(
            f"{row['ticker']:<9}"
            f"{first_held:<13}"
            f"{last_held:<13}"
            f"{row['snapshots_held']:>8}"
            f"{'Yes' if row['current'] else 'No':>10}"
            f"{row['history']:>20}"
            f"{format_percent(row['since_first_held']):>15}"
            f"{format_percent(row['post_removal']):>16}"
        )

    print()
    print(
        "Since First = adjusted-price return from the "
        "first snapshot where the stock was held "
        "through the latest available snapshot."
    )

    print(
        "Post Removal = adjusted-price return beginning "
        "with the first snapshot where the stock was "
        "known to be absent."
    )

    print(
        "Snapshot dates are observation dates, not exact "
        "buy or sell dates."
    )

    print(
        "A missing monthly snapshot creates a longer "
        "measurement interval rather than an inferred "
        "ownership decision."
    )


def main():
    tickers = get_portfolio_tickers()

    summary_rows = []

    for ticker in tickers:
        try:
            row = get_summary_row(
                ticker
            )

            if row is not None:
                summary_rows.append(
                    row
                )

        except Exception as exc:
            print(
                f"WARNING: {ticker}: {exc}"
            )

    summary_rows.sort(
        key=lambda row: (
            row["history"],
            row["ticker"],
        )
    )

    print_summary(
        summary_rows
    )


if __name__ == "__main__":
    main()