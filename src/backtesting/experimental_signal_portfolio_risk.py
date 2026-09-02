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
HOLDING_DAYS = 45

TRADE_SIZES = [
    Decimal("500"),
    Decimal("750"),
    Decimal("1000"),
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


def calculate_average(values):
    if not values:
        return None

    return (
        sum(values, Decimal("0"))
        / Decimal(len(values))
    )


def calculate_median(values):
    if not values:
        return None

    return Decimal(
        str(
            median(values)
        )
    )


def calculate_win_rate(values):
    if not values:
        return None

    winners = sum(
        1
        for value in values
        if value > 0
    )

    return (
        Decimal(winners)
        / Decimal(len(values))
        * Decimal("100")
    )


def get_trade_result(
    row,
    trade_size,
):
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

    exit_price = exit_record[
        "price"
    ]

    stock_return = calculate_return(
        entry_price,
        exit_price,
    )

    if stock_return is None:
        return None

    profit = (
        trade_size
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

        "investment":
            trade_size,

        "profit":
            profit,

        "exit_value":
            trade_size + profit,
    }


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


def get_ticker_exposure(
    positions,
    ticker,
):
    return sum(
        (
            position["investment"]
            for position in positions
            if position["ticker"] == ticker
        ),
        Decimal("0"),
    )


def get_total_invested(
    positions,
):
    return sum(
        (
            position["investment"]
            for position in positions
        ),
        Decimal("0"),
    )


def simulate_portfolio(
    rows,
    trade_size,
    ticker_cap_percent=None,
):
    ordered = sorted(
        rows,
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        )
    )

    cash = STARTING_CASH
    open_positions = []
    completed = []

    skipped_cash_trades = []
    skipped_cap_trades = []

    missing_price = 0

    max_open_positions = 0
    max_invested = Decimal("0")
    max_ticker_exposure = Decimal("0")

    for row in ordered:
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

        trade = get_trade_result(
            row,
            trade_size,
        )

        if trade is None:
            missing_price += 1
            continue

        if cash < trade_size:
            skipped_cash_trades.append(
                trade
            )

            continue

        ticker = row[
            "ticker"
        ]

        current_ticker_exposure = (
            get_ticker_exposure(
                open_positions,
                ticker,
            )
        )

        proposed_ticker_exposure = (
            current_ticker_exposure
            + trade_size
        )

        if ticker_cap_percent is not None:
            portfolio_value_for_cap = (
                cash
                + get_total_invested(
                    open_positions
                )
            )

            maximum_ticker_exposure = (
                portfolio_value_for_cap
                * ticker_cap_percent
                / Decimal("100")
            )

            if (
                proposed_ticker_exposure
                > maximum_ticker_exposure
            ):
                skipped_cap_trades.append(
                    trade
                )

                continue

        open_positions.append(
            trade
        )

        cash -= trade_size

        current_invested = (
            get_total_invested(
                open_positions
            )
        )

        current_ticker_exposure = (
            get_ticker_exposure(
                open_positions,
                ticker,
            )
        )

        max_open_positions = max(
            max_open_positions,
            len(open_positions),
        )

        max_invested = max(
            max_invested,
            current_invested,
        )

        max_ticker_exposure = max(
            max_ticker_exposure,
            current_ticker_exposure,
        )

    for position in open_positions:
        cash += position[
            "exit_value"
        ]

        completed.append(
            position
        )

    profit = (
        cash
        - STARTING_CASH
    )

    total_return = (
        profit
        / STARTING_CASH
        * Decimal("100")
    )

    completed_returns = [
        trade["return"]
        for trade in completed
    ]

    return {
        "signals":
            len(rows),

        "trades":
            len(completed),

        "skipped_cash":
            len(
                skipped_cash_trades
            ),

        "skipped_cap":
            len(
                skipped_cap_trades
            ),

        "skipped_cash_trades":
            skipped_cash_trades,

        "skipped_cap_trades":
            skipped_cap_trades,

        "missing_price":
            missing_price,

        "max_open":
            max_open_positions,

        "max_invested":
            max_invested,

        "max_ticker_exposure":
            max_ticker_exposure,

        "final_value":
            cash,

        "profit":
            profit,

        "return":
            total_return,

        "win_rate":
            calculate_win_rate(
                completed_returns
            ),
    }


def print_trade_size_test(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 145)

    print(
        f"{'Trade Size':<14}"
        f"{'Signals':>10}"
        f"{'Trades':>10}"
        f"{'Cash Skip':>12}"
        f"{'Max Open':>11}"
        f"{'Max Invested':>16}"
        f"{'Profit':>15}"
        f"{'Final Value':>16}"
        f"{'Return':>12}"
        f"{'Win Rate':>12}"
    )

    print("-" * 145)

    for trade_size in TRADE_SIZES:
        result = simulate_portfolio(
            rows,
            trade_size,
        )

        print(
            f"{format_money(trade_size):<14}"
            f"{result['signals']:>10}"
            f"{result['trades']:>10}"
            f"{result['skipped_cash']:>12}"
            f"{result['max_open']:>11}"
            f"{format_money(result['max_invested']):>16}"
            f"{format_money(result['profit']):>15}"
            f"{format_money(result['final_value']):>16}"
            f"{format_percent(result['return']):>12}"
            f"{format_percent(result['win_rate']):>12}"
        )


def print_ticker_cap_test(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 150)

    print(
        f"{'Ticker Cap':<16}"
        f"{'Signals':>10}"
        f"{'Trades':>10}"
        f"{'Cash Skip':>12}"
        f"{'Cap Skip':>11}"
        f"{'Max Open':>11}"
        f"{'Max Ticker':>14}"
        f"{'Profit':>15}"
        f"{'Return':>12}"
        f"{'Win Rate':>12}"
    )

    print("-" * 150)

    tests = [
        (
            "Unlimited",
            None,
        ),
        (
            "10%",
            Decimal("10"),
        ),
        (
            "20%",
            Decimal("20"),
        ),
        (
            "30%",
            Decimal("30"),
        ),
    ]

    for name, ticker_cap in tests:
        result = simulate_portfolio(
            rows,
            Decimal("1000"),
            ticker_cap,
        )

        print(
            f"{name:<16}"
            f"{result['signals']:>10}"
            f"{result['trades']:>10}"
            f"{result['skipped_cash']:>12}"
            f"{result['skipped_cap']:>11}"
            f"{result['max_open']:>11}"
            f"{format_money(result['max_ticker_exposure']):>14}"
            f"{format_money(result['profit']):>15}"
            f"{format_percent(result['return']):>12}"
            f"{format_percent(result['win_rate']):>12}"
        )


def print_cash_skip_analysis(
    title,
    rows,
):
    result = simulate_portfolio(
        rows,
        Decimal("1000"),
        Decimal("20"),
    )

    taken_returns = []

    ordered = sorted(
        rows,
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        )
    )

    skipped_keys = {
        (
            trade["ticker"],
            trade["entry_date"],
        )
        for trade in result[
            "skipped_cash_trades"
        ]
    }

    for row in ordered:
        key = (
            row["ticker"],
            row["entry_date"],
        )

        if key in skipped_keys:
            continue

        trade = get_trade_result(
            row,
            Decimal("1000"),
        )

        if trade is not None:
            taken_returns.append(
                trade["return"]
            )

    skipped_returns = [
        trade["return"]
        for trade in result[
            "skipped_cash_trades"
        ]
    ]

    print()
    print(title)
    print("=" * 105)

    print(
        f"{'Group':<22}"
        f"{'N':>10}"
        f"{'Average':>16}"
        f"{'Median':>16}"
        f"{'Win Rate':>16}"
        f"{'Worst':>16}"
        f"{'Best':>16}"
    )

    print("-" * 105)

    groups = [
        (
            "Taken / available",
            taken_returns,
        ),
        (
            "Skipped for cash",
            skipped_returns,
        ),
    ]

    for name, values in groups:
        average = (
            calculate_average(
                values
            )
        )

        middle = (
            calculate_median(
                values
            )
        )

        win_rate = (
            calculate_win_rate(
                values
            )
        )

        worst = (
            min(values)
            if values
            else None
        )

        best = (
            max(values)
            if values
            else None
        )

        print(
            f"{name:<22}"
            f"{len(values):>10}"
            f"{format_percent(average):>16}"
            f"{format_percent(middle):>16}"
            f"{format_percent(win_rate):>16}"
            f"{format_percent(worst):>16}"
            f"{format_percent(best):>16}"
        )

    print()
    print(
        "Skipped-cash signals:"
    )

    if not result[
        "skipped_cash_trades"
    ]:
        print(
            "None."
        )

        return

    for trade in result[
        "skipped_cash_trades"
    ]:
        print(
            f"{trade['entry_date']}  "
            f"{trade['ticker']:<7}  "
            f"{format_percent(trade['return']):>10}"
        )


def main():
    universe_name = (
        get_universe_name()
    )

    rows = get_events(
        universe_name
    )

    training, testing = split_by_time(
        rows
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
        "EXPERIMENTAL SIGNAL PORTFOLIO RISK TEST"
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
        len(training_matches),
    )

    print(
        "Out-of-sample signal matches:",
        len(testing_matches),
    )

    print_trade_size_test(
        "TRAINING — TRADE SIZE / CAPITAL UTILIZATION",
        training_matches,
    )

    print_trade_size_test(
        "OUT-OF-SAMPLE — TRADE SIZE / CAPITAL UTILIZATION",
        testing_matches,
    )

    print_ticker_cap_test(
        "TRAINING — $1,000 TRADE / TICKER CAP",
        training_matches,
    )

    print_ticker_cap_test(
        "OUT-OF-SAMPLE — $1,000 TRADE / TICKER CAP",
        testing_matches,
    )

    print_cash_skip_analysis(
        "TRAINING — $1,000 CASH BOTTLENECK ANALYSIS",
        training_matches,
    )

    print_cash_skip_analysis(
        "OUT-OF-SAMPLE — $1,000 CASH BOTTLENECK ANALYSIS",
        testing_matches,
    )


if __name__ == "__main__":
    main()