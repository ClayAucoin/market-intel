import sys
from decimal import Decimal

from src.database import get_connection


PORTFOLIO_NAME = "Rum Runners"


def get_snapshot(snapshot_month):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    portfolio_name,
                    snapshot_month,
                    cash,
                    total_portfolio_value,
                    total_cost_basis,
                    source_filename
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
            f"No Rum Runners snapshot found for "
            f"{snapshot_month}."
        )

    return {
        "id": row[0],
        "portfolio_name": row[1],
        "snapshot_month": row[2],
        "cash": row[3],
        "total_portfolio_value": row[4],
        "total_cost_basis": row[5],
        "source_filename": row[6],
    }


def get_holdings(snapshot_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    security_id,
                    ticker,
                    description,
                    price,
                    shares,
                    market_value,
                    cost_basis,
                    gain_loss
                FROM portfolio_snapshot_holdings
                WHERE snapshot_id = %s
                ORDER BY ticker
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
            "description": row[2],
            "price": row[3],
            "shares": row[4],
            "market_value": row[5],
            "cost_basis": row[6],
            "gain_loss": row[7],
        }
        for row in rows
    }


def money(value):
    if value is None:
        return "-"

    return f"${value:,.2f}"


def number(value):
    if value is None:
        return "-"

    return f"{value:,.4f}"


def difference(new_value, old_value):
    if new_value is None or old_value is None:
        return None

    return new_value - old_value


def print_snapshot_summary(
    first_snapshot,
    second_snapshot,
):
    print()
    print("RUM RUNNERS SNAPSHOT COMPARISON")
    print("=" * 110)

    print(
        f"From: {first_snapshot['snapshot_month']} "
        f"({first_snapshot['source_filename']})"
    )

    print(
        f"To:   {second_snapshot['snapshot_month']} "
        f"({second_snapshot['source_filename']})"
    )

    print()
    print("PORTFOLIO TOTALS")
    print("-" * 110)

    total_change = difference(
        second_snapshot["total_portfolio_value"],
        first_snapshot["total_portfolio_value"],
    )

    cash_change = difference(
        second_snapshot["cash"],
        first_snapshot["cash"],
    )

    cost_change = difference(
        second_snapshot["total_cost_basis"],
        first_snapshot["total_cost_basis"],
    )

    print(
        f"{'Metric':<28}"
        f"{'Earlier':>20}"
        f"{'Later':>20}"
        f"{'Change':>20}"
    )

    print("-" * 88)

    print(
        f"{'Total portfolio value':<28}"
        f"{money(first_snapshot['total_portfolio_value']):>20}"
        f"{money(second_snapshot['total_portfolio_value']):>20}"
        f"{money(total_change):>20}"
    )

    print(
        f"{'Cash':<28}"
        f"{money(first_snapshot['cash']):>20}"
        f"{money(second_snapshot['cash']):>20}"
        f"{money(cash_change):>20}"
    )

    print(
        f"{'Total cost basis':<28}"
        f"{money(first_snapshot['total_cost_basis']):>20}"
        f"{money(second_snapshot['total_cost_basis']):>20}"
        f"{money(cost_change):>20}"
    )


def print_added(added):
    print()
    print("ADDED HOLDINGS")
    print("=" * 110)

    if not added:
        print("None")
        return

    print(
        f"{'Ticker':<8}"
        f"{'Shares':>14}"
        f"{'Price':>14}"
        f"{'Market Value':>18}"
        f"{'Cost Basis':>18}"
        f"{'Gain/Loss':>18}"
    )

    print("-" * 110)

    for item in sorted(
        added,
        key=lambda x: x["ticker"],
    ):
        print(
            f"{item['ticker']:<8}"
            f"{number(item['shares']):>14}"
            f"{money(item['price']):>14}"
            f"{money(item['market_value']):>18}"
            f"{money(item['cost_basis']):>18}"
            f"{money(item['gain_loss']):>18}"
        )


def print_removed(removed):
    print()
    print("REMOVED HOLDINGS")
    print("=" * 110)

    if not removed:
        print("None")
        return

    print(
        f"{'Ticker':<8}"
        f"{'Shares':>14}"
        f"{'Last Price':>14}"
        f"{'Last Value':>18}"
        f"{'Cost Basis':>18}"
        f"{'Gain/Loss':>18}"
    )

    print("-" * 110)

    for item in sorted(
        removed,
        key=lambda x: x["ticker"],
    ):
        print(
            f"{item['ticker']:<8}"
            f"{number(item['shares']):>14}"
            f"{money(item['price']):>14}"
            f"{money(item['market_value']):>18}"
            f"{money(item['cost_basis']):>18}"
            f"{money(item['gain_loss']):>18}"
        )


def print_kept_changes(changes):
    print()
    print("KEPT HOLDINGS WITH CHANGES")
    print("=" * 145)

    if not changes:
        print("None")
        return

    print(
        f"{'Ticker':<8}"
        f"{'Old Shares':>14}"
        f"{'New Shares':>14}"
        f"{'Share Δ':>14}"
        f"{'Old Value':>16}"
        f"{'New Value':>16}"
        f"{'Value Δ':>16}"
    )

    print("-" * 145)

    for item in sorted(
        changes,
        key=lambda x: x["ticker"],
    ):
        print(
            f"{item['ticker']:<8}"
            f"{number(item['old_shares']):>14}"
            f"{number(item['new_shares']):>14}"
            f"{number(item['share_change']):>14}"
            f"{money(item['old_value']):>16}"
            f"{money(item['new_value']):>16}"
            f"{money(item['value_change']):>16}"
        )


def build_comparison(
    first_snapshot,
    second_snapshot,
):
    first_holdings = get_holdings(
        first_snapshot["id"]
    )

    second_holdings = get_holdings(
        second_snapshot["id"]
    )

    first_ids = set(
        first_holdings.keys()
    )

    second_ids = set(
        second_holdings.keys()
    )

    added_ids = (
        second_ids - first_ids
    )

    removed_ids = (
        first_ids - second_ids
    )

    kept_ids = (
        first_ids & second_ids
    )

    added = [
        second_holdings[security_id]
        for security_id in added_ids
    ]

    removed = [
        first_holdings[security_id]
        for security_id in removed_ids
    ]

    changes = []

    for security_id in kept_ids:
        old = first_holdings[
            security_id
        ]

        new = second_holdings[
            security_id
        ]

        share_change = difference(
            new["shares"],
            old["shares"],
        )

        value_change = difference(
            new["market_value"],
            old["market_value"],
        )

        changed = (
            share_change != Decimal("0")
            or value_change != Decimal("0")
        )

        if not changed:
            continue

        changes.append(
            {
                "ticker": new["ticker"],
                "old_shares": old["shares"],
                "new_shares": new["shares"],
                "share_change": share_change,
                "old_value": old["market_value"],
                "new_value": new["market_value"],
                "value_change": value_change,
            }
        )

    return {
        "added": added,
        "removed": removed,
        "kept_count": len(kept_ids),
        "changes": changes,
        "first_count": len(first_holdings),
        "second_count": len(second_holdings),
    }


def print_summary(comparison):
    print()
    print("HOLDING SUMMARY")
    print("=" * 80)

    print(
        f"Earlier holdings: "
        f"{comparison['first_count']}"
    )

    print(
        f"Later holdings: "
        f"{comparison['second_count']}"
    )

    print(
        f"Kept: "
        f"{comparison['kept_count']}"
    )

    print(
        f"Added: "
        f"{len(comparison['added'])}"
    )

    print(
        f"Removed: "
        f"{len(comparison['removed'])}"
    )

    print(
        f"Kept holdings with share/value changes: "
        f"{len(comparison['changes'])}"
    )


def main():
    if len(sys.argv) != 3:
        print(
            "Usage:"
        )
        print(
            "python -m "
            "src.analysis.rum_runner_snapshot_comparison "
            "YYYY-MM-DD YYYY-MM-DD"
        )
        raise SystemExit(1)

    first_month = sys.argv[1]
    second_month = sys.argv[2]

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

    comparison = build_comparison(
        first_snapshot,
        second_snapshot,
    )

    print_snapshot_summary(
        first_snapshot,
        second_snapshot,
    )

    print_summary(
        comparison
    )

    print_added(
        comparison["added"]
    )

    print_removed(
        comparison["removed"]
    )

    print_kept_changes(
        comparison["changes"]
    )


if __name__ == "__main__":
    main()