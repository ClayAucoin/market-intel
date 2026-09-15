from collections import defaultdict
from decimal import Decimal

from src.analysis.portfolio_history_snapshot_report import (
    build_analysis,
)
from src.analysis.portfolio_history_stock_performance import (
    get_adjusted_price,
    get_daily_price_columns,
    percent_change,
)
from src.database import get_connection


PORTFOLIO_NAME = "Historical Portfolio"


def get_snapshot_months():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    snapshot_month
                FROM portfolio_snapshots
                WHERE portfolio_name = %s
                ORDER BY snapshot_month;
                """,
                (
                    PORTFOLIO_NAME,
                ),
            )

            rows = cursor.fetchall()

    return [
        row[0]
        for row in rows
    ]


def get_price_return(
    cursor,
    ticker,
    start_date,
    end_date,
    date_column,
    price_column,
):
    start_price = get_adjusted_price(
        cursor,
        ticker,
        start_date,
        date_column,
        price_column,
    )

    end_price = get_adjusted_price(
        cursor,
        ticker,
        end_date,
        date_column,
        price_column,
    )

    if (
        start_price is None
        or end_price is None
    ):
        return None

    result = percent_change(
        start_price["price"],
        end_price["price"],
    )

    if result is None:
        return None

    return {
        "return_percent": result,
        "start_price_date":
            start_price["date"],
        "end_price_date":
            end_price["date"],
    }


def get_group(priority):
    if priority is None:
        return "Insufficient Data"

    if priority >= 3:
        return "Priority 3+"

    if priority == 2:
        return "Priority 2"

    if priority == 1:
        return "Priority 1"

    return "Priority 0"


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def format_money(value):
    if value is None:
        return "-"

    return f"${value:,.2f}"


def weighted_average(rows):
    usable = [
        row
        for row in rows
        if (
            row["return_percent"]
            is not None
            and row["market_value"]
            is not None
            and row["market_value"] > 0
        )
    ]

    if not usable:
        return None

    total_value = sum(
        (
            Decimal(str(row["market_value"]))
            for row in usable
        ),
        Decimal("0"),
    )

    if total_value == 0:
        return None

    weighted_sum = sum(
        (
            Decimal(str(row["market_value"]))
            * row["return_percent"]
            for row in usable
        ),
        Decimal("0"),
    )

    return weighted_sum / total_value


def simple_average(rows):
    values = [
        row["return_percent"]
        for row in rows
        if row["return_percent"] is not None
    ]

    if not values:
        return None

    return (
        sum(values, Decimal("0"))
        / Decimal(len(values))
    )


def build_transition(
    start_month,
    end_month,
):
    (
        start_snapshot,
        results,
        diagnostics,
    ) = build_analysis(
        start_month
    )

    (
        end_snapshot,
        _,
        _,
    ) = build_analysis(
        end_month
    )

    start_date = start_snapshot[
        "as_of_date"
    ]

    end_date = end_snapshot[
        "as_of_date"
    ]

    rows = []

    with get_connection() as conn:
        with conn.cursor() as cursor:
            (
                date_column,
                price_column,
            ) = get_daily_price_columns(
                cursor
            )

            for item in results:
                price_result = (
                    get_price_return(
                        cursor,
                        item["ticker"],
                        start_date,
                        end_date,
                        date_column,
                        price_column,
                    )
                )

                if price_result is None:
                    return_percent = None
                    start_price_date = None
                    end_price_date = None
                else:
                    return_percent = (
                        price_result[
                            "return_percent"
                        ]
                    )

                    start_price_date = (
                        price_result[
                            "start_price_date"
                        ]
                    )

                    end_price_date = (
                        price_result[
                            "end_price_date"
                        ]
                    )

                rows.append(
                    {
                        "ticker":
                            item["ticker"],
                        "market_value":
                            item["market_value"],
                        "score":
                            item["score"],
                        "priority":
                            item["priority"],
                        "status":
                            item["status"],
                        "sector_confidence":
                            item[
                                "sector_confidence"
                            ],
                        "group":
                            get_group(
                                item["priority"]
                            ),
                        "return_percent":
                            return_percent,
                        "start_price_date":
                            start_price_date,
                        "end_price_date":
                            end_price_date,
                    }
                )

    return {
        "start_month":
            start_month,
        "end_month":
            end_month,
        "start_date":
            start_date,
        "end_date":
            end_date,
        "as_of_source":
            start_snapshot[
                "as_of_source"
            ],
        "universe":
            diagnostics[
                "universe_name"
            ],
        "rows":
            rows,
    }


def print_transition(transition):
    print()
    print("=" * 110)

    print(
        f"{transition['start_month']:%Y-%m}"
        f" -> "
        f"{transition['end_month']:%Y-%m}"
    )

    print(
        f"Analysis date: "
        f"{transition['start_date']}"
    )

    print(
        f"Observation date: "
        f"{transition['end_date']}"
    )

    print(
        f"As-of source: "
        f"{transition['as_of_source']}"
    )

    print(
        f"Universe: "
        f"{transition['universe']}"
    )

    print("-" * 110)

    groups = [
        "Priority 3+",
        "Priority 2",
        "Priority 1",
        "Priority 0",
        "Insufficient Data",
    ]

    for group in groups:
        rows = [
            row
            for row in transition["rows"]
            if row["group"] == group
        ]

        measured = [
            row
            for row in rows
            if row["return_percent"]
            is not None
        ]

        print(
            f"{group:<20}"
            f"N={len(rows):>3}  "
            f"Measured={len(measured):>3}  "
            f"Avg="
            f"{format_percent(
                simple_average(rows)
            ):>9}  "
            f"Value-weighted="
            f"{format_percent(
                weighted_average(rows)
            ):>9}"
        )

    priority_rows = [
        row
        for row in transition["rows"]
        if (
            row["priority"] is not None
            and row["priority"] >= 3
            and row["return_percent"]
            is not None
        )
    ]

    nonpriority_rows = [
        row
        for row in transition["rows"]
        if (
            row["priority"] is not None
            and row["priority"] < 3
            and row["return_percent"]
            is not None
        )
    ]

    priority_return = weighted_average(
        priority_rows
    )

    nonpriority_return = weighted_average(
        nonpriority_rows
    )

    advantage = None

    if (
        priority_return is not None
        and nonpriority_return is not None
    ):
        advantage = (
            priority_return
            - nonpriority_return
        )

    print()
    print(
        f"Priority 3+ value-weighted return: "
        f"{format_percent(priority_return)}"
    )

    print(
        f"Priority 0-2 value-weighted return: "
        f"{format_percent(nonpriority_return)}"
    )

    print(
        f"Priority 3+ advantage: "
        f"{format_percent(advantage)}"
    )


def print_overall(transitions):
    grouped = defaultdict(list)

    for transition in transitions:
        for row in transition["rows"]:
            if row["return_percent"] is None:
                continue

            grouped[
                row["group"]
            ].append(
                row
            )

    print()
    print()
    print(
        "OVERALL MARKET-INTEL "
        "HISTORICAL PORTFOLIO COMPARISON"
    )
    print("=" * 110)

    groups = [
        "Priority 3+",
        "Priority 2",
        "Priority 1",
        "Priority 0",
        "Insufficient Data",
    ]

    for group in groups:
        rows = grouped[group]

        print(
            f"{group:<20}"
            f"N={len(rows):>4}  "
            f"Avg="
            f"{format_percent(
                simple_average(rows)
            ):>9}  "
            f"Value-weighted="
            f"{format_percent(
                weighted_average(rows)
            ):>9}"
        )

    priority_rows = []

    nonpriority_rows = []

    for transition in transitions:
        for row in transition["rows"]:
            if (
                row["return_percent"]
                is None
                or row["priority"] is None
            ):
                continue

            if row["priority"] >= 3:
                priority_rows.append(
                    row
                )
            else:
                nonpriority_rows.append(
                    row
                )

    priority_return = weighted_average(
        priority_rows
    )

    nonpriority_return = weighted_average(
        nonpriority_rows
    )

    advantage = None

    if (
        priority_return is not None
        and nonpriority_return is not None
    ):
        advantage = (
            priority_return
            - nonpriority_return
        )

    print()
    print(
        f"Priority 3+ value-weighted return: "
        f"{format_percent(priority_return)}"
    )

    print(
        f"Priority 0-2 value-weighted return: "
        f"{format_percent(nonpriority_return)}"
    )

    print(
        f"Priority 3+ advantage: "
        f"{format_percent(advantage)}"
    )


def main():
    snapshot_months = (
        get_snapshot_months()
    )

    if len(snapshot_months) < 2:
        raise RuntimeError(
            "At least two Historical Portfolio "
            "snapshots are required."
        )

    transitions = []

    for index in range(
        len(snapshot_months) - 1
    ):
        transition = build_transition(
            snapshot_months[index],
            snapshot_months[index + 1],
        )

        transitions.append(
            transition
        )

        print_transition(
            transition
        )

    print_overall(
        transitions
    )


if __name__ == "__main__":
    main()