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
STARTING_VALUE = Decimal("10000")


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
                price_result = get_price_return(
                    cursor,
                    item["ticker"],
                    start_date,
                    end_date,
                    date_column,
                    price_column,
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

    priority_rows = [
        row
        for row in rows
        if (
            row["priority"] is not None
            and row["priority"] >= 3
            and row["return_percent"]
            is not None
        )
    ]

    comparison_rows = [
        row
        for row in rows
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

    comparison_return = weighted_average(
        comparison_rows
    )

    advantage = None

    if (
        priority_return is not None
        and comparison_return is not None
    ):
        advantage = (
            priority_return
            - comparison_return
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
        "priority_return":
            priority_return,
        "comparison_return":
            comparison_return,
        "advantage":
            advantage,
        "priority_count":
            len(priority_rows),
        "comparison_count":
            len(comparison_rows),
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

    print()

    print(
        f"Priority 3+ value-weighted return: "
        f"{format_percent(
            transition['priority_return']
        )}"
    )

    print(
        f"Priority 0-2 value-weighted return: "
        f"{format_percent(
            transition['comparison_return']
        )}"
    )

    print(
        f"Priority 3+ advantage: "
        f"{format_percent(
            transition['advantage']
        )}"
    )


def print_pooled_summary(transitions):
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
        "POOLED HOLDING OBSERVATIONS"
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


def apply_return(
    portfolio_value,
    return_percent,
):
    if return_percent is None:
        return portfolio_value

    multiplier = (
        Decimal("1")
        + (
            return_percent
            / Decimal("100")
        )
    )

    return (
        portfolio_value
        * multiplier
    )


def print_compounded_comparison(
    transitions,
):
    priority_value = STARTING_VALUE
    comparison_value = STARTING_VALUE

    print()
    print()
    print(
        "COMPOUNDED SNAPSHOT-TO-SNAPSHOT "
        "COMPARISON"
    )
    print("=" * 110)

    print(
        f"{'Period':<22}"
        f"{'Priority 3+':>16}"
        f"{'Priority 0-2':>16}"
        f"{'Advantage':>14}"
        f"{'MI Value':>16}"
        f"{'Compare Value':>16}"
    )

    print("-" * 110)

    periods_used = 0

    for transition in transitions:
        priority_return = (
            transition[
                "priority_return"
            ]
        )

        comparison_return = (
            transition[
                "comparison_return"
            ]
        )

        if (
            priority_return is None
            or comparison_return is None
        ):
            continue

        periods_used += 1

        priority_value = apply_return(
            priority_value,
            priority_return,
        )

        comparison_value = apply_return(
            comparison_value,
            comparison_return,
        )

        period_label = (
            f"{transition['start_month']:%Y-%m}"
            f" -> "
            f"{transition['end_month']:%Y-%m}"
        )

        print(
            f"{period_label:<22}"
            f"{format_percent(
                priority_return
            ):>16}"
            f"{format_percent(
                comparison_return
            ):>16}"
            f"{format_percent(
                transition['advantage']
            ):>14}"
            f"{format_money(
                priority_value
            ):>16}"
            f"{format_money(
                comparison_value
            ):>16}"
        )

    priority_total_return = (
        (
            priority_value
            / STARTING_VALUE
        )
        - Decimal("1")
    ) * Decimal("100")

    comparison_total_return = (
        (
            comparison_value
            / STARTING_VALUE
        )
        - Decimal("1")
    ) * Decimal("100")

    return_advantage = (
        priority_total_return
        - comparison_total_return
    )

    dollar_advantage = (
        priority_value
        - comparison_value
    )

    print("-" * 110)

    print(
        f"Periods compared: "
        f"{periods_used}"
    )

    print(
        f"Starting value: "
        f"{format_money(STARTING_VALUE)}"
    )

    print()

    print(
        f"Priority 3+ ending value: "
        f"{format_money(priority_value)}"
    )

    print(
        f"Priority 3+ compounded return: "
        f"{format_percent(
            priority_total_return
        )}"
    )

    print()

    print(
        f"Priority 0-2 ending value: "
        f"{format_money(comparison_value)}"
    )

    print(
        f"Priority 0-2 compounded return: "
        f"{format_percent(
            comparison_total_return
        )}"
    )

    print()

    print(
        f"Market-Intel return advantage: "
        f"{format_percent(
            return_advantage
        )}"
    )

    print(
        f"Market-Intel dollar advantage "
        f"on $10,000: "
        f"{format_money(
            dollar_advantage
        )}"
    )

    if priority_value > comparison_value:
        result = (
            "Priority 3+ outperformed "
            "Priority 0-2."
        )
    elif priority_value < comparison_value:
        result = (
            "Priority 3+ underperformed "
            "Priority 0-2."
        )
    else:
        result = (
            "Priority 3+ and Priority 0-2 "
            "finished equal."
        )

    print()
    print(
        f"Result: {result}"
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

    print_pooled_summary(
        transitions
    )

    print_compounded_comparison(
        transitions
    )


if __name__ == "__main__":
    main()