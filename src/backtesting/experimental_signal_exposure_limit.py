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

EXPOSURE_LIMITS = [
    Decimal("100"),
    Decimal("90"),
    Decimal("80"),
    Decimal("70"),
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


def get_cost_basis(
    positions,
):
    return (
        Decimal(
            len(positions)
        )
        * TRADE_SIZE
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


def simulate_portfolio(
    rows,
    exposure_limit_percent,
):
    ordered = sorted(
        rows,
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        )
    )

    trade_rows = []

    missing = 0

    for row in ordered:
        trade = get_trade_result(
            row
        )

        if trade is None:
            missing += 1
        else:
            trade_rows.append(
                trade
            )

    if not trade_rows:
        return None

    trade_map = {}

    for trade in trade_rows:
        trade_map.setdefault(
            trade["entry_date"],
            []
        ).append(
            trade
        )

    start_date = min(
        trade["entry_date"]
        for trade in trade_rows
    )

    end_date = max(
        trade["exit_date"]
        for trade in trade_rows
    )

    cash = STARTING_CASH
    open_positions = []

    accepted = []
    cash_skips = 0
    exposure_skips = 0

    max_open = 0
    max_cost_basis = Decimal("0")

    peak_value = STARTING_CASH
    current_peak_date = start_date

    max_drawdown = Decimal("0")
    max_drawdown_dollars = Decimal("0")

    drawdown_peak_date = None
    drawdown_trough_date = None

    current_date = start_date

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

            current_cost_basis = (
                get_cost_basis(
                    open_positions
                )
            )

            account_value_for_limit = (
                cash
                + current_cost_basis
            )

            maximum_exposure = (
                account_value_for_limit
                * exposure_limit_percent
                / Decimal("100")
            )

            proposed_exposure = (
                current_cost_basis
                + TRADE_SIZE
            )

            if (
                proposed_exposure
                > maximum_exposure
            ):
                exposure_skips += 1
                continue

            open_positions.append(
                trade
            )

            cash -= TRADE_SIZE

            accepted.append(
                trade
            )

            current_cost_basis = (
                get_cost_basis(
                    open_positions
                )
            )

            max_open = max(
                max_open,
                len(open_positions),
            )

            max_cost_basis = max(
                max_cost_basis,
                current_cost_basis,
            )

        portfolio_value = (
            calculate_portfolio_value(
                cash,
                open_positions,
                current_date,
            )
        )

        if portfolio_value > peak_value:
            peak_value = (
                portfolio_value
            )

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

    wins = sum(
        1
        for trade in accepted
        if trade["return"] > 0
    )

    if accepted:
        win_rate = (
            Decimal(wins)
            / Decimal(
                len(accepted)
            )
            * Decimal("100")
        )

        avg_trade = (
            sum(
                (
                    trade["return"]
                    for trade in accepted
                ),
                Decimal("0"),
            )
            / Decimal(
                len(accepted)
            )
        )
    else:
        win_rate = None
        avg_trade = None

    return {
        "trades":
            len(accepted),

        "cash_skips":
            cash_skips,

        "exposure_skips":
            exposure_skips,

        "missing":
            missing,

        "max_open":
            max_open,

        "max_cost_basis":
            max_cost_basis,

        "profit":
            profit,

        "return":
            total_return,

        "win_rate":
            win_rate,

        "avg_trade":
            avg_trade,

        "max_drawdown":
            max_drawdown,

        "max_drawdown_dollars":
            max_drawdown_dollars,

        "drawdown_peak_date":
            drawdown_peak_date,

        "drawdown_trough_date":
            drawdown_trough_date,
    }


def print_period(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 155)

    print(
        f"{'Exposure':<10}"
        f"{'Trades':>8}"
        f"{'Cash Skip':>12}"
        f"{'Limit Skip':>12}"
        f"{'Missing':>10}"
        f"{'Max Open':>10}"
        f"{'Max Invested':>15}"
        f"{'Profit':>15}"
        f"{'Return':>12}"
        f"{'Win Rate':>12}"
        f"{'Avg Trade':>12}"
        f"{'Max DD':>12}"
        f"{'Max DD $':>15}"
    )

    print("-" * 155)

    for limit in EXPOSURE_LIMITS:
        result = simulate_portfolio(
            rows,
            limit,
        )

        print(
            f"{format_percent(limit):<10}"
            f"{result['trades']:>8}"
            f"{result['cash_skips']:>12}"
            f"{result['exposure_skips']:>12}"
            f"{result['missing']:>10}"
            f"{result['max_open']:>10}"
            f"{format_money(result['max_cost_basis']):>15}"
            f"{format_money(result['profit']):>15}"
            f"{format_percent(result['return']):>12}"
            f"{format_percent(result['win_rate']):>12}"
            f"{format_percent(result['avg_trade']):>12}"
            f"{format_percent(result['max_drawdown']):>12}"
            f"{format_money(result['max_drawdown_dollars']):>15}"
        )

        print(
            f"{'':10}"
            f"Drawdown: "
            f"{result['drawdown_peak_date']} "
            f"to "
            f"{result['drawdown_trough_date']}"
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
        "PORTFOLIO EXPOSURE LIMIT TEST"
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
        "Exposure limits:",
        ", ".join(
            format_percent(limit)
            for limit in EXPOSURE_LIMITS
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
        "TRAINING — PORTFOLIO EXPOSURE LIMIT",
        training_matches,
    )

    print_period(
        "OUT-OF-SAMPLE — PORTFOLIO EXPOSURE LIMIT",
        testing_matches,
    )


if __name__ == "__main__":
    main()