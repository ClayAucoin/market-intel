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

SECTOR_CAPS = [
    None,
    Decimal("30"),
    Decimal("40"),
    Decimal("50"),
    Decimal("60"),
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


def format_cap(value):
    if value is None:
        return "Unlimited"

    return f"{value:.0f}%"


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

        "sector":
            row.get("sector")
            or "UNKNOWN",

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


def get_total_invested(
    positions,
):
    return (
        Decimal(
            len(positions)
        )
        * TRADE_SIZE
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

    trades_taken = 0
    skipped_cash = 0
    skipped_sector = 0
    missing_price = 0

    max_open = 0
    max_invested = Decimal("0")

    max_sector_positions = 0
    max_sector_percent = Decimal("0")
    max_sector_name = None
    max_sector_date = None

    winners = 0
    total_trade_profit = Decimal("0")

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
                skipped_sector += 1
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

        max_open = max(
            max_open,
            len(open_positions),
        )

        current_invested = (
            get_total_invested(
                open_positions
            )
        )

        max_invested = max(
            max_invested,
            current_invested,
        )

        sector_counts = defaultdict(int)

        for position in open_positions:
            sector_counts[
                position["sector"]
            ] += 1

        for sector, count in (
            sector_counts.items()
        ):
            sector_exposure = (
                Decimal(count)
                * TRADE_SIZE
            )

            portfolio_value = (
                cash
                + current_invested
            )

            sector_percent = (
                sector_exposure
                / portfolio_value
                * Decimal("100")
                if portfolio_value > 0
                else Decimal("0")
            )

            if (
                count > max_sector_positions
                or (
                    count
                    == max_sector_positions
                    and sector_percent
                    > max_sector_percent
                )
            ):
                max_sector_positions = count
                max_sector_percent = (
                    sector_percent
                )
                max_sector_name = sector
                max_sector_date = (
                    entry_date
                )

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

        "sector_skips":
            skipped_sector,

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

        "max_sector_positions":
            max_sector_positions,

        "max_sector_percent":
            max_sector_percent,

        "max_sector_name":
            max_sector_name,

        "max_sector_date":
            max_sector_date,
    }


def print_period(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 175)

    print(
        f"{'Sector Cap':<14}"
        f"{'Trades':>9}"
        f"{'Cash Skip':>11}"
        f"{'Sector Skip':>13}"
        f"{'Missing':>9}"
        f"{'Max Open':>10}"
        f"{'Max Invested':>15}"
        f"{'Profit':>14}"
        f"{'Return':>11}"
        f"{'Win Rate':>11}"
        f"{'Avg Trade':>12}"
        f"{'Peak Sector':>22}"
        f"{'Peak Count':>12}"
        f"{'Peak %':>10}"
    )

    print("-" * 175)

    for sector_cap in SECTOR_CAPS:
        result = simulate_portfolio(
            rows,
            sector_cap,
        )

        peak_sector = (
            result["max_sector_name"]
            or "N/A"
        )

        print(
            f"{format_cap(sector_cap):<14}"
            f"{result['trades']:>9}"
            f"{result['cash_skips']:>11}"
            f"{result['sector_skips']:>13}"
            f"{result['missing']:>9}"
            f"{result['max_open']:>10}"
            f"{format_money(result['max_invested']):>15}"
            f"{format_money(result['profit']):>14}"
            f"{format_percent(result['return']):>11}"
            f"{format_percent(result['win_rate']):>11}"
            f"{format_percent(result['avg_trade_return']):>12}"
            f"{peak_sector:>22}"
            f"{result['max_sector_positions']:>12}"
            f"{format_percent(result['max_sector_percent']):>10}"
        )

        if result[
            "max_sector_date"
        ] is not None:
            print(
                f"{'':<14}"
                f"Peak sector date: "
                f"{result['max_sector_date']}"
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
        "SECTOR CAP TEST"
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
        "TRAINING — SECTOR CAP COMPARISON",
        training_matches,
    )

    print_period(
        "OUT-OF-SAMPLE — SECTOR CAP COMPARISON",
        testing_matches,
    )


if __name__ == "__main__":
    main()