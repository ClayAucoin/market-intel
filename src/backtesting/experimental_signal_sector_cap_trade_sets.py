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

STARTING_CASH = Decimal("10000")
TRADE_SIZE = Decimal("1000")
HOLDING_DAYS = 45
SECTOR_CAP_PERCENT = Decimal("30")


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

    return {
        "ticker":
            ticker,

        "sector":
            row.get("sector")
            or "UNKNOWN",

        "entry_date":
            entry_date,

        "exit_date":
            exit_record["trade_date"],

        "return":
            stock_return,

        "exit_value":
            (
                TRADE_SIZE
                * (
                    Decimal("1")
                    + stock_return
                    / Decimal("100")
                )
            ),
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


def get_total_invested(
    positions,
):
    return (
        Decimal(
            len(positions)
        )
        * TRADE_SIZE
    )


def get_sector_exposure(
    positions,
    sector,
):
    return sum(
        (
            TRADE_SIZE
            for position in positions
            if position["sector"] == sector
        ),
        Decimal("0"),
    )


def trade_key(trade):
    return (
        trade["entry_date"],
        trade["ticker"],
    )


def simulate_portfolio(
    rows,
    sector_cap_percent,
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

    taken = []
    cash_skips = []
    sector_skips = []
    missing = []

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
            missing.append(
                {
                    "ticker":
                        row["ticker"],

                    "entry_date":
                        entry_date,

                    "sector":
                        row.get("sector")
                        or "UNKNOWN",
                }
            )

            continue

        if cash < TRADE_SIZE:
            cash_skips.append(
                trade
            )
            continue

        if sector_cap_percent is not None:
            sector = trade[
                "sector"
            ]

            current_sector_exposure = (
                get_sector_exposure(
                    open_positions,
                    sector,
                )
            )

            proposed_sector_exposure = (
                current_sector_exposure
                + TRADE_SIZE
            )

            portfolio_value_for_cap = (
                cash
                + get_total_invested(
                    open_positions
                )
            )

            maximum_sector_exposure = (
                portfolio_value_for_cap
                * sector_cap_percent
                / Decimal("100")
            )

            if (
                proposed_sector_exposure
                > maximum_sector_exposure
            ):
                sector_skips.append(
                    trade
                )
                continue

        open_positions.append(
            trade
        )

        cash -= TRADE_SIZE

        taken.append(
            trade
        )

    for position in open_positions:
        cash += position[
            "exit_value"
        ]

    profit = (
        cash
        - STARTING_CASH
    )

    return {
        "taken":
            taken,

        "cash_skips":
            cash_skips,

        "sector_skips":
            sector_skips,

        "missing":
            missing,

        "profit":
            profit,

        "return":
            (
                profit
                / STARTING_CASH
                * Decimal("100")
            ),
    }


def summarize_trades(
    trades,
):
    if not trades:
        return {
            "count": 0,
            "profit": Decimal("0"),
            "avg_return": None,
            "win_rate": None,
        }

    profit = sum(
        (
            trade["exit_value"]
            - TRADE_SIZE
            for trade in trades
        ),
        Decimal("0"),
    )

    avg_return = (
        sum(
            (
                trade["return"]
                for trade in trades
            ),
            Decimal("0"),
        )
        / Decimal(
            len(trades)
        )
    )

    wins = sum(
        1
        for trade in trades
        if trade["return"] > 0
    )

    win_rate = (
        Decimal(wins)
        / Decimal(
            len(trades)
        )
        * Decimal("100")
    )

    return {
        "count":
            len(trades),

        "profit":
            profit,

        "avg_return":
            avg_return,

        "win_rate":
            win_rate,
    }


def print_trade_group(
    title,
    trades,
):
    summary = summarize_trades(
        trades
    )

    print()
    print(title)
    print("-" * 110)

    print(
        "Trades:",
        summary["count"],
    )

    print(
        "Combined profit:",
        format_money(
            summary["profit"]
        ),
    )

    print(
        "Average return:",
        format_percent(
            summary["avg_return"]
        ),
    )

    print(
        "Win rate:",
        format_percent(
            summary["win_rate"]
        ),
    )

    if not trades:
        print(
            "No trades in this group."
        )
        return

    print()

    for trade in sorted(
        trades,
        key=trade_key,
    ):
        print(
            f"{trade['entry_date']}  "
            f"{trade['ticker']:<6}  "
            f"{trade['sector']:<25}  "
            f"{format_percent(trade['return']):>10}"
        )


def compare_trade_sets(
    title,
    rows,
):
    unlimited = simulate_portfolio(
        rows,
        None,
    )

    capped = simulate_portfolio(
        rows,
        SECTOR_CAP_PERCENT,
    )

    unlimited_map = {
        trade_key(trade): trade
        for trade in unlimited[
            "taken"
        ]
    }

    capped_map = {
        trade_key(trade): trade
        for trade in capped[
            "taken"
        ]
    }

    unlimited_keys = set(
        unlimited_map
    )

    capped_keys = set(
        capped_map
    )

    shared_keys = (
        unlimited_keys
        & capped_keys
    )

    unlimited_only_keys = (
        unlimited_keys
        - capped_keys
    )

    capped_only_keys = (
        capped_keys
        - unlimited_keys
    )

    shared = [
        unlimited_map[key]
        for key in shared_keys
    ]

    unlimited_only = [
        unlimited_map[key]
        for key in unlimited_only_keys
    ]

    capped_only = [
        capped_map[key]
        for key in capped_only_keys
    ]

    print()
    print(title)
    print("=" * 110)

    print(
        "Unlimited:",
        f"{len(unlimited['taken'])} trades,",
        f"{len(unlimited['cash_skips'])} cash skips,",
        f"{len(unlimited['sector_skips'])} sector skips,",
        f"{len(unlimited['missing'])} missing,",
        f"{format_money(unlimited['profit'])} profit,",
        format_percent(
            unlimited["return"]
        ),
    )

    print(
        "30% cap:",
        f"{len(capped['taken'])} trades,",
        f"{len(capped['cash_skips'])} cash skips,",
        f"{len(capped['sector_skips'])} sector skips,",
        f"{len(capped['missing'])} missing,",
        f"{format_money(capped['profit'])} profit,",
        format_percent(
            capped["return"]
        ),
    )

    print(
        "Profit difference:",
        format_money(
            capped["profit"]
            - unlimited["profit"]
        ),
    )

    print_trade_group(
        "TRADES TAKEN BY BOTH PORTFOLIOS",
        shared,
    )

    print_trade_group(
        "UNLIMITED ONLY",
        unlimited_only,
    )

    print_trade_group(
        "30% CAP ONLY",
        capped_only,
    )

    unlimited_only_summary = (
        summarize_trades(
            unlimited_only
        )
    )

    capped_only_summary = (
        summarize_trades(
            capped_only
        )
    )

    difference = (
        capped_only_summary[
            "profit"
        ]
        - unlimited_only_summary[
            "profit"
        ]
    )

    print()
    print(
        "DIFFERING TRADE-SET PROFIT COMPARISON"
    )
    print("-" * 110)

    print(
        "Unlimited-only profit:",
        format_money(
            unlimited_only_summary[
                "profit"
            ]
        ),
    )

    print(
        "30%-cap-only profit:",
        format_money(
            capped_only_summary[
                "profit"
            ]
        ),
    )

    print(
        "Difference from differing trades:",
        format_money(
            difference
        ),
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
        "SECTOR CAP TRADE-SET COMPARISON"
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
        "Sector cap:",
        format_percent(
            SECTOR_CAP_PERCENT
        ),
    )

    print(
        "Training through:",
        TRAIN_END,
    )

    print(
        "Out-of-sample from:",
        TEST_START,
    )

    compare_trade_sets(
        "TRAINING — UNLIMITED VS. 30% SECTOR CAP",
        training_matches,
    )

    compare_trade_sets(
        "OUT-OF-SAMPLE — UNLIMITED VS. 30% SECTOR CAP",
        testing_matches,
    )


if __name__ == "__main__":
    main()