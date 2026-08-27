from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from src.capital_constrained_backtest import (
    STARTING_CASH,
    TRADE_SIZE,
    build_candidate_trades,
)
from src.database import get_connection
from src.recommendation_backtest import get_backtest_events
from src.time_split_statistics import split_by_time


HOLDING_DAYS = 180
TICKER_CAP_PERCENT = Decimal("20")
BENCHMARK = "SPY"


def format_money(value):
    return f"${value:,.2f}"


def format_percent(value):
    return f"{value:+.2f}%"


def get_candidates():
    rows = get_backtest_events()
    training, testing = split_by_time(rows)

    return build_candidate_trades(
        testing,
        rows,
    )


def get_daily_prices(symbol, start_date, end_date):
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
            return price_map[current_date]

        current_date -= timedelta(days=1)

    return None


def get_entry_price(
    ticker,
    entry_date,
):
    query = """
        SELECT adjusted_open
        FROM daily_prices
        WHERE symbol = %s
          AND trade_date = %s
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    ticker,
                    entry_date,
                ),
            )

            row = cur.fetchone()

    if not row or row[0] is None:
        return None

    return Decimal(str(row[0]))


def get_exit_price(
    ticker,
    target_date,
):
    query = """
        SELECT
            trade_date,
            adjusted_close
        FROM daily_prices
        WHERE symbol = %s
          AND trade_date >= %s
        ORDER BY trade_date
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    ticker,
                    target_date,
                ),
            )

            row = cur.fetchone()

    if not row:
        return None

    return {
        "date": row[0],
        "price": Decimal(
            str(row[1])
        ),
    }


def build_trade_schedule(
    candidates,
):
    cash = STARTING_CASH
    open_positions = []
    accepted = []

    for row in candidates:
        entry_date = row["entry_date"]

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

        open_positions = still_open

        if cash < TRADE_SIZE:
            continue

        portfolio_value = (
            cash
            + sum(
                position["investment"]
                for position
                in open_positions
            )
        )

        ticker_exposure = sum(
            (
                position["investment"]
                for position
                in open_positions
                if position["ticker"]
                == row["ticker"]
            ),
            Decimal("0"),
        )

        proposed_exposure = (
            ticker_exposure
            + TRADE_SIZE
        )

        maximum_allowed = (
            portfolio_value
            * TICKER_CAP_PERCENT
            / Decimal("100")
        )

        if (
            proposed_exposure
            > maximum_allowed
        ):
            continue

        entry_price = get_entry_price(
            row["ticker"],
            entry_date,
        )

        if entry_price is None:
            continue

        target_exit_date = (
            entry_date
            + timedelta(
                days=HOLDING_DAYS
            )
        )

        exit_data = get_exit_price(
            row["ticker"],
            target_exit_date,
        )

        if exit_data is None:
            continue

        shares = (
            TRADE_SIZE
            / entry_price
        )

        exit_value = (
            shares
            * exit_data["price"]
        )

        position = {
            "ticker":
                row["ticker"],

            "entry_date":
                entry_date,

            "exit_date":
                exit_data["date"],

            "entry_price":
                entry_price,

            "exit_price":
                exit_data["price"],

            "shares":
                shares,

            "investment":
                TRADE_SIZE,

            "exit_value":
                exit_value,
        }

        open_positions.append(
            position
        )

        accepted.append(
            position
        )

        cash -= TRADE_SIZE

    return accepted


def build_strategy_equity_curve(
    trades,
):
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
        price_maps[ticker] = (
            get_daily_prices(
                ticker,
                start_date,
                end_date,
            )
        )

    spy_prices = get_daily_prices(
        BENCHMARK,
        start_date,
        end_date,
    )

    trading_dates = sorted(
        spy_prices.keys()
    )

    buys_by_date = defaultdict(list)
    sells_by_date = defaultdict(list)

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
            matching = None

            for position in open_positions:
                if position is trade:
                    matching = position
                    break

            if matching is not None:
                cash += matching[
                    "exit_value"
                ]

                open_positions.remove(
                    matching
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

        holdings_value = Decimal("0")

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
    peak_value = curve[
        0
    ]["value"]

    peak_date = curve[
        0
    ]["date"]

    max_drawdown = Decimal("0")
    max_drawdown_dollars = Decimal("0")

    drawdown_peak_date = None
    drawdown_low_date = None

    lowest_value = curve[
        0
    ]["value"]

    lowest_date = curve[
        0
    ]["date"]

    highest_value = curve[
        0
    ]["value"]

    highest_date = curve[
        0
    ]["date"]

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

        if value > highest_value:
            highest_value = value
            highest_date = date

        if value < lowest_value:
            lowest_value = value
            lowest_date = date

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

        "highest_value":
            highest_value,

        "highest_date":
            highest_date,

        "lowest_value":
            lowest_value,

        "lowest_date":
            lowest_date,
    }


def calculate_yearly_returns(
    curve,
):
    by_year = defaultdict(list)

    for point in curve:
        by_year[
            point["date"].year
        ].append(
            point
        )

    results = {}

    for year, points in sorted(
        by_year.items()
    ):
        start_value = points[
            0
        ]["value"]

        end_value = points[
            -1
        ]["value"]

        yearly_return = (
            (
                end_value
                - start_value
            )
            / start_value
            * Decimal("100")
        )

        results[year] = {
            "start_value":
                start_value,

            "end_value":
                end_value,

            "return":
                yearly_return,
        }

    return results


def print_summary(
    strategy_curve,
    spy_curve,
):
    strategy_stats = (
        calculate_drawdown(
            strategy_curve
        )
    )

    spy_stats = (
        calculate_drawdown(
            spy_curve
        )
    )

    strategy_return = (
        (
            strategy_curve[-1]["value"]
            - STARTING_CASH
        )
        / STARTING_CASH
        * Decimal("100")
    )

    spy_return = (
        (
            spy_curve[-1]["value"]
            - STARTING_CASH
        )
        / STARTING_CASH
        * Decimal("100")
    )

    print()
    print(
        "PORTFOLIO DRAWDOWN TEST"
    )

    print("=" * 95)

    print(
        f"{'Metric':<32}"
        f"{'Strategy':>25}"
        f"{'SPY':>25}"
    )

    print("-" * 95)

    print(
        f"{'Final value':<32}"
        f"{format_money(strategy_curve[-1]['value']):>25}"
        f"{format_money(spy_curve[-1]['value']):>25}"
    )

    print(
        f"{'Total return':<32}"
        f"{format_percent(strategy_return):>25}"
        f"{format_percent(spy_return):>25}"
    )

    print(
        f"{'Maximum drawdown':<32}"
        f"{format_percent(-strategy_stats['max_drawdown']):>25}"
        f"{format_percent(-spy_stats['max_drawdown']):>25}"
    )

    print(
        f"{'Worst dollar decline':<32}"
        f"{format_money(-strategy_stats['max_drawdown_dollars']):>25}"
        f"{format_money(-spy_stats['max_drawdown_dollars']):>25}"
    )

    print(
        f"{'Highest account value':<32}"
        f"{format_money(strategy_stats['highest_value']):>25}"
        f"{format_money(spy_stats['highest_value']):>25}"
    )

    print(
        f"{'Lowest account value':<32}"
        f"{format_money(strategy_stats['lowest_value']):>25}"
        f"{format_money(spy_stats['lowest_value']):>25}"
    )

    print()
    print(
        "MAXIMUM DRAWDOWN PERIOD"
    )

    print("-" * 95)

    print(
        "Strategy: "
        f"{strategy_stats['drawdown_peak_date']} "
        "to "
        f"{strategy_stats['drawdown_low_date']}"
    )

    print(
        "SPY:      "
        f"{spy_stats['drawdown_peak_date']} "
        "to "
        f"{spy_stats['drawdown_low_date']}"
    )


def print_yearly_results(
    strategy_curve,
    spy_curve,
):
    strategy_years = (
        calculate_yearly_returns(
            strategy_curve
        )
    )

    spy_years = (
        calculate_yearly_returns(
            spy_curve
        )
    )

    years = sorted(
        set(strategy_years)
        & set(spy_years)
    )

    print()
    print(
        "YEAR-BY-YEAR PERFORMANCE"
    )

    print("=" * 95)

    print(
        f"{'Year':<10}"
        f"{'Strategy Start':>18}"
        f"{'Strategy End':>18}"
        f"{'Strategy':>15}"
        f"{'SPY':>15}"
    )

    print("-" * 95)

    for year in years:
        strategy = strategy_years[
            year
        ]

        spy = spy_years[
            year
        ]

        print(
            f"{year:<10}"
            f"{format_money(strategy['start_value']):>18}"
            f"{format_money(strategy['end_value']):>18}"
            f"{format_percent(strategy['return']):>15}"
            f"{format_percent(spy['return']):>15}"
        )


def main():
    candidates = get_candidates()

    trades = build_trade_schedule(
        candidates
    )

    strategy_curve = (
        build_strategy_equity_curve(
            trades
        )
    )

    spy_curve = (
        build_spy_equity_curve(
            strategy_curve
        )
    )

    print()
    print(
        f"Accepted strategy trades: "
        f"{len(trades)}"
    )

    print_summary(
        strategy_curve,
        spy_curve,
    )

    print_yearly_results(
        strategy_curve,
        spy_curve,
    )


if __name__ == "__main__":
    main()