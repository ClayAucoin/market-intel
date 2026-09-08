import sys
from datetime import date
from decimal import Decimal

from src.database import get_connection


PORTFOLIO_NAME = "Historical Portfolio"


def get_snapshot(snapshot_month):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    snapshot_month
                FROM portfolio_snapshots
                WHERE
                    portfolio_name = %s
                    AND snapshot_month = %s
                """,
                (
                    PORTFOLIO_NAME,
                    snapshot_month,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        raise RuntimeError(
            f"No Historical Portfolio snapshot found for "
            f"{snapshot_month}."
        )

    return {
        "id": row[0],
        "snapshot_month": row[1],
    }


def get_holdings(snapshot_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    security_id,
                    ticker,
                    shares,
                    market_value
                FROM portfolio_snapshot_holdings
                WHERE snapshot_id = %s
                """,
                (
                    snapshot_id,
                ),
            )

            rows = cursor.fetchall()

    return {
        row[0]: {
            "security_id": row[0],
            "ticker": row[1],
            "shares": Decimal(str(row[2])),
            "market_value": Decimal(
                str(row[3])
            ),
        }
        for row in rows
    }


def get_price_on_or_after(
    ticker,
    target_date,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    trade_date,
                    adjusted_close
                FROM daily_prices
                WHERE
                    UPPER(symbol) = UPPER(%s)
                    AND trade_date >= %s
                    AND adjusted_close IS NOT NULL
                ORDER BY trade_date
                LIMIT 1
                """,
                (
                    ticker,
                    target_date,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "date": row[0],
        "price": Decimal(
            str(row[1])
        ),
    }


def get_price_on_or_before(
    ticker,
    target_date,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    trade_date,
                    adjusted_close
                FROM daily_prices
                WHERE
                    UPPER(symbol) = UPPER(%s)
                    AND trade_date <= %s
                    AND adjusted_close IS NOT NULL
                ORDER BY trade_date DESC
                LIMIT 1
                """,
                (
                    ticker,
                    target_date,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "date": row[0],
        "price": Decimal(
            str(row[1])
        ),
    }


def build_removed_holdings(
    first_snapshot,
    second_snapshot,
):
    first_holdings = get_holdings(
        first_snapshot["id"]
    )

    second_holdings = get_holdings(
        second_snapshot["id"]
    )

    removed_ids = (
        set(first_holdings.keys())
        - set(second_holdings.keys())
    )

    return [
        first_holdings[
            security_id
        ]
        for security_id in removed_ids
    ]


def analyze_removed_holding(
    holding,
    first_snapshot_date,
    removal_date,
    followup_date,
):
    starting_price = get_price_on_or_after(
        holding["ticker"],
        first_snapshot_date,
    )

    removal_price = get_price_on_or_after(
        holding["ticker"],
        removal_date,
    )

    followup_price = get_price_on_or_before(
        holding["ticker"],
        followup_date,
    )

    if (
        starting_price is None
        or removal_price is None
        or followup_price is None
        or starting_price["price"] == 0
        or removal_price["price"] == 0
    ):
        return {
            **holding,
            "starting_price": starting_price,
            "removal_price": removal_price,
            "followup_price": followup_price,
            "estimated_removal_value": None,
            "estimated_hold_value": None,
            "hold_profit": None,
            "hold_return_percent": None,
        }

    value_at_removal_ratio = (
        removal_price["price"]
        / starting_price["price"]
    )

    estimated_removal_value = (
        holding["market_value"]
        * value_at_removal_ratio
    )

    post_removal_ratio = (
        followup_price["price"]
        / removal_price["price"]
    )

    estimated_hold_value = (
        estimated_removal_value
        * post_removal_ratio
    )

    hold_profit = (
        estimated_hold_value
        - estimated_removal_value
    )

    hold_return_percent = (
        hold_profit
        / estimated_removal_value
        * Decimal("100")
    )

    return {
        **holding,
        "starting_price": starting_price,
        "removal_price": removal_price,
        "followup_price": followup_price,
        "estimated_removal_value":
            estimated_removal_value,
        "estimated_hold_value":
            estimated_hold_value,
        "hold_profit":
            hold_profit,
        "hold_return_percent":
            hold_return_percent,
    }


def money(value):
    if value is None:
        return "-"

    return f"${value:,.2f}"


def percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_report(
    first_snapshot,
    second_snapshot,
    followup_date,
    results,
):
    print()
    print(
        "HISTORICAL PORTFOLIO REMOVED STOCK FOLLOW-UP"
    )
    print("=" * 165)

    print(
        f"Earlier snapshot: "
        f"{first_snapshot['snapshot_month']}"
    )

    print(
        f"Removal detected in: "
        f"{second_snapshot['snapshot_month']}"
    )

    print(
        f"Follow-up date: "
        f"{followup_date}"
    )

    print(
        f"Removed holdings: "
        f"{len(results)}"
    )

    print()
    print(
        f"{'Ticker':<8}"
        f"{'Shares':>12}"
        f"{'Removal Date':>14}"
        f"{'Removal Adj':>14}"
        f"{'Follow Date':>14}"
        f"{'Follow Adj':>14}"
        f"{'Est. Drop Value':>18}"
        f"{'Est. Hold Value':>18}"
        f"{'Hold P/L':>16}"
        f"{'Hold Return':>14}"
    )

    print("-" * 165)

    for item in sorted(
        results,
        key=lambda x: x["ticker"],
    ):
        removal = item["removal_price"]
        follow = item["followup_price"]

        removal_date_text = (
            str(removal["date"])
            if removal is not None
            else "-"
        )

        removal_price_text = (
            money(removal["price"])
            if removal is not None
            else "-"
        )

        follow_date_text = (
            str(follow["date"])
            if follow is not None
            else "-"
        )

        follow_price_text = (
            money(follow["price"])
            if follow is not None
            else "-"
        )

        print(
            f"{item['ticker']:<8}"
            f"{item['shares']:>12,.4f}"
            f"{removal_date_text:>14}"
            f"{removal_price_text:>14}"
            f"{follow_date_text:>14}"
            f"{follow_price_text:>14}"
            f"{money(item.get('estimated_removal_value')):>18}"
            f"{money(item.get('estimated_hold_value')):>18}"
            f"{money(item.get('hold_profit')):>16}"
            f"{percent(item.get('hold_return_percent')):>14}"
        )


def main():
    if len(sys.argv) != 4:
        print("Usage:")
        print(
            "python -m "
            "src.analysis.portfolio_history_removed_stock_followup "
            "EARLIER_SNAPSHOT "
            "LATER_SNAPSHOT "
            "FOLLOWUP_DATE"
        )

        print()
        print("Example:")
        print(
            "python -m "
            "src.analysis.portfolio_history_removed_stock_followup "
            "2026-09-01 2026-10-01 2026-12-31"
        )

        raise SystemExit(1)

    first_month = sys.argv[1]
    second_month = sys.argv[2]

    try:
        followup_date = date.fromisoformat(
            sys.argv[3]
        )

    except ValueError:
        print()
        print(
            "Follow-up date must use "
            "YYYY-MM-DD format."
        )
        raise SystemExit(1)

    try:
        first_snapshot = get_snapshot(
            first_month
        )

        second_snapshot = get_snapshot(
            second_month
        )

    except RuntimeError as exc:
        print()
        print(exc)
        raise SystemExit(1)

    if (
        followup_date
        < second_snapshot[
            "snapshot_month"
        ]
    ):
        print()
        print(
            "Follow-up date cannot be "
            "before the later snapshot."
        )
        raise SystemExit(1)

    removed = build_removed_holdings(
        first_snapshot,
        second_snapshot,
    )

    results = [
        analyze_removed_holding(
            holding,
            first_snapshot[
                "snapshot_month"
            ],
            second_snapshot[
                "snapshot_month"
            ],
            followup_date,
        )
        for holding in removed
    ]

    print_report(
        first_snapshot,
        second_snapshot,
        followup_date,
        results,
    )


if __name__ == "__main__":
    main()