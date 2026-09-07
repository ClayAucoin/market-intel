import sys
from datetime import date
from decimal import Decimal

from src.analysis.rum_runner_removed_stock_followup import (
    get_snapshot,
    build_removed_holdings,
    analyze_removed_holding,
)

from src.analysis.rum_runner_added_stock_followup import (
    build_added_holdings,
    analyze_added_holding,
)


def money(value):
    if value is None:
        return "-"

    return f"${value:,.2f}"


def percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def summarize_removed(results):
    usable = [
        item
        for item in results
        if (
            item.get(
                "estimated_removal_value"
            )
            is not None
            and item.get(
                "estimated_hold_value"
            )
            is not None
            and item.get(
                "hold_profit"
            )
            is not None
        )
    ]

    if not usable:
        return {
            "count": len(results),
            "usable_count": 0,
            "starting_value": None,
            "ending_value": None,
            "profit": None,
            "weighted_return": None,
            "average_return": None,
        }

    starting_value = sum(
        (
            item[
                "estimated_removal_value"
            ]
            for item in usable
        ),
        Decimal("0"),
    )

    ending_value = sum(
        (
            item[
                "estimated_hold_value"
            ]
            for item in usable
        ),
        Decimal("0"),
    )

    profit = sum(
        (
            item["hold_profit"]
            for item in usable
        ),
        Decimal("0"),
    )

    if starting_value == 0:
        weighted_return = None
    else:
        weighted_return = (
            profit
            / starting_value
            * Decimal("100")
        )

    returns = [
        item["hold_return_percent"]
        for item in usable
        if item.get(
            "hold_return_percent"
        )
        is not None
    ]

    if returns:
        average_return = (
            sum(
                returns,
                Decimal("0"),
            )
            / Decimal(
                str(len(returns))
            )
        )
    else:
        average_return = None

    return {
        "count": len(results),
        "usable_count": len(usable),
        "starting_value": starting_value,
        "ending_value": ending_value,
        "profit": profit,
        "weighted_return": weighted_return,
        "average_return": average_return,
    }


def summarize_added(results):
    usable = [
        item
        for item in results
        if (
            item.get(
                "estimated_hold_value"
            )
            is not None
            and item.get(
                "estimated_profit"
            )
            is not None
        )
    ]

    if not usable:
        return {
            "count": len(results),
            "usable_count": 0,
            "starting_value": None,
            "ending_value": None,
            "profit": None,
            "weighted_return": None,
            "average_return": None,
        }

    starting_value = sum(
        (
            item["market_value"]
            for item in usable
        ),
        Decimal("0"),
    )

    ending_value = sum(
        (
            item[
                "estimated_hold_value"
            ]
            for item in usable
        ),
        Decimal("0"),
    )

    profit = sum(
        (
            item[
                "estimated_profit"
            ]
            for item in usable
        ),
        Decimal("0"),
    )

    if starting_value == 0:
        weighted_return = None
    else:
        weighted_return = (
            profit
            / starting_value
            * Decimal("100")
        )

    returns = [
        item["return_percent"]
        for item in usable
        if item.get(
            "return_percent"
        )
        is not None
    ]

    if returns:
        average_return = (
            sum(
                returns,
                Decimal("0"),
            )
            / Decimal(
                str(len(returns))
            )
        )
    else:
        average_return = None

    return {
        "count": len(results),
        "usable_count": len(usable),
        "starting_value": starting_value,
        "ending_value": ending_value,
        "profit": profit,
        "weighted_return": weighted_return,
        "average_return": average_return,
    }


def print_removed_detail(results):
    print()
    print("REMOVED STOCKS")
    print("=" * 100)

    if not results:
        print("None")
        return

    print(
        f"{'Ticker':<10}"
        f"{'Start Value':>18}"
        f"{'Hold Value':>18}"
        f"{'Hold P/L':>18}"
        f"{'Return':>14}"
    )

    print("-" * 100)

    for item in sorted(
        results,
        key=lambda x: x["ticker"],
    ):
        print(
            f"{item['ticker']:<10}"
            f"{money(item.get('estimated_removal_value')):>18}"
            f"{money(item.get('estimated_hold_value')):>18}"
            f"{money(item.get('hold_profit')):>18}"
            f"{percent(item.get('hold_return_percent')):>14}"
        )


def print_added_detail(results):
    print()
    print("ADDED STOCKS")
    print("=" * 100)

    if not results:
        print("None")
        return

    print(
        f"{'Ticker':<10}"
        f"{'Start Value':>18}"
        f"{'Hold Value':>18}"
        f"{'Hold P/L':>18}"
        f"{'Return':>14}"
    )

    print("-" * 100)

    for item in sorted(
        results,
        key=lambda x: x["ticker"],
    ):
        print(
            f"{item['ticker']:<10}"
            f"{money(item.get('market_value')):>18}"
            f"{money(item.get('estimated_hold_value')):>18}"
            f"{money(item.get('estimated_profit')):>18}"
            f"{percent(item.get('return_percent')):>14}"
        )


def print_group_summary(
    removed_summary,
    added_summary,
):
    print()
    print("GROUP COMPARISON")
    print("=" * 115)

    print(
        f"{'Group':<18}"
        f"{'Stocks':>10}"
        f"{'Usable':>10}"
        f"{'Start Value':>18}"
        f"{'End Value':>18}"
        f"{'P/L':>18}"
        f"{'Wt. Return':>15}"
    )

    print("-" * 115)

    print(
        f"{'Removed / Held':<18}"
        f"{removed_summary['count']:>10}"
        f"{removed_summary['usable_count']:>10}"
        f"{money(removed_summary['starting_value']):>18}"
        f"{money(removed_summary['ending_value']):>18}"
        f"{money(removed_summary['profit']):>18}"
        f"{percent(removed_summary['weighted_return']):>15}"
    )

    print(
        f"{'Added':<18}"
        f"{added_summary['count']:>10}"
        f"{added_summary['usable_count']:>10}"
        f"{money(added_summary['starting_value']):>18}"
        f"{money(added_summary['ending_value']):>18}"
        f"{money(added_summary['profit']):>18}"
        f"{percent(added_summary['weighted_return']):>15}"
    )

    print()
    print(
        f"Removed average stock return: "
        f"{percent(removed_summary['average_return'])}"
    )

    print(
        f"Added average stock return:   "
        f"{percent(added_summary['average_return'])}"
    )


def print_verdict(
    removed_summary,
    added_summary,
):
    removed_return = (
        removed_summary[
            "weighted_return"
        ]
    )

    added_return = (
        added_summary[
            "weighted_return"
        ]
    )

    print()
    print("REPLACEMENT RESULT")
    print("=" * 80)

    if (
        removed_return is None
        or added_return is None
    ):
        print(
            "Not enough price data to "
            "compare the groups."
        )
        return

    difference = (
        added_return
        - removed_return
    )

    print(
        f"Added-stock weighted return: "
        f"{percent(added_return)}"
    )

    print(
        f"Removed-stock hold return:   "
        f"{percent(removed_return)}"
    )

    print(
        f"Replacement advantage:       "
        f"{percent(difference)}"
    )

    print()

    if difference > 0:
        print(
            "Result: The stocks added by the "
            "club outperformed the stocks it "
            "removed over this follow-up period."
        )

    elif difference < 0:
        print(
            "Result: The stocks the club removed "
            "would have outperformed the stocks "
            "it added over this follow-up period."
        )

    else:
        print(
            "Result: The added and removed groups "
            "had the same weighted return."
        )


def main():
    if len(sys.argv) != 4:
        print("Usage:")
        print(
            "python -m "
            "src.analysis.rum_runner_replacement_comparison "
            "EARLIER_SNAPSHOT "
            "LATER_SNAPSHOT "
            "FOLLOWUP_DATE"
        )

        print()
        print("Example:")
        print(
            "python -m "
            "src.analysis.rum_runner_replacement_comparison "
            "2026-09-01 "
            "2026-10-01 "
            "2026-12-31"
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

    removed_holdings = build_removed_holdings(
        first_snapshot,
        second_snapshot,
    )

    added_holdings = build_added_holdings(
        first_snapshot,
        second_snapshot,
    )

    removed_results = [
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
        for holding in removed_holdings
    ]

    added_results = [
        analyze_added_holding(
            holding,
            second_snapshot[
                "snapshot_month"
            ],
            followup_date,
        )
        for holding in added_holdings
    ]

    removed_summary = summarize_removed(
        removed_results
    )

    added_summary = summarize_added(
        added_results
    )

    print()
    print(
        "RUM RUNNERS REPLACEMENT COMPARISON"
    )
    print("=" * 115)

    print(
        f"Earlier snapshot: "
        f"{first_snapshot['snapshot_month']}"
    )

    print(
        f"Later snapshot:   "
        f"{second_snapshot['snapshot_month']}"
    )

    print(
        f"Follow-up date:   "
        f"{followup_date}"
    )

    print()
    print(
        "Note: the later monthly snapshot date "
        "is used as the estimated replacement "
        "date because exact trade dates are "
        "not available."
    )

    print_removed_detail(
        removed_results
    )

    print_added_detail(
        added_results
    )

    print_group_summary(
        removed_summary,
        added_summary,
    )

    print_verdict(
        removed_summary,
        added_summary,
    )


if __name__ == "__main__":
    main()