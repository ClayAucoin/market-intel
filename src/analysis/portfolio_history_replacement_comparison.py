from decimal import Decimal

from src.database import get_connection

from src.analysis.portfolio_history_stock_performance import (
    build_history,
)

from src.analysis.portfolio_history_stock_performance_summary import (
    get_portfolio_tickers,
)


PORTFOLIO_NAME = "Historical Portfolio"


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


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def format_money(value):
    if value is None:
        return "-"

    if value >= 0:
        return f"+${value:,.2f}"

    return f"-${abs(value):,.2f}"


def get_snapshot_months():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT snapshot_month
                FROM portfolio_snapshots
                WHERE portfolio_name = %s
                ORDER BY snapshot_month;
                """,
                (PORTFOLIO_NAME,),
            )

            return [
                row[0]
                for row in cursor.fetchall()
            ]


def get_history_map():
    histories = {}

    for ticker in get_portfolio_tickers():
        actual_ticker, rows = build_history(
            ticker
        )

        histories[actual_ticker] = {
            row["month"]: row
            for row in rows
        }

    return histories


def find_changes(
    histories,
    earlier_month,
    later_month,
):
    removed = []
    added = []

    for ticker, history in histories.items():
        earlier = history.get(
            earlier_month
        )

        later = history.get(
            later_month
        )

        if (
            earlier is None
            or later is None
        ):
            continue

        if (
            earlier["held"]
            and not later["held"]
        ):
            removed.append(
                ticker
            )

        if (
            not earlier["held"]
            and later["held"]
        ):
            added.append(
                ticker
            )

    return (
        sorted(removed),
        sorted(added),
    )


def analyze_removed(
    ticker,
    history,
    earlier_month,
    later_month,
    latest_month,
):
    earlier = history[
        earlier_month
    ]

    later = history[
        later_month
    ]

    latest = history[
        latest_month
    ]

    return_percent = None
    estimated_change = None

    if (
        later_month < latest_month
        and later["adjusted_price"] is not None
        and latest["adjusted_price"] is not None
    ):
        return_percent = percent_change(
            later["adjusted_price"],
            latest["adjusted_price"],
        )

        if (
            earlier["market_value"]
            is not None
            and return_percent is not None
        ):
            estimated_change = (
                Decimal(
                    str(
                        earlier[
                            "market_value"
                        ]
                    )
                )
                * return_percent
                / Decimal("100")
            )

    return {
        "ticker": ticker,
        "starting_value": (
            earlier["market_value"]
        ),
        "return_percent": (
            return_percent
        ),
        "estimated_change": (
            estimated_change
        ),
    }


def analyze_added(
    ticker,
    history,
    later_month,
    latest_month,
):
    later = history[
        later_month
    ]

    latest = history[
        latest_month
    ]

    return_percent = None
    estimated_change = None

    if (
        later_month < latest_month
        and later["adjusted_price"] is not None
        and latest["adjusted_price"] is not None
    ):
        return_percent = percent_change(
            later["adjusted_price"],
            latest["adjusted_price"],
        )

        if (
            later["market_value"]
            is not None
            and return_percent is not None
        ):
            estimated_change = (
                Decimal(
                    str(
                        later[
                            "market_value"
                        ]
                    )
                )
                * return_percent
                / Decimal("100")
            )

    return {
        "ticker": ticker,
        "starting_value": (
            later["market_value"]
        ),
        "return_percent": (
            return_percent
        ),
        "estimated_change": (
            estimated_change
        ),
    }


def summarize_group(rows):
    usable = [
        row
        for row in rows
        if (
            row["return_percent"]
            is not None
            and row[
                "starting_value"
            ] is not None
            and row[
                "estimated_change"
            ] is not None
        )
    ]

    if not usable:
        return {
            "count": len(rows),
            "usable": 0,
            "starting_value": None,
            "change": None,
            "weighted_return": None,
            "average_return": None,
        }

    starting_value = sum(
        (
            Decimal(
                str(
                    row[
                        "starting_value"
                    ]
                )
            )
            for row in usable
        ),
        Decimal("0"),
    )

    change = sum(
        (
            row[
                "estimated_change"
            ]
            for row in usable
        ),
        Decimal("0"),
    )

    if starting_value == 0:
        weighted_return = None
    else:
        weighted_return = (
            change
            / starting_value
            * Decimal("100")
        )

    average_return = (
        sum(
            (
                row[
                    "return_percent"
                ]
                for row in usable
            ),
            Decimal("0"),
        )
        / Decimal(
            len(usable)
        )
    )

    return {
        "count": len(rows),
        "usable": len(usable),
        "starting_value": (
            starting_value
        ),
        "change": change,
        "weighted_return": (
            weighted_return
        ),
        "average_return": (
            average_return
        ),
    }


def build_transition(
    histories,
    earlier_month,
    later_month,
    latest_month,
):
    removed_tickers, added_tickers = (
        find_changes(
            histories,
            earlier_month,
            later_month,
        )
    )

    if (
        not removed_tickers
        and not added_tickers
    ):
        return None

    removed = [
        analyze_removed(
            ticker,
            histories[ticker],
            earlier_month,
            later_month,
            latest_month,
        )
        for ticker in removed_tickers
    ]

    added = [
        analyze_added(
            ticker,
            histories[ticker],
            later_month,
            latest_month,
        )
        for ticker in added_tickers
    ]

    return {
        "earlier_month": earlier_month,
        "later_month": later_month,
        "removed": removed,
        "added": added,
        "removed_summary": (
            summarize_group(
                removed
            )
        ),
        "added_summary": (
            summarize_group(
                added
            )
        ),
    }


def print_stock_rows(
    title,
    rows,
):
    print()
    print(title)

    if not rows:
        print("  None")
        return

    for row in rows:
        print(
            f"  {row['ticker']:<8}"
            f" Return "
            f"{format_percent(row['return_percent']):>9}"
            f"   Estimated "
            f"{format_money(row['estimated_change']):>12}"
        )


def print_transition(
    transition,
    latest_month,
):
    earlier = (
        transition[
            "earlier_month"
        ]
        .strftime("%Y-%m")
    )

    later = (
        transition[
            "later_month"
        ]
        .strftime("%Y-%m")
    )

    latest = latest_month.strftime(
        "%Y-%m"
    )

    removed_summary = (
        transition[
            "removed_summary"
        ]
    )

    added_summary = (
        transition[
            "added_summary"
        ]
    )

    print()
    print("=" * 90)

    print(
        f"TRANSITION: "
        f"{earlier} -> {later}"
    )

    print(
        f"Follow-up through: "
        f"{latest}"
    )

    print_stock_rows(
        "REMOVED",
        transition["removed"],
    )

    print_stock_rows(
        "ADDED",
        transition["added"],
    )

    print()
    print("GROUP RESULT")

    print(
        "  Removed stocks if held: "
        f"{format_percent(removed_summary['weighted_return'])}"
    )

    print(
        "  Added stocks:           "
        f"{format_percent(added_summary['weighted_return'])}"
    )

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

    if (
        not transition["removed"]
        or not transition["added"]
    ):
        print(
            "  Replacement comparison: "
            "Not a complete remove/add transition."
        )

        return

    if (
        removed_return is None
        or added_return is None
    ):
        print(
            "  Replacement comparison: "
            "Too soon to evaluate."
        )

        return

    advantage = (
        added_return
        - removed_return
    )

    print(
        "  Replacement advantage:  "
        f"{format_percent(advantage)}"
    )

    if advantage > 0:
        print(
            "  Verdict: Replacements "
            "outperformed removed stocks."
        )

    elif advantage < 0:
        print(
            "  Verdict: Removed stocks "
            "would have performed better."
        )

    else:
        print(
            "  Verdict: No difference."
        )


def print_overall(
    transitions,
):
    comparable = []

    for transition in transitions:
        removed_summary = (
            transition[
                "removed_summary"
            ]
        )

        added_summary = (
            transition[
                "added_summary"
            ]
        )

        if (
            transition["removed"]
            and transition["added"]
            and removed_summary[
                "weighted_return"
            ] is not None
            and added_summary[
                "weighted_return"
            ] is not None
        ):
            comparable.append(
                transition
            )

    print()
    print("=" * 90)
    print("OVERALL REPLACEMENT SUMMARY")
    print("=" * 90)

    print(
        f"Snapshot transitions with changes: "
        f"{len(transitions)}"
    )

    print(
        f"Comparable remove/add transitions: "
        f"{len(comparable)}"
    )

    if not comparable:
        print(
            "Not enough follow-up data "
            "for an overall comparison."
        )
        return

    advantages = []

    positive = 0
    negative = 0
    neutral = 0

    removed_start_total = Decimal("0")
    removed_change_total = Decimal("0")

    added_start_total = Decimal("0")
    added_change_total = Decimal("0")

    for transition in comparable:
        removed_summary = (
            transition[
                "removed_summary"
            ]
        )

        added_summary = (
            transition[
                "added_summary"
            ]
        )

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

        advantage = (
            added_return
            - removed_return
        )

        advantages.append(
            advantage
        )

        if advantage > 0:
            positive += 1

        elif advantage < 0:
            negative += 1

        else:
            neutral += 1

        removed_start_total += (
            removed_summary[
                "starting_value"
            ]
        )

        removed_change_total += (
            removed_summary[
                "change"
            ]
        )

        added_start_total += (
            added_summary[
                "starting_value"
            ]
        )

        added_change_total += (
            added_summary[
                "change"
            ]
        )

    average_advantage = (
        sum(
            advantages,
            Decimal("0"),
        )
        / Decimal(
            len(advantages)
        )
    )

    if removed_start_total == 0:
        removed_weighted_return = None
    else:
        removed_weighted_return = (
            removed_change_total
            / removed_start_total
            * Decimal("100")
        )

    if added_start_total == 0:
        added_weighted_return = None
    else:
        added_weighted_return = (
            added_change_total
            / added_start_total
            * Decimal("100")
        )

    if (
        removed_weighted_return is None
        or added_weighted_return is None
    ):
        overall_advantage = None
    else:
        overall_advantage = (
            added_weighted_return
            - removed_weighted_return
        )

    dollar_difference = (
        added_change_total
        - removed_change_total
    )

    print(
        f"Replacement decisions helped: "
        f"{positive}"
    )

    print(
        f"Replacement decisions hurt: "
        f"{negative}"
    )

    print(
        f"Neutral: "
        f"{neutral}"
    )

    print()
    print(
        "Average transition advantage: "
        f"{format_percent(average_advantage)}"
    )

    print()
    print("DOLLAR-WEIGHTED COMPARISON")
    print("-" * 90)

    print(
        "Removed positions starting value: "
        f"${removed_start_total:,.2f}"
    )

    print(
        "Removed positions if held change: "
        f"{format_money(removed_change_total)}"
    )

    print(
        "Removed positions weighted return: "
        f"{format_percent(removed_weighted_return)}"
    )

    print()

    print(
        "Added positions starting value:   "
        f"${added_start_total:,.2f}"
    )

    print(
        "Added positions estimated change: "
        f"{format_money(added_change_total)}"
    )

    print(
        "Added positions weighted return:  "
        f"{format_percent(added_weighted_return)}"
    )

    print()

    print(
        "Dollar change difference:         "
        f"{format_money(dollar_difference)}"
    )

    print(
        "Weighted replacement advantage:  "
        f"{format_percent(overall_advantage)}"
    )

    print()

    if overall_advantage is None:
        print(
            "Overall observed result: "
            "NOT ENOUGH DATA"
        )

    elif overall_advantage > 0:
        print(
            "Overall observed result: "
            "REPLACEMENTS HELPED"
        )

    elif overall_advantage < 0:
        print(
            "Overall observed result: "
            "REPLACEMENTS HURT"
        )

    else:
        print(
            "Overall observed result: "
            "NEUTRAL"
        )

    print()
    print(
        "Dollar change difference compares the "
        "observed change in the added positions "
        "with the hypothetical change in the "
        "removed positions if they had remained held."
    )

    print(
        "Because the removed and added groups can "
        "have different starting values, the dollar "
        "difference and percentage advantage answer "
        "slightly different questions."
    )


def main():
    months = get_snapshot_months()

    if len(months) < 2:
        print(
            "At least two snapshots are "
            "required."
        )
        return

    histories = get_history_map()

    latest_month = months[-1]

    transitions = []

    for index in range(
        1,
        len(months),
    ):
        transition = build_transition(
            histories,
            months[index - 1],
            months[index],
            latest_month,
        )

        if transition is not None:
            transitions.append(
                transition
            )

    print()
    print(
        "HISTORICAL PORTFOLIO "
        "REPLACEMENT COMPARISON"
    )

    print("=" * 90)

    print(
        "Latest available snapshot: "
        f"{latest_month}"
    )

    print()
    print(
        "Returns use the later snapshot "
        "as the observation point because "
        "exact transaction dates are not available."
    )

    print(
        "Missing monthly snapshots create "
        "longer observation intervals and do "
        "not imply a transaction date."
    )

    for transition in transitions:
        print_transition(
            transition,
            latest_month,
        )

    print_overall(
        transitions
    )


if __name__ == "__main__":
    main()