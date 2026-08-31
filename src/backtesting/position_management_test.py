from datetime import timedelta
from decimal import Decimal

from src.backtesting.capital_constrained_backtest import (
    STARTING_CASH,
    TRADE_SIZE,
    build_candidate_trades,
)
from src.backtesting.recommendation_backtest import (
    get_backtest_events,
)
from src.backtesting.time_split_statistics import (
    split_by_time,
)


HOLDING_DAYS = 180


def format_money(value):
    return f"${value:,.2f}"


def format_percent(value):
    return f"{value:+.2f}%"


def get_candidates():
    rows = get_backtest_events()

    training, testing = split_by_time(
        rows
    )

    return build_candidate_trades(
        testing,
        rows,
    )


def calculate_exit_value(
    investment,
    return_percent,
):
    profit = (
        investment
        * return_percent
        / Decimal("100")
    )

    return (
        investment + profit,
        profit,
    )


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


def finish_positions(
    positions,
    cash,
):
    for position in positions:
        cash += position[
            "exit_value"
        ]

    return (
        cash,
        list(positions),
    )


def build_position(
    row,
):
    return_percent = row[
        "return_180d"
    ]

    (
        exit_value,
        profit,
    ) = calculate_exit_value(
        TRADE_SIZE,
        return_percent,
    )

    return {
        "ticker":
            row["ticker"],

        "entry_date":
            row["entry_date"],

        "exit_date":
            (
                row["entry_date"]
                + timedelta(
                    days=HOLDING_DAYS
                )
            ),

        "priority":
            row["priority"],

        "score":
            row["score"],

        "investment":
            TRADE_SIZE,

        "return":
            return_percent,

        "profit":
            profit,

        "exit_value":
            exit_value,

        "extensions":
            0,
    }


def simulate_current_behavior(
    candidates,
):
    cash = STARTING_CASH

    open_positions = []
    completed = []

    skipped_cash = 0

    for row in candidates:
        entry_date = row[
            "entry_date"
        ]

        (
            open_positions,
            cash,
            closed,
        ) = close_due_positions(
            open_positions,
            cash,
            entry_date,
        )

        completed.extend(
            closed
        )

        if cash < TRADE_SIZE:
            skipped_cash += 1
            continue

        position = build_position(
            row
        )

        open_positions.append(
            position
        )

        cash -= TRADE_SIZE

    cash, closed = finish_positions(
        open_positions,
        cash,
    )

    completed.extend(
        closed
    )

    return {
        "cash":
            cash,

        "completed":
            completed,

        "skipped_cash":
            skipped_cash,

        "skipped_existing":
            0,

        "extensions":
            0,
    }


def simulate_one_position_per_ticker(
    candidates,
):
    cash = STARTING_CASH

    open_positions = []
    completed = []

    skipped_cash = 0
    skipped_existing = 0

    for row in candidates:
        entry_date = row[
            "entry_date"
        ]

        (
            open_positions,
            cash,
            closed,
        ) = close_due_positions(
            open_positions,
            cash,
            entry_date,
        )

        completed.extend(
            closed
        )

        ticker_is_open = any(
            position["ticker"]
            == row["ticker"]
            for position
            in open_positions
        )

        if ticker_is_open:
            skipped_existing += 1
            continue

        if cash < TRADE_SIZE:
            skipped_cash += 1
            continue

        position = build_position(
            row
        )

        open_positions.append(
            position
        )

        cash -= TRADE_SIZE

    cash, closed = finish_positions(
        open_positions,
        cash,
    )

    completed.extend(
        closed
    )

    return {
        "cash":
            cash,

        "completed":
            completed,

        "skipped_cash":
            skipped_cash,

        "skipped_existing":
            skipped_existing,

        "extensions":
            0,
    }


def simulate_extend_existing(
    candidates,
):
    cash = STARTING_CASH

    open_positions = []
    completed = []

    skipped_cash = 0
    extensions = 0

    for row in candidates:
        entry_date = row[
            "entry_date"
        ]

        (
            open_positions,
            cash,
            closed,
        ) = close_due_positions(
            open_positions,
            cash,
            entry_date,
        )

        completed.extend(
            closed
        )

        existing = None

        for position in open_positions:
            if (
                position["ticker"]
                == row["ticker"]
            ):
                existing = position
                break

        if existing is not None:
            extensions += 1

            existing[
                "exit_date"
            ] = (
                entry_date
                + timedelta(
                    days=HOLDING_DAYS
                )
            )

            existing[
                "extensions"
            ] += 1

            continue

        if cash < TRADE_SIZE:
            skipped_cash += 1
            continue

        position = build_position(
            row
        )

        open_positions.append(
            position
        )

        cash -= TRADE_SIZE

    cash, closed = finish_positions(
        open_positions,
        cash,
    )

    completed.extend(
        closed
    )

    return {
        "cash":
            cash,

        "completed":
            completed,

        "skipped_cash":
            skipped_cash,

        "skipped_existing":
            0,

        "extensions":
            extensions,
    }


def calculate_stats(
    result,
):
    completed = result[
        "completed"
    ]

    final_value = result[
        "cash"
    ]

    profit = (
        final_value
        - STARTING_CASH
    )

    total_return = (
        profit
        / STARTING_CASH
        * Decimal("100")
    )

    winners = sum(
        1
        for position in completed
        if position["profit"] > 0
    )

    win_rate = (
        Decimal(winners)
        / Decimal(len(completed))
        * Decimal("100")
        if completed
        else Decimal("0")
    )

    return {
        "positions":
            len(completed),

        "profit":
            profit,

        "final_value":
            final_value,

        "return":
            total_return,

        "win_rate":
            win_rate,

        "skipped_cash":
            result[
                "skipped_cash"
            ],

        "skipped_existing":
            result[
                "skipped_existing"
            ],

        "extensions":
            result[
                "extensions"
            ],
    }


def print_comparison(
    candidates,
):
    tests = [
        (
            "A. Current behavior",
            simulate_current_behavior(
                candidates
            ),
        ),
        (
            "B. One position/ticker",
            simulate_one_position_per_ticker(
                candidates
            ),
        ),
        (
            "C. Extend existing",
            simulate_extend_existing(
                candidates
            ),
        ),
    ]

    print()
    print(
        "POSITION MANAGEMENT TEST"
    )

    print("=" * 145)

    print(
        f"{'Policy':<26}"
        f"{'Positions':>11}"
        f"{'Win Rate':>12}"
        f"{'Cash Skip':>11}"
        f"{'Own Skip':>11}"
        f"{'Extensions':>12}"
        f"{'Profit':>16}"
        f"{'Final Value':>18}"
        f"{'Return':>13}"
    )

    print("-" * 145)

    for name, result in tests:
        stats = calculate_stats(
            result
        )

        print(
            f"{name:<26}"
            f"{stats['positions']:>11}"
            f"{format_percent(stats['win_rate']):>12}"
            f"{stats['skipped_cash']:>11}"
            f"{stats['skipped_existing']:>11}"
            f"{stats['extensions']:>12}"
            f"{format_money(stats['profit']):>16}"
            f"{format_money(stats['final_value']):>18}"
            f"{format_percent(stats['return']):>13}"
        )


def print_repeated_signals(
    candidates,
):
    by_ticker = {}

    for row in candidates:
        by_ticker.setdefault(
            row["ticker"],
            [],
        ).append(
            row
        )

    repeated = {
        ticker: rows
        for ticker, rows
        in by_ticker.items()
        if len(rows) > 1
    }

    print()
    print(
        "REPEATED QUALIFYING SIGNALS"
    )

    print("=" * 110)

    for ticker in sorted(
        repeated
    ):
        rows = repeated[
            ticker
        ]

        print()
        print(
            f"{ticker}: "
            f"{len(rows)} signals"
        )

        for row in rows:
            print(
                "  "
                f"{row['entry_date']}  "
                f"Priority {row['priority']}  "
                f"Score {row['score']}  "
                f"180d {format_percent(row['return_180d'])}"
            )


def main():
    candidates = get_candidates()

    print_comparison(
        candidates
    )

    print_repeated_signals(
        candidates
    )


if __name__ == "__main__":
    main()