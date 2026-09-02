import sys
from datetime import timedelta
from decimal import Decimal

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

TRADE_SIZE = Decimal("1000")
HOLDING_DAYS = 45

STARTING_CAPITAL_LEVELS = [
    Decimal("10000"),
    Decimal("12000"),
    Decimal("15000"),
    Decimal("20000"),
]


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

        "return":
            stock_return,

        "profit":
            profit,

        "exit_value":
            TRADE_SIZE + profit,
    }


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


def simulate_portfolio(
    rows,
    starting_cash,
):
    ordered = sorted(
        rows,
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        )
    )

    cash = starting_cash
    open_positions = []

    trades_taken = 0
    skipped_cash = 0
    missing_price = 0

    max_open = 0
    max_invested = Decimal("0")

    total_trade_profit = Decimal("0")
    winners = 0

    for row in ordered:
        entry_date = row[
            "entry_date"
        ]

        (
            open_positions,
            cash,
        ) = close_due_positions(
            open_positions,
            cash,
            entry_date,
        )

        trade = get_trade_result(
            row
        )

        if trade is None:
            missing_price += 1
            continue

        if cash < TRADE_SIZE:
            skipped_cash += 1
            continue

        open_positions.append(
            trade
        )

        cash -= TRADE_SIZE

        trades_taken += 1

        total_trade_profit += trade[
            "profit"
        ]

        if trade["profit"] > 0:
            winners += 1

        current_invested = (
            Decimal(
                len(open_positions)
            )
            * TRADE_SIZE
        )

        max_open = max(
            max_open,
            len(open_positions),
        )

        max_invested = max(
            max_invested,
            current_invested,
        )

    for position in open_positions:
        cash += position[
            "exit_value"
        ]

    profit = (
        cash
        - starting_cash
    )

    total_return = (
        profit
        / starting_cash
        * Decimal("100")
    )

    win_rate = (
        Decimal(winners)
        / Decimal(trades_taken)
        * Decimal("100")
        if trades_taken
        else None
    )

    average_trade_return = (
        total_trade_profit
        / Decimal(trades_taken)
        / TRADE_SIZE
        * Decimal("100")
        if trades_taken
        else None
    )

    return {
        "signals":
            len(rows),

        "trades":
            trades_taken,

        "cash_skips":
            skipped_cash,

        "missing":
            missing_price,

        "max_open":
            max_open,

        "max_invested":
            max_invested,

        "profit":
            profit,

        "final_value":
            cash,

        "return":
            total_return,

        "win_rate":
            win_rate,

        "avg_trade_return":
            average_trade_return,
    }


def print_period(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 160)

    print(
        f"{'Capital':<14}"
        f"{'Signals':>10}"
        f"{'Trades':>10}"
        f"{'Cash Skip':>12}"
        f"{'Missing':>10}"
        f"{'Max Open':>11}"
        f"{'Max Invested':>16}"
        f"{'Profit':>15}"
        f"{'Final Value':>16}"
        f"{'Return':>12}"
        f"{'Win Rate':>12}"
        f"{'Avg Trade':>13}"
    )

    print("-" * 160)

    for starting_cash in (
        STARTING_CAPITAL_LEVELS
    ):
        result = simulate_portfolio(
            rows,
            starting_cash,
        )

        print(
            f"{format_money(starting_cash):<14}"
            f"{result['signals']:>10}"
            f"{result['trades']:>10}"
            f"{result['cash_skips']:>12}"
            f"{result['missing']:>10}"
            f"{result['max_open']:>11}"
            f"{format_money(result['max_invested']):>16}"
            f"{format_money(result['profit']):>15}"
            f"{format_money(result['final_value']):>16}"
            f"{format_percent(result['return']):>12}"
            f"{format_percent(result['win_rate']):>12}"
            f"{format_percent(result['avg_trade_return']):>13}"
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
        "PORTFOLIO CAPACITY TEST"
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
        "TRAINING — PORTFOLIO CAPACITY",
        training_matches,
    )

    print_period(
        "OUT-OF-SAMPLE — PORTFOLIO CAPACITY",
        testing_matches,
    )


if __name__ == "__main__":
    main()