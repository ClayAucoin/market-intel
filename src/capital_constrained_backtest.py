from datetime import timedelta
from decimal import Decimal

from src.recommendation_backtest import (
    add_historical_recommendations,
    get_backtest_events,
)
from src.time_split_statistics import (
    split_by_time,
)


STARTING_CASH = Decimal("10000")
TRADE_SIZE = Decimal("1000")
MINIMUM_PRIORITY = 3
HOLDING_DAYS = 180


def format_money(value):
    return f"${value:,.2f}"


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def close_due_positions(
    positions,
    cash,
    current_date,
):
    still_open = []

    closed = []

    for position in positions:
        if (
            position["exit_date"]
            <= current_date
        ):
            cash += position[
                "exit_value"
            ]

            closed.append(
                position
            )

        else:
            still_open.append(
                position
            )

    return (
        still_open,
        cash,
        closed,
    )


def build_candidate_trades(
    testing_rows,
    all_rows,
):
    scored = (
        add_historical_recommendations(
            testing_rows,
            all_rows,
        )
    )

    candidates = []

    for row in scored:
        if (
            row["priority"]
            < MINIMUM_PRIORITY
        ):
            continue

        if (
            row.get("return_180d")
            is None
        ):
            continue

        candidates.append(
            row
        )

    candidates.sort(
        key=lambda row: (
            row["entry_date"],
            -row["priority"],
            -row["score"],
            row["ticker"],
        )
    )

    return candidates


def simulate_portfolio(
    candidates,
):
    cash = STARTING_CASH

    open_positions = []

    completed_positions = []

    skipped_signals = []

    transactions = []

    for row in candidates:
        entry_date = row[
            "entry_date"
        ]

        (
            open_positions,
            cash,
            newly_closed,
        ) = close_due_positions(
            open_positions,
            cash,
            entry_date,
        )

        completed_positions.extend(
            newly_closed
        )

        for position in newly_closed:
            transactions.append(
                {
                    "date":
                        position[
                            "exit_date"
                        ],

                    "type":
                        "SELL",

                    "ticker":
                        position[
                            "ticker"
                        ],

                    "amount":
                        position[
                            "exit_value"
                        ],

                    "profit":
                        position[
                            "profit"
                        ],
                }
            )

        if cash < TRADE_SIZE:
            skipped_signals.append(
                {
                    **row,
                    "skip_reason":
                        "Insufficient cash",
                }
            )

            continue

        stock_return = row[
            "return_180d"
        ]

        profit = (
            TRADE_SIZE
            * stock_return
            / Decimal("100")
        )

        exit_value = (
            TRADE_SIZE
            + profit
        )

        exit_date = (
            entry_date
            + timedelta(
                days=HOLDING_DAYS
            )
        )

        position = {
            "ticker":
                row["ticker"],

            "sector":
                row["sector"],

            "entry_date":
                entry_date,

            "exit_date":
                exit_date,

            "priority":
                row["priority"],

            "score":
                row["score"],

            "sector_confidence":
                row[
                    "sector_confidence"
                ],

            "recommendation":
                row[
                    "recommendation"
                ],

            "investment":
                TRADE_SIZE,

            "return":
                stock_return,

            "profit":
                profit,

            "exit_value":
                exit_value,
        }

        open_positions.append(
            position
        )

        cash -= TRADE_SIZE

        transactions.append(
            {
                "date":
                    entry_date,

                "type":
                    "BUY",

                "ticker":
                    row["ticker"],

                "amount":
                    TRADE_SIZE,

                "profit":
                    None,
            }
        )

    if candidates:
        final_date = max(
            row["entry_date"]
            for row in candidates
        ) + timedelta(
            days=HOLDING_DAYS
        )

        (
            open_positions,
            cash,
            newly_closed,
        ) = close_due_positions(
            open_positions,
            cash,
            final_date,
        )

        completed_positions.extend(
            newly_closed
        )

        for position in newly_closed:
            transactions.append(
                {
                    "date":
                        position[
                            "exit_date"
                        ],

                    "type":
                        "SELL",

                    "ticker":
                        position[
                            "ticker"
                        ],

                    "amount":
                        position[
                            "exit_value"
                        ],

                    "profit":
                        position[
                            "profit"
                        ],
                }
            )

    transactions.sort(
        key=lambda item: (
            item["date"],
            item["type"],
            item["ticker"],
        )
    )

    return {
        "cash":
            cash,

        "completed_positions":
            completed_positions,

        "open_positions":
            open_positions,

        "skipped_signals":
            skipped_signals,

        "transactions":
            transactions,
    }


def calculate_summary(
    result,
):
    completed = result[
        "completed_positions"
    ]

    final_value = result[
        "cash"
    ]

    total_profit = (
        final_value
        - STARTING_CASH
    )

    total_return = (
        total_profit
        / STARTING_CASH
        * Decimal("100")
    )

    winners = [
        position
        for position in completed
        if position["profit"] > 0
    ]

    losers = [
        position
        for position in completed
        if position["profit"] < 0
    ]

    win_rate = None

    if completed:
        win_rate = (
            Decimal(
                len(winners)
            )
            / Decimal(
                len(completed)
            )
            * Decimal("100")
        )

    return {
        "final_value":
            final_value,

        "profit":
            total_profit,

        "return":
            total_return,

        "completed":
            len(completed),

        "winners":
            len(winners),

        "losers":
            len(losers),

        "win_rate":
            win_rate,

        "skipped":
            len(
                result[
                    "skipped_signals"
                ]
            ),
    }


def print_summary(
    result,
):
    summary = calculate_summary(
        result
    )

    print()
    print(
        "CAPITAL-CONSTRAINED PORTFOLIO BACKTEST"
    )

    print("=" * 80)

    print(
        "Starting cash:",
        format_money(
            STARTING_CASH
        ),
    )

    print(
        "Trade size:",
        format_money(
            TRADE_SIZE
        ),
    )

    print(
        "Minimum priority:",
        MINIMUM_PRIORITY,
    )

    print(
        "Holding period:",
        f"{HOLDING_DAYS} days",
    )

    print()

    print(
        "Completed trades:",
        summary[
            "completed"
        ],
    )

    print(
        "Winning trades:",
        summary[
            "winners"
        ],
    )

    print(
        "Losing trades:",
        summary[
            "losers"
        ],
    )

    print(
        "Win rate:",
        format_percent(
            summary[
                "win_rate"
            ]
        ),
    )

    print(
        "Skipped signals:",
        summary[
            "skipped"
        ],
    )

    print()

    print(
        "Final account value:",
        format_money(
            summary[
                "final_value"
            ]
        ),
    )

    print(
        "Total profit:",
        format_money(
            summary[
                "profit"
            ]
        ),
    )

    print(
        "Total return:",
        format_percent(
            summary[
                "return"
            ]
        ),
    )


def print_completed_trades(
    result,
):
    trades = sorted(
        result[
            "completed_positions"
        ],
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        ),
    )

    print()
    print(
        "COMPLETED TRADES"
    )

    print("=" * 150)

    print(
        f"{'Ticker':<8}"
        f"{'Entry':>12}"
        f"{'Exit':>12}"
        f"{'Priority':>10}"
        f"{'Score':>8}"
        f"{'Sector Conf':<16}"
        f"{'Return':>12}"
        f"{'Profit':>14}"
        f"{'Exit Value':>14}"
    )

    print("-" * 150)

    for trade in trades:
        print(
            f"{trade['ticker']:<8}"
            f"{str(trade['entry_date']):>12}"
            f"{str(trade['exit_date']):>12}"
            f"{trade['priority']:>10}"
            f"{trade['score']:>8}"
            f"{trade['sector_confidence']:<16}"
            f"{format_percent(trade['return']):>12}"
            f"{format_money(trade['profit']):>14}"
            f"{format_money(trade['exit_value']):>14}"
        )


def print_skipped_signals(
    result,
):
    skipped = result[
        "skipped_signals"
    ]

    print()
    print(
        "SKIPPED SIGNALS"
    )

    print("=" * 125)

    if not skipped:
        print(
            "None"
        )

        return

    print(
        f"{'Ticker':<8}"
        f"{'Entry':>12}"
        f"{'Priority':>10}"
        f"{'Score':>8}"
        f"{'Sector Conf':<16}"
        f"{'Reason':<30}"
    )

    print("-" * 125)

    for row in skipped:
        print(
            f"{row['ticker']:<8}"
            f"{str(row['entry_date']):>12}"
            f"{row['priority']:>10}"
            f"{row['score']:>8}"
            f"{row['sector_confidence']:<16}"
            f"{row['skip_reason']:<30}"
        )


def print_transactions(
    result,
):
    transactions = result[
        "transactions"
    ]

    print()
    print(
        "TRANSACTION TIMELINE"
    )

    print("=" * 90)

    print(
        f"{'Date':<12}"
        f"{'Type':<8}"
        f"{'Ticker':<8}"
        f"{'Amount':>16}"
        f"{'Profit':>16}"
    )

    print("-" * 90)

    for item in transactions:
        profit = (
            "-"
            if item["profit"] is None
            else format_money(
                item["profit"]
            )
        )

        print(
            f"{str(item['date']):<12}"
            f"{item['type']:<8}"
            f"{item['ticker']:<8}"
            f"{format_money(item['amount']):>16}"
            f"{profit:>16}"
        )


def main():
    rows = get_backtest_events()

    training, testing = split_by_time(
        rows
    )

    candidates = (
        build_candidate_trades(
            testing,
            rows,
        )
    )

    result = simulate_portfolio(
        candidates
    )

    print_summary(
        result
    )

    print_completed_trades(
        result
    )

    print_skipped_signals(
        result
    )

    print_transactions(
        result
    )


if __name__ == "__main__":
    main()