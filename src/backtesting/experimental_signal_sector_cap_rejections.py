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


def get_sector_positions(
    positions,
    sector,
):
    return [
        position
        for position in positions
        if position["sector"] == sector
    ]


def find_rejections(rows):
    ordered = sorted(
        rows,
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        )
    )

    cash = STARTING_CASH
    open_positions = []

    rejections = []

    cash_skips = 0
    missing = 0
    accepted = 0

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
            * SECTOR_CAP_PERCENT
            / Decimal("100")
        )

        if (
            proposed_sector_exposure
            > maximum_sector_exposure
        ):
            same_sector_positions = (
                get_sector_positions(
                    open_positions,
                    sector,
                )
            )

            current_sector_percent = (
                current_sector_exposure
                / portfolio_value_for_cap
                * Decimal("100")
            )

            proposed_sector_percent = (
                proposed_sector_exposure
                / portfolio_value_for_cap
                * Decimal("100")
            )

            rejections.append(
                {
                    "trade":
                        trade,

                    "portfolio_value":
                        portfolio_value_for_cap,

                    "cash":
                        cash,

                    "open_positions":
                        len(
                            open_positions
                        ),

                    "sector_positions":
                        len(
                            same_sector_positions
                        ),

                    "current_sector_percent":
                        current_sector_percent,

                    "proposed_sector_percent":
                        proposed_sector_percent,

                    "same_sector_tickers":
                        [
                            position["ticker"]
                            for position
                            in same_sector_positions
                        ],
                }
            )

            continue

        open_positions.append(
            trade
        )

        cash -= TRADE_SIZE
        accepted += 1

    return {
        "accepted":
            accepted,

        "cash_skips":
            cash_skips,

        "missing":
            missing,

        "rejections":
            rejections,
    }


def print_period(
    title,
    rows,
):
    result = find_rejections(
        rows
    )

    rejections = result[
        "rejections"
    ]

    print()
    print(title)
    print("=" * 110)

    print(
        "Signals:",
        len(rows),
    )

    print(
        "Accepted:",
        result["accepted"],
    )

    print(
        "Cash skips:",
        result["cash_skips"],
    )

    print(
        "Sector-cap rejections:",
        len(rejections),
    )

    print(
        "Missing:",
        result["missing"],
    )

    if not rejections:
        print()
        print(
            "No sector-cap rejections."
        )

        return

    print()

    for number, rejection in enumerate(
        rejections,
        start=1,
    ):
        trade = rejection[
            "trade"
        ]

        print(
            f"REJECTION {number}"
        )

        print("-" * 110)

        print(
            "Date:",
            trade["entry_date"],
        )

        print(
            "Ticker:",
            trade["ticker"],
        )

        print(
            "Sector:",
            trade["sector"],
        )

        print(
            "45-day return:",
            format_percent(
                trade["return"]
            ),
        )

        print(
            "Portfolio value:",
            format_money(
                rejection[
                    "portfolio_value"
                ]
            ),
        )

        print(
            "Available cash:",
            format_money(
                rejection["cash"]
            ),
        )

        print(
            "Open positions:",
            rejection[
                "open_positions"
            ],
        )

        print(
            "Existing positions in sector:",
            rejection[
                "sector_positions"
            ],
        )

        print(
            "Existing sector tickers:",
            (
                ", ".join(
                    rejection[
                        "same_sector_tickers"
                    ]
                )
                or "None"
            ),
        )

        print(
            "Current sector exposure:",
            format_percent(
                rejection[
                    "current_sector_percent"
                ]
            ),
        )

        print(
            "Proposed sector exposure:",
            format_percent(
                rejection[
                    "proposed_sector_percent"
                ]
            ),
        )

        print(
            "Sector cap:",
            format_percent(
                SECTOR_CAP_PERCENT
            ),
        )

        print()


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
        "SECTOR CAP REJECTION ANALYSIS"
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

    print_period(
        "TRAINING — 30% SECTOR CAP REJECTIONS",
        training_matches,
    )

    print_period(
        "OUT-OF-SAMPLE — 30% SECTOR CAP REJECTIONS",
        testing_matches,
    )


if __name__ == "__main__":
    main()