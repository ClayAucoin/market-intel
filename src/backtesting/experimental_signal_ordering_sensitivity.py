import random
import sys
from datetime import timedelta
from decimal import Decimal
from statistics import median

from src.analysis.experimental_signal import (
    SIGNAL_DESCRIPTION,
    get_experimental_signal_events,
)
from src.backtesting.backtester import (
    calculate_return,
    get_price_on_date,
    get_price_on_or_after,
)
from src.backtesting.time_split_statistics import (
    TRAIN_END,
    TEST_START,
    get_events,
    split_by_time,
)


DEFAULT_UNIVERSE = "expanded_500"

STARTING_CASH = Decimal("10000")
TRADE_SIZE = Decimal("1000")
HOLDING_DAYS = 45
SIMULATIONS = 1000
RANDOM_SEED = 42


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


def format_money(value):
    return f"${value:,.2f}"


def format_percent(value):
    if value is None:
        return "N/A"

    return f"{value:+.2f}%"


def get_trade_result(row):
    ticker = row["ticker"]
    entry_date = row["entry_date"]

    entry_record = get_price_on_date(
        ticker,
        entry_date,
    )

    if entry_record is None:
        return None

    entry_price = entry_record[
        "adjusted_open"
    ]

    if entry_price is None:
        return None

    target_exit_date = (
        entry_date
        + timedelta(
            days=HOLDING_DAYS
        )
    )

    exit_record = get_price_on_or_after(
        ticker,
        target_exit_date,
    )

    if exit_record is None:
        return None

    stock_return = calculate_return(
        entry_price,
        exit_record["price"],
    )

    if stock_return is None:
        return None

    profit = (
        TRADE_SIZE
        * stock_return
        / Decimal("100")
    )

    return {
        "ticker":
            ticker,

        "entry_date":
            entry_date,

        "exit_date":
            exit_record["trade_date"],

        "investment":
            TRADE_SIZE,

        "return":
            stock_return,

        "profit":
            profit,

        "exit_value":
            TRADE_SIZE + profit,
    }


def build_trade_results(rows):
    trades = []

    for row in rows:
        trade = get_trade_result(
            row
        )

        if trade is not None:
            trades.append(
                trade
            )

    return trades


def group_by_entry_date(trades):
    grouped = {}

    for trade in trades:
        entry_date = trade[
            "entry_date"
        ]

        grouped.setdefault(
            entry_date,
            [],
        ).append(
            trade
        )

    return grouped


def close_due_positions(
    positions,
    cash,
    current_date,
):
    still_open = []

    for position in positions:
        if (
            position["exit_date"]
            <= current_date
        ):
            cash += position[
                "exit_value"
            ]
        else:
            still_open.append(
                position
            )

    return (
        still_open,
        cash,
    )


def simulate_order(
    grouped,
    rng=None,
    alphabetical=False,
):
    cash = STARTING_CASH
    open_positions = []

    trades_taken = 0
    cash_skips = 0

    for entry_date in sorted(
        grouped
    ):
        (
            open_positions,
            cash,
        ) = close_due_positions(
            open_positions,
            cash,
            entry_date,
        )

        day_trades = list(
            grouped[entry_date]
        )

        if alphabetical:
            day_trades.sort(
                key=lambda trade:
                    trade["ticker"]
            )
        else:
            rng.shuffle(
                day_trades
            )

        for trade in day_trades:
            if cash < TRADE_SIZE:
                cash_skips += 1
                continue

            open_positions.append(
                trade
            )

            cash -= TRADE_SIZE
            trades_taken += 1

    for position in open_positions:
        cash += position[
            "exit_value"
        ]

    profit = (
        cash
        - STARTING_CASH
    )

    total_return = (
        profit
        / STARTING_CASH
        * Decimal("100")
    )

    return {
        "trades":
            trades_taken,

        "cash_skips":
            cash_skips,

        "profit":
            profit,

        "final_value":
            cash,

        "return":
            total_return,
    }


def percentile(
    values,
    percent,
):
    if not values:
        return None

    ordered = sorted(
        values
    )

    index = int(
        (
            len(ordered) - 1
        )
        * percent
    )

    return ordered[
        index
    ]


def run_random_simulations(
    grouped,
):
    rng = random.Random(
        RANDOM_SEED
    )

    results = []

    for _ in range(
        SIMULATIONS
    ):
        results.append(
            simulate_order(
                grouped,
                rng=rng,
            )
        )

    return results


def print_period(
    title,
    rows,
):
    trades = build_trade_results(
        rows
    )

    grouped = group_by_entry_date(
        trades
    )

    alphabetical_result = (
        simulate_order(
            grouped,
            alphabetical=True,
        )
    )

    random_results = (
        run_random_simulations(
            grouped
        )
    )

    returns = [
        result["return"]
        for result in random_results
    ]

    profits = [
        result["profit"]
        for result in random_results
    ]

    trade_counts = [
        result["trades"]
        for result in random_results
    ]

    skip_counts = [
        result["cash_skips"]
        for result in random_results
    ]

    average_return = (
        sum(
            returns,
            Decimal("0"),
        )
        / Decimal(
            len(returns)
        )
    )

    average_profit = (
        sum(
            profits,
            Decimal("0"),
        )
        / Decimal(
            len(profits)
        )
    )

    median_return = Decimal(
        str(
            median(
                returns
            )
        )
    )

    print()
    print(title)
    print("=" * 100)

    print(
        "Completed signal trades:",
        len(trades),
    )

    print(
        "Entry dates:",
        len(grouped),
    )

    print()
    print(
        "ALPHABETICAL BASELINE"
    )

    print("-" * 100)

    print(
        "Trades taken:",
        alphabetical_result[
            "trades"
        ],
    )

    print(
        "Cash skips:",
        alphabetical_result[
            "cash_skips"
        ],
    )

    print(
        "Profit:",
        format_money(
            alphabetical_result[
                "profit"
            ]
        ),
    )

    print(
        "Final value:",
        format_money(
            alphabetical_result[
                "final_value"
            ]
        ),
    )

    print(
        "Return:",
        format_percent(
            alphabetical_result[
                "return"
            ]
        ),
    )

    print()
    print(
        f"RANDOM SAME-DAY ORDER — "
        f"{SIMULATIONS:,} SIMULATIONS"
    )

    print("-" * 100)

    print(
        "Average return:",
        format_percent(
            average_return
        ),
    )

    print(
        "Median return:",
        format_percent(
            median_return
        ),
    )

    print(
        "5th percentile:",
        format_percent(
            percentile(
                returns,
                Decimal("0.05"),
            )
        ),
    )

    print(
        "25th percentile:",
        format_percent(
            percentile(
                returns,
                Decimal("0.25"),
            )
        ),
    )

    print(
        "75th percentile:",
        format_percent(
            percentile(
                returns,
                Decimal("0.75"),
            )
        ),
    )

    print(
        "95th percentile:",
        format_percent(
            percentile(
                returns,
                Decimal("0.95"),
            )
        ),
    )

    print(
        "Worst return:",
        format_percent(
            min(
                returns
            )
        ),
    )

    print(
        "Best return:",
        format_percent(
            max(
                returns
            )
        ),
    )

    print(
        "Average profit:",
        format_money(
            average_profit
        ),
    )

    print(
        "Trade count range:",
        f"{min(trade_counts)}"
        f" - "
        f"{max(trade_counts)}",
    )

    print(
        "Cash skip range:",
        f"{min(skip_counts)}"
        f" - "
        f"{max(skip_counts)}",
    )

    below_baseline = sum(
        1
        for value in returns
        if value
        < alphabetical_result[
            "return"
        ]
    )

    above_baseline = sum(
        1
        for value in returns
        if value
        > alphabetical_result[
            "return"
        ]
    )

    print()
    print(
        "Random runs below alphabetical:",
        below_baseline,
    )

    print(
        "Random runs above alphabetical:",
        above_baseline,
    )


def main():
    universe_name = (
        get_universe_name()
    )

    rows = get_events(
        universe_name
    )

    training, testing = (
        split_by_time(
            rows
        )
    )

    training_matches = (
        get_experimental_signal_events(
            training
        )
    )

    testing_matches = (
        get_experimental_signal_events(
            testing
        )
    )

    print()
    print(
        "EXPERIMENTAL SIGNAL "
        "ORDERING SENSITIVITY TEST"
    )

    print("=" * 100)

    print(
        "Universe:",
        universe_name,
    )

    print(
        "Signal:",
        SIGNAL_DESCRIPTION,
    )

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
        "Holding period:",
        f"{HOLDING_DAYS} calendar days",
    )

    print(
        "Random simulations:",
        f"{SIMULATIONS:,}",
    )

    print(
        "Random seed:",
        RANDOM_SEED,
    )

    print(
        "Training through:",
        TRAIN_END,
    )

    print(
        "Out-of-sample from:",
        TEST_START,
    )

    print(
        "Training signal matches:",
        len(
            training_matches
        ),
    )

    print(
        "Out-of-sample signal matches:",
        len(
            testing_matches
        ),
    )

    print_period(
        "TRAINING — ORDERING SENSITIVITY",
        training_matches,
    )

    print_period(
        "OUT-OF-SAMPLE — ORDERING SENSITIVITY",
        testing_matches,
    )


if __name__ == "__main__":
    main()