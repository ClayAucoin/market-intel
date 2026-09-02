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


def get_sector_counts(
    positions,
):
    counts = defaultdict(int)

    for position in positions:
        counts[
            position["sector"]
        ] += 1

    return counts


def simulate_portfolio(rows):
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
    missing_price = 0

    maximum_sector_positions = (
        defaultdict(int)
    )

    peak_sector_percent = (
        defaultdict(
            lambda: Decimal("0")
        )
    )

    peak_sector_date = {}
    peak_sector_positions = {}

    overall_peak_sector = None
    overall_peak_count = 0
    overall_peak_percent = Decimal("0")
    overall_peak_date = None

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

        sector_counts = (
            get_sector_counts(
                open_positions
            )
        )

        total_open = len(
            open_positions
        )

        for sector, count in (
            sector_counts.items()
        ):
            sector_percent = (
                Decimal(count)
                / Decimal(total_open)
                * Decimal("100")
            )

            if (
                count
                > maximum_sector_positions[
                    sector
                ]
            ):
                maximum_sector_positions[
                    sector
                ] = count

            if (
                sector_percent
                > peak_sector_percent[
                    sector
                ]
            ):
                peak_sector_percent[
                    sector
                ] = sector_percent

                peak_sector_date[
                    sector
                ] = entry_date

                peak_sector_positions[
                    sector
                ] = total_open

            if (
                count
                > overall_peak_count
            ):
                overall_peak_sector = (
                    sector
                )

                overall_peak_count = (
                    count
                )

                overall_peak_percent = (
                    sector_percent
                )

                overall_peak_date = (
                    entry_date
                )

            elif (
                count
                == overall_peak_count
                and sector_percent
                > overall_peak_percent
            ):
                overall_peak_sector = (
                    sector
                )

                overall_peak_percent = (
                    sector_percent
                )

                overall_peak_date = (
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

    return {
        "signals":
            len(rows),

        "trades":
            trades_taken,

        "cash_skips":
            skipped_cash,

        "missing":
            missing_price,

        "profit":
            profit,

        "return":
            total_return,

        "maximum_sector_positions":
            maximum_sector_positions,

        "peak_sector_percent":
            peak_sector_percent,

        "peak_sector_date":
            peak_sector_date,

        "peak_sector_positions":
            peak_sector_positions,

        "overall_peak_sector":
            overall_peak_sector,

        "overall_peak_count":
            overall_peak_count,

        "overall_peak_percent":
            overall_peak_percent,

        "overall_peak_date":
            overall_peak_date,
    }


def print_period(
    title,
    rows,
):
    result = simulate_portfolio(
        rows
    )

    print()
    print(title)
    print("=" * 120)

    print(
        "Signals:",
        result["signals"],
    )

    print(
        "Trades taken:",
        result["trades"],
    )

    print(
        "Cash skips:",
        result["cash_skips"],
    )

    print(
        "Missing:",
        result["missing"],
    )

    print(
        "Profit:",
        format_money(
            result["profit"]
        ),
    )

    print(
        "Return:",
        format_percent(
            result["return"]
        ),
    )

    print()
    print(
        "Largest simultaneous "
        "single-sector position count:"
    )

    print(
        f"{result['overall_peak_sector']}: "
        f"{result['overall_peak_count']} positions "
        f"({format_percent(result['overall_peak_percent'])}) "
        f"on {result['overall_peak_date']}"
    )

    print()
    print(
        f"{'Sector':<28}"
        f"{'Max Positions':>15}"
        f"{'Peak % Open':>16}"
        f"{'Peak Date':>15}"
        f"{'Open at Peak':>15}"
    )

    print("-" * 89)

    sectors = sorted(
        result[
            "maximum_sector_positions"
        ],
        key=lambda sector: (
            -result[
                "maximum_sector_positions"
            ][sector],
            sector,
        ),
    )

    for sector in sectors:
        print(
            f"{sector:<28}"
            f"{result['maximum_sector_positions'][sector]:>15}"
            f"{format_percent(result['peak_sector_percent'][sector]):>16}"
            f"{str(result['peak_sector_date'][sector]):>15}"
            f"{result['peak_sector_positions'][sector]:>15}"
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
        "SECTOR CONCENTRATION TEST"
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
        "TRAINING — SECTOR CONCENTRATION",
        training_matches,
    )

    print_period(
        "OUT-OF-SAMPLE — SECTOR CONCENTRATION",
        testing_matches,
    )


if __name__ == "__main__":
    main()