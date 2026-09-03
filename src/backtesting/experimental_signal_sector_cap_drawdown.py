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

        "entry_price":
            entry_price,

        "exit_date":
            exit_record["trade_date"],

        "exit_price":
            exit_record["price"],

        "return":
            stock_return,

        "shares":
            TRADE_SIZE
            / entry_price,

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


def get_position_value_on_date(
    position,
    current_date,
):
    price_record = get_price_on_or_after(
        position["ticker"],
        current_date,
    )

    if price_record is None:
        return None

    if (
        price_record["trade_date"]
        > position["exit_date"]
    ):
        return position[
            "exit_value"
        ]

    return (
        position["shares"]
        * price_record["price"]
    )


def calculate_portfolio_value(
    cash,
    positions,
    current_date,
):
    value = cash

    for position in positions:
        position_value = (
            get_position_value_on_date(
                position,
                current_date,
            )
        )

        if position_value is None:
            position_value = (
                TRADE_SIZE
            )

        value += position_value

    return value


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
    sector_cap_percent,
):
    ordered = sorted(
        rows,
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        )
    )

    if not ordered:
        return None

    trades = []

    for row in ordered:
        trade = get_trade_result(
            row
        )

        if trade is not None:
            trades.append(
                trade
            )

    if not trades:
        return None

    start_date = min(
        trade["entry_date"]
        for trade in trades
    )

    end_date = max(
        trade["exit_date"]
        for trade in trades
    )

    cash = STARTING_CASH
    open_positions = []

    cash_skips = 0
    sector_skips = 0
    missing = (
        len(rows)
        - len(trades)
    )

    trade_map = {}

    for trade in trades:
        trade_map.setdefault(
            trade["entry_date"],
            []
        ).append(
            trade
        )

    peak_value = STARTING_CASH
    max_drawdown = Decimal("0")
    max_drawdown_dollars = Decimal("0")

    drawdown_peak_date = None
    drawdown_trough_date = None
    current_peak_date = start_date

    current_date = start_date

    accepted = 0

    while current_date <= end_date:
        (
            open_positions,
            cash,
        ) = close_due_positions(
            open_positions,
            cash,
            current_date,
        )

        todays_trades = sorted(
            trade_map.get(
                current_date,
                [],
            ),
            key=lambda trade: (
                trade["ticker"]
            ),
        )

        for trade in todays_trades:
            if cash < TRADE_SIZE:
                cash_skips += 1
                continue

            if sector_cap_percent is not None:
                current_sector_exposure = (
                    get_sector_exposure(
                        open_positions,
                        trade["sector"],
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
                    sector_skips += 1
                    continue

            open_positions.append(
                trade
            )

            cash -= TRADE_SIZE
            accepted += 1

        portfolio_value = (
            calculate_portfolio_value(
                cash,
                open_positions,
                current_date,
            )
        )

        if portfolio_value > peak_value:
            peak_value = portfolio_value
            current_peak_date = (
                current_date
            )

        drawdown_dollars = (
            portfolio_value
            - peak_value
        )

        if peak_value > 0:
            drawdown_percent = (
                drawdown_dollars
                / peak_value
                * Decimal("100")
            )
        else:
            drawdown_percent = (
                Decimal("0")
            )

        if (
            drawdown_percent
            < max_drawdown
        ):
            max_drawdown = (
                drawdown_percent
            )

            max_drawdown_dollars = (
                drawdown_dollars
            )

            drawdown_peak_date = (
                current_peak_date
            )

            drawdown_trough_date = (
                current_date
            )

        current_date += timedelta(
            days=1
        )

    (
        open_positions,
        cash,
    ) = close_due_positions(
        open_positions,
        cash,
        end_date
        + timedelta(days=1),
    )

    final_value = cash

    profit = (
        final_value
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
            accepted,

        "cash_skips":
            cash_skips,

        "sector_skips":
            sector_skips,

        "missing":
            missing,

        "final_value":
            final_value,

        "profit":
            profit,

        "return":
            total_return,

        "max_drawdown":
            max_drawdown,

        "max_drawdown_dollars":
            max_drawdown_dollars,

        "drawdown_peak_date":
            drawdown_peak_date,

        "drawdown_trough_date":
            drawdown_trough_date,
    }


def print_result(
    label,
    result,
):
    print(
        f"{label:<12}"
        f"{result['trades']:>8}"
        f"{result['cash_skips']:>12}"
        f"{result['sector_skips']:>14}"
        f"{result['missing']:>10}"
        f"{format_money(result['profit']):>15}"
        f"{format_percent(result['return']):>12}"
        f"{format_percent(result['max_drawdown']):>14}"
        f"{format_money(result['max_drawdown_dollars']):>16}"
    )

    print(
        f"{'':12}"
        f"Drawdown: "
        f"{result['drawdown_peak_date']} "
        f"to "
        f"{result['drawdown_trough_date']}"
    )


def print_period(
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

    print()
    print(title)
    print("=" * 120)

    print(
        f"{'Sector Cap':<12}"
        f"{'Trades':>8}"
        f"{'Cash Skip':>12}"
        f"{'Sector Skip':>14}"
        f"{'Missing':>10}"
        f"{'Profit':>15}"
        f"{'Return':>12}"
        f"{'Max DD':>14}"
        f"{'Max DD $':>16}"
    )

    print("-" * 120)

    print_result(
        "Unlimited",
        unlimited,
    )

    print_result(
        "30%",
        capped,
    )

    print()
    print(
        "Return difference:",
        format_percent(
            capped["return"]
            - unlimited["return"]
        ),
    )

    print(
        "Drawdown improvement:",
        format_percent(
            capped["max_drawdown"]
            - unlimited["max_drawdown"]
        ),
    )

    print(
        "Dollar drawdown improvement:",
        format_money(
            capped["max_drawdown_dollars"]
            - unlimited[
                "max_drawdown_dollars"
            ]
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
        "SECTOR CAP DRAWDOWN TEST"
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
        "TRAINING — DRAWDOWN COMPARISON",
        training_matches,
    )

    print_period(
        "OUT-OF-SAMPLE — DRAWDOWN COMPARISON",
        testing_matches,
    )


if __name__ == "__main__":
    main()