import sys
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from src.analysis.experimental_signal import (
    SIGNAL_DESCRIPTION,
    get_experimental_signal_events,
)
from src.backtesting.backtester import (
    get_price_on_date,
    get_price_on_or_after,
)
from src.backtesting.time_split_statistics import (
    TRAIN_END,
    TEST_START,
    get_events,
    split_by_time,
)
from src.database import get_connection


DEFAULT_UNIVERSE = "expanded_500"
BENCHMARK = "SPY"

STARTING_CASH = Decimal("10000")
HOLDING_DAYS = 45
TICKER_CAP_PERCENT = Decimal("20")

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


def get_daily_prices(
    symbol,
    start_date,
    end_date,
):
    query = """
        SELECT
            trade_date,
            adjusted_close
        FROM daily_prices
        WHERE symbol = %s
          AND trade_date >= %s
          AND trade_date <= %s
        ORDER BY trade_date
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    symbol,
                    start_date,
                    end_date,
                ),
            )

            rows = cur.fetchall()

    return {
        row[0]: Decimal(str(row[1]))
        for row in rows
        if row[1] is not None
    }


def get_price_on_or_before(
    price_map,
    target_date,
):
    current_date = target_date

    for _ in range(10):
        if current_date in price_map:
            return price_map[
                current_date
            ]

        current_date -= timedelta(
            days=1
        )

    return None


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


def build_trade(
    row,
    trade_size,
):
    ticker = row[
        "ticker"
    ]

    entry_date = row[
        "entry_date"
    ]

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

    if exit_price is None:
        return None

    shares = (
        trade_size
        / entry_price
    )

    exit_value = (
        shares
        * exit_price
    )

    return {
        "ticker":
            ticker,

        "entry_date":
            entry_date,

        "exit_date":
            exit_record[
                "trade_date"
            ],

        "entry_price":
            entry_price,

        "exit_price":
            exit_price,

        "shares":
            shares,

        "investment":
            trade_size,

        "exit_value":
            exit_value,
    }


def build_trade_schedule(
    rows,
    trade_size,
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
    accepted = []

    skipped_cash = 0
    skipped_cap = 0
    missing_price = 0

    max_open = 0
    max_invested = Decimal("0")

    for row in ordered:
        entry_date = row[
            "entry_date"
        ]

        still_open = []

        for position in open_positions:
            if (
                position["exit_date"]
                <= entry_date
            ):
                cash += position[
                    "exit_value"
                ]
            else:
                still_open.append(
                    position
                )

        open_positions = (
            still_open
        )

        trade = build_trade(
            row,
            trade_size,
        )

        if trade is None:
            missing_price += 1
            continue

        if cash < trade_size:
            skipped_cash += 1
            continue

        ticker_exposure = (
            get_ticker_exposure(
                open_positions,
                row["ticker"],
            )
        )

        proposed_exposure = (
            ticker_exposure
            + trade_size
        )

        portfolio_value_for_cap = (
            cash
            + get_total_invested(
                open_positions
            )
        )

        maximum_allowed = (
            portfolio_value_for_cap
            * TICKER_CAP_PERCENT
            / Decimal("100")
        )

        if (
            proposed_exposure
            > maximum_allowed
        ):
            skipped_cap += 1
            continue

        open_positions.append(
            trade
        )

        accepted.append(
            trade
        )

        cash -= trade_size

        max_open = max(
            max_open,
            len(open_positions),
        )

        max_invested = max(
            max_invested,
            get_total_invested(
                open_positions
            ),
        )

    return {
        "trades":
            accepted,

        "skipped_cash":
            skipped_cash,

        "skipped_cap":
            skipped_cap,

        "missing_price":
            missing_price,

        "max_open":
            max_open,

        "max_invested":
            max_invested,
    }


def build_strategy_equity_curve(
    trades,
):
    if not trades:
        return []

    start_date = min(
        trade["entry_date"]
        for trade in trades
    )

    end_date = max(
        trade["exit_date"]
        for trade in trades
    )

    tickers = sorted(
        {
            trade["ticker"]
            for trade in trades
        }
    )

    price_maps = {}

    for ticker in tickers:
        price_maps[
            ticker
        ] = get_daily_prices(
            ticker,
            start_date,
            end_date,
        )

    spy_prices = get_daily_prices(
        BENCHMARK,
        start_date,
        end_date,
    )

    trading_dates = sorted(
        spy_prices.keys()
    )

    buys_by_date = defaultdict(
        list
    )

    sells_by_date = defaultdict(
        list
    )

    for trade in trades:
        buys_by_date[
            trade["entry_date"]
        ].append(
            trade
        )

        sells_by_date[
            trade["exit_date"]
        ].append(
            trade
        )

    cash = STARTING_CASH
    open_positions = []
    curve = []

    for current_date in trading_dates:
        for trade in sells_by_date.get(
            current_date,
            [],
        ):
            if trade in open_positions:
                cash += trade[
                    "exit_value"
                ]

                open_positions.remove(
                    trade
                )

        for trade in buys_by_date.get(
            current_date,
            [],
        ):
            cash -= trade[
                "investment"
            ]

            open_positions.append(
                trade
            )

        holdings_value = Decimal(
            "0"
        )

        for position in open_positions:
            price = get_price_on_or_before(
                price_maps[
                    position["ticker"]
                ],
                current_date,
            )

            if price is None:
                continue

            holdings_value += (
                position["shares"]
                * price
            )

        total_value = (
            cash
            + holdings_value
        )

        curve.append(
            {
                "date":
                    current_date,

                "value":
                    total_value,
            }
        )

    return curve


def build_spy_equity_curve(
    strategy_curve,
):
    if not strategy_curve:
        return []

    start_date = strategy_curve[
        0
    ]["date"]

    end_date = strategy_curve[
        -1
    ]["date"]

    spy_prices = get_daily_prices(
        BENCHMARK,
        start_date,
        end_date,
    )

    dates = sorted(
        spy_prices.keys()
    )

    if not dates:
        return []

    first_price = spy_prices[
        dates[0]
    ]

    shares = (
        STARTING_CASH
        / first_price
    )

    return [
        {
            "date":
                trade_date,

            "value":
                shares
                * spy_prices[
                    trade_date
                ],
        }
        for trade_date in dates
    ]


def calculate_drawdown(
    curve,
):
    if not curve:
        return None

    peak_value = curve[
        0
    ]["value"]

    peak_date = curve[
        0
    ]["date"]

    max_drawdown = Decimal(
        "0"
    )

    max_drawdown_dollars = Decimal(
        "0"
    )

    drawdown_peak_date = None
    drawdown_low_date = None

    for point in curve:
        value = point[
            "value"
        ]

        date = point[
            "date"
        ]

        if value > peak_value:
            peak_value = value
            peak_date = date

        drawdown_dollars = (
            peak_value
            - value
        )

        if peak_value != 0:
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
            > max_drawdown
        ):
            max_drawdown = (
                drawdown_percent
            )

            max_drawdown_dollars = (
                drawdown_dollars
            )

            drawdown_peak_date = (
                peak_date
            )

            drawdown_low_date = (
                date
            )

    return {
        "max_drawdown":
            max_drawdown,

        "max_drawdown_dollars":
            max_drawdown_dollars,

        "drawdown_peak_date":
            drawdown_peak_date,

        "drawdown_low_date":
            drawdown_low_date,
    }


def get_total_return(
    curve,
):
    if not curve:
        return None

    return (
        (
            curve[-1]["value"]
            - STARTING_CASH
        )
        / STARTING_CASH
        * Decimal("100")
    )


def print_period(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 155)

    print(
        f"{'Trade Size':<14}"
        f"{'Trades':>10}"
        f"{'Cash Skip':>12}"
        f"{'Cap Skip':>11}"
        f"{'Missing':>10}"
        f"{'Max Open':>11}"
        f"{'Max Invested':>16}"
        f"{'Return':>12}"
        f"{'Max DD':>12}"
        f"{'DD Dollars':>15}"
        f"{'SPY Return':>13}"
        f"{'SPY Max DD':>13}"
    )

    print("-" * 155)

    for trade_size in TRADE_SIZES:
        schedule = (
            build_trade_schedule(
                rows,
                trade_size,
            )
        )

        strategy_curve = (
            build_strategy_equity_curve(
                schedule["trades"]
            )
        )

        spy_curve = (
            build_spy_equity_curve(
                strategy_curve
            )
        )

        strategy_drawdown = (
            calculate_drawdown(
                strategy_curve
            )
        )

        spy_drawdown = (
            calculate_drawdown(
                spy_curve
            )
        )

        strategy_return = (
            get_total_return(
                strategy_curve
            )
        )

        spy_return = (
            get_total_return(
                spy_curve
            )
        )

        print(
            f"{format_money(trade_size):<14}"
            f"{len(schedule['trades']):>10}"
            f"{schedule['skipped_cash']:>12}"
            f"{schedule['skipped_cap']:>11}"
            f"{schedule['missing_price']:>10}"
            f"{schedule['max_open']:>11}"
            f"{format_money(schedule['max_invested']):>16}"
            f"{format_percent(strategy_return):>12}"
            f"{format_percent(
                -strategy_drawdown['max_drawdown']
                if strategy_drawdown
                else None
            ):>12}"
            f"{format_money(
                -strategy_drawdown[
                    'max_drawdown_dollars'
                ]
                if strategy_drawdown
                else Decimal('0')
            ):>15}"
            f"{format_percent(spy_return):>13}"
            f"{format_percent(
                -spy_drawdown['max_drawdown']
                if spy_drawdown
                else None
            ):>13}"
        )

        if strategy_drawdown:
            print(
                " " * 14,
                "Strategy max drawdown:",
                strategy_drawdown[
                    "drawdown_peak_date"
                ],
                "to",
                strategy_drawdown[
                    "drawdown_low_date"
                ],
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
        "EXPERIMENTAL SIGNAL PORTFOLIO DRAWDOWN TEST"
    )

    print("=" * 110)

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
        "Ticker cap:",
        f"{TICKER_CAP_PERCENT}%",
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

    print_period(
        "TRAINING PORTFOLIO DRAWDOWN",
        training_matches,
    )

    print_period(
        "OUT-OF-SAMPLE PORTFOLIO DRAWDOWN",
        testing_matches,
    )


if __name__ == "__main__":
    main()