import sys
from collections import defaultdict
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

STARTING_CASH = Decimal("10000")
TRADE_SIZE = Decimal("1000")
HOLDING_DAYS = 45


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

    shares = (
        TRADE_SIZE
        / entry_price
    )

    exit_value = (
        shares
        * exit_record["price"]
    )

    return {
        "ticker":
            ticker,

        "sector":
            row.get("sector")
            or "UNKNOWN",

        "entry_date":
            entry_date,

        "entry_price":
            entry_price,

        "exit_date":
            exit_record["trade_date"],

        "exit_price":
            exit_record["price"],

        "return":
            stock_return,

        "shares":
            shares,

        "exit_value":
            exit_value,
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


def build_portfolio(rows):
    ordered = sorted(
        rows,
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        )
    )

    cash = STARTING_CASH
    open_positions = []

    accepted = []
    cash_skips = 0
    missing = 0

    daily_open_counts = {}
    overlap_entries = []

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
            missing += 1
            continue

        if cash < TRADE_SIZE:
            cash_skips += 1
            continue

        positions_before = len(
            open_positions
        )

        sectors_before = sorted(
            {
                position["sector"]
                for position
                in open_positions
            }
        )

        tickers_before = sorted(
            position["ticker"]
            for position
            in open_positions
        )

        open_positions.append(
            trade
        )

        cash -= TRADE_SIZE

        accepted.append(
            trade
        )

        positions_after = len(
            open_positions
        )

        daily_open_counts[
            entry_date
        ] = max(
            daily_open_counts.get(
                entry_date,
                0,
            ),
            positions_after,
        )

        overlap_entries.append(
            {
                "trade":
                    trade,

                "positions_before":
                    positions_before,

                "positions_after":
                    positions_after,

                "sectors_before":
                    sectors_before,

                "tickers_before":
                    tickers_before,
            }
        )

    return {
        "accepted":
            accepted,

        "cash_skips":
            cash_skips,

        "missing":
            missing,

        "daily_open_counts":
            daily_open_counts,

        "overlap_entries":
            overlap_entries,
    }


def summarize_by_overlap(
    overlap_entries,
):
    groups = defaultdict(
        list
    )

    for item in overlap_entries:
        count = item[
            "positions_before"
        ]

        trade = item[
            "trade"
        ]

        groups[count].append(
            trade
        )

    return groups


def summarize_bucket(
    trades,
):
    if not trades:
        return None

    returns = [
        trade["return"]
        for trade in trades
    ]

    wins = sum(
        1
        for value in returns
        if value > 0
    )

    losses = [
        value
        for value in returns
        if value < 0
    ]

    avg_return = (
        sum(
            returns,
            Decimal("0"),
        )
        / Decimal(
            len(returns)
        )
    )

    win_rate = (
        Decimal(wins)
        / Decimal(
            len(returns)
        )
        * Decimal("100")
    )

    worst_return = min(
        returns
    )

    avg_loss = None

    if losses:
        avg_loss = (
            sum(
                losses,
                Decimal("0"),
            )
            / Decimal(
                len(losses)
            )
        )

    return {
        "count":
            len(trades),

        "avg_return":
            avg_return,

        "win_rate":
            win_rate,

        "worst_return":
            worst_return,

        "avg_loss":
            avg_loss,
    }


def print_overlap_table(
    groups,
):
    print()
    print(
        "RETURN BY NUMBER OF POSITIONS "
        "ALREADY OPEN"
    )
    print("-" * 95)

    print(
        f"{'Already Open':>12}"
        f"{'Trades':>10}"
        f"{'Avg Return':>15}"
        f"{'Win Rate':>15}"
        f"{'Worst':>15}"
        f"{'Avg Loss':>15}"
    )

    print("-" * 95)

    for count in sorted(
        groups
    ):
        summary = summarize_bucket(
            groups[count]
        )

        print(
            f"{count:>12}"
            f"{summary['count']:>10}"
            f"{format_percent(summary['avg_return']):>15}"
            f"{format_percent(summary['win_rate']):>15}"
            f"{format_percent(summary['worst_return']):>15}"
            f"{format_percent(summary['avg_loss']):>15}"
        )


def print_high_overlap_trades(
    overlap_entries,
):
    if not overlap_entries:
        return

    max_before = max(
        item["positions_before"]
        for item in overlap_entries
    )

    threshold = max(
        5,
        max_before - 2,
    )

    high_overlap = [
        item
        for item in overlap_entries
        if (
            item["positions_before"]
            >= threshold
        )
    ]

    print()
    print(
        "HIGHEST-OVERLAP ENTRIES"
    )
    print("-" * 120)

    print(
        "Showing entries made with "
        f"{threshold}+ positions already open."
    )

    if not high_overlap:
        print(
            "No entries reached this level."
        )
        return

    print()

    for item in high_overlap:
        trade = item[
            "trade"
        ]

        print(
            f"{trade['entry_date']}  "
            f"{trade['ticker']:<6}  "
            f"{trade['sector']:<25}  "
            f"Before: "
            f"{item['positions_before']:>2}  "
            f"After: "
            f"{item['positions_after']:>2}  "
            f"Return: "
            f"{format_percent(trade['return']):>9}"
        )


def print_loss_clusters(
    trades,
):
    losing_trades = [
        trade
        for trade in trades
        if trade["return"] < 0
    ]

    by_exit_month = defaultdict(
        list
    )

    for trade in losing_trades:
        key = (
            trade["exit_date"].year,
            trade["exit_date"].month,
        )

        by_exit_month[key].append(
            trade
        )

    clusters = [
        (
            key,
            month_trades,
        )
        for key, month_trades
        in by_exit_month.items()
        if len(month_trades) >= 2
    ]

    clusters.sort(
        key=lambda item: (
            -len(item[1]),
            item[0],
        )
    )

    print()
    print(
        "LOSS CLUSTERS BY EXIT MONTH"
    )
    print("-" * 110)

    if not clusters:
        print(
            "No months contained two or "
            "more losing exits."
        )
        return

    for (
        year_month,
        month_trades,
    ) in clusters[:10]:
        year, month = year_month

        combined_return = sum(
            (
                trade["return"]
                for trade
                in month_trades
            ),
            Decimal("0"),
        )

        tickers = ", ".join(
            trade["ticker"]
            for trade
            in sorted(
                month_trades,
                key=lambda trade: (
                    trade["exit_date"],
                    trade["ticker"],
                ),
            )
        )

        print(
            f"{year}-{month:02d}  "
            f"Losses: "
            f"{len(month_trades):>2}  "
            f"Combined trade returns: "
            f"{format_percent(combined_return):>10}  "
            f"{tickers}"
        )


def print_period(
    title,
    rows,
):
    result = build_portfolio(
        rows
    )

    accepted = result[
        "accepted"
    ]

    overlap_entries = result[
        "overlap_entries"
    ]

    print()
    print(title)
    print("=" * 120)

    print(
        "Signals:",
        len(rows),
    )

    print(
        "Trades taken:",
        len(accepted),
    )

    print(
        "Cash skips:",
        result["cash_skips"],
    )

    print(
        "Missing:",
        result["missing"],
    )

    if overlap_entries:
        max_open = max(
            item["positions_after"]
            for item
            in overlap_entries
        )
    else:
        max_open = 0

    print(
        "Maximum simultaneous positions:",
        max_open,
    )

    groups = summarize_by_overlap(
        overlap_entries
    )

    print_overlap_table(
        groups
    )

    print_high_overlap_trades(
        overlap_entries
    )

    print_loss_clusters(
        accepted
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
        "OVERLAP RISK TEST"
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
        "Training through:",
        TRAIN_END,
    )

    print(
        "Out-of-sample from:",
        TEST_START,
    )

    print_period(
        "TRAINING — OVERLAP RISK",
        training_matches,
    )

    print_period(
        "OUT-OF-SAMPLE — OVERLAP RISK",
        testing_matches,
    )


if __name__ == "__main__":
    main()