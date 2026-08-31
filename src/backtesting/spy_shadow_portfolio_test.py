from datetime import timedelta
from decimal import Decimal

from src.backtesting.capital_constrained_backtest import (
    STARTING_CASH,
    TRADE_SIZE,
    build_candidate_trades,
)
from src.database import get_connection
from src.backtesting.recommendation_backtest import get_backtest_events
from src.backtesting.time_split_statistics import split_by_time


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


def get_entry_price(
    symbol,
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
                    symbol,
                    entry_date,
                ),
            )

            row = cur.fetchone()

    if not row or row[0] is None:
        return None

    return Decimal(
        str(row[0])
    )


def get_exit_price(
    symbol,
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
                    symbol,
                    target_date,
                ),
            )

            row = cur.fetchone()

    if not row or row[1] is None:
        return None

    return {
        "date":
            row[0],

        "price":
            Decimal(
                str(row[1])
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


def get_ticker_exposure(
    positions,
    ticker,
):
    return sum(
        (
            position["investment"]
            for position in positions
            if position["ticker"]
            == ticker
        ),
        Decimal("0"),
    )


def get_portfolio_value_for_cap(
    cash,
    positions,
):
    invested = sum(
        (
            position["investment"]
            for position in positions
        ),
        Decimal("0"),
    )

    return cash + invested


def build_strategy_trade_schedule(
    candidates,
):
    cash = STARTING_CASH
    open_positions = []

    accepted = []

    skipped_cash = 0
    skipped_cap = 0

    for row in candidates:
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

        if cash < TRADE_SIZE:
            skipped_cash += 1
            continue

        ticker = row[
            "ticker"
        ]

        ticker_exposure = (
            get_ticker_exposure(
                open_positions,
                ticker,
            )
        )

        proposed_exposure = (
            ticker_exposure
            + TRADE_SIZE
        )

        portfolio_value = (
            get_portfolio_value_for_cap(
                cash,
                open_positions,
            )
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
            skipped_cap += 1
            continue

        entry_price = get_entry_price(
            ticker,
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
            ticker,
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
            * exit_data[
                "price"
            ]
        )

        profit = (
            exit_value
            - TRADE_SIZE
        )

        trade = {
            "ticker":
                ticker,

            "entry_date":
                entry_date,

            "exit_date":
                exit_data[
                    "date"
                ],

            "investment":
                TRADE_SIZE,

            "entry_price":
                entry_price,

            "exit_price":
                exit_data[
                    "price"
                ],

            "exit_value":
                exit_value,

            "profit":
                profit,
        }

        open_positions.append(
            trade
        )

        accepted.append(
            trade
        )

        cash -= TRADE_SIZE

    return {
        "trades":
            accepted,

        "skipped_cash":
            skipped_cash,

        "skipped_cap":
            skipped_cap,
    }


def build_shadow_trade(
    strategy_trade,
):
    entry_price = get_entry_price(
        BENCHMARK,
        strategy_trade[
            "entry_date"
        ],
    )

    if entry_price is None:
        return None

    exit_data = get_exit_price(
        BENCHMARK,
        strategy_trade[
            "exit_date"
        ],
    )

    if exit_data is None:
        return None

    shares = (
        TRADE_SIZE
        / entry_price
    )

    exit_value = (
        shares
        * exit_data[
            "price"
        ]
    )

    profit = (
        exit_value
        - TRADE_SIZE
    )

    return {
        "ticker":
            BENCHMARK,

        "signal_ticker":
            strategy_trade[
                "ticker"
            ],

        "entry_date":
            strategy_trade[
                "entry_date"
            ],

        "exit_date":
            exit_data[
                "date"
            ],

        "investment":
            TRADE_SIZE,

        "entry_price":
            entry_price,

        "exit_price":
            exit_data[
                "price"
            ],

        "exit_value":
            exit_value,

        "profit":
            profit,
    }


def calculate_fixed_schedule_result(
    trades,
):
    total_profit = sum(
        (
            trade["profit"]
            for trade in trades
        ),
        Decimal("0"),
    )

    final_value = (
        STARTING_CASH
        + total_profit
    )

    total_return = (
        total_profit
        / STARTING_CASH
        * Decimal("100")
    )

    winners = sum(
        1
        for trade in trades
        if trade["profit"] > 0
    )

    win_rate = (
        Decimal(winners)
        / Decimal(len(trades))
        * Decimal("100")
        if trades
        else Decimal("0")
    )

    average_trade_return = (
        total_profit
        / (
            TRADE_SIZE
            * Decimal(
                len(trades)
            )
        )
        * Decimal("100")
        if trades
        else Decimal("0")
    )

    return {
        "trades":
            len(trades),

        "winners":
            winners,

        "win_rate":
            win_rate,

        "profit":
            total_profit,

        "final_value":
            final_value,

        "return":
            total_return,

        "average_trade_return":
            average_trade_return,
    }


def print_summary(
    strategy_trades,
    spy_trades,
):
    strategy = (
        calculate_fixed_schedule_result(
            strategy_trades
        )
    )

    spy = (
        calculate_fixed_schedule_result(
            spy_trades
        )
    )

    print()
    print(
        "SPY SHADOW PORTFOLIO TEST"
    )

    print("=" * 100)

    print(
        f"{'Metric':<30}"
        f"{'Strategy':>25}"
        f"{'SPY Shadow':>25}"
    )

    print("-" * 100)

    print(
        f"{'Trades':<30}"
        f"{strategy['trades']:>25}"
        f"{spy['trades']:>25}"
    )

    print(
        f"{'Winning trades':<30}"
        f"{strategy['winners']:>25}"
        f"{spy['winners']:>25}"
    )

    print(
        f"{'Win rate':<30}"
        f"{format_percent(strategy['win_rate']):>25}"
        f"{format_percent(spy['win_rate']):>25}"
    )

    print(
        f"{'Average trade return':<30}"
        f"{format_percent(strategy['average_trade_return']):>25}"
        f"{format_percent(spy['average_trade_return']):>25}"
    )

    print(
        f"{'Total profit':<30}"
        f"{format_money(strategy['profit']):>25}"
        f"{format_money(spy['profit']):>25}"
    )

    print(
        f"{'Equivalent final value':<30}"
        f"{format_money(strategy['final_value']):>25}"
        f"{format_money(spy['final_value']):>25}"
    )

    print(
        f"{'Equivalent return':<30}"
        f"{format_percent(strategy['return']):>25}"
        f"{format_percent(spy['return']):>25}"
    )

    advantage = (
        strategy[
            "profit"
        ]
        - spy[
            "profit"
        ]
    )

    advantage_percent = (
        advantage
        / STARTING_CASH
        * Decimal("100")
    )

    print()
    print(
        "STOCK-SELECTION ADVANTAGE"
    )

    print("-" * 100)

    print(
        f"Additional profit vs SPY shadow: "
        f"{format_money(advantage)}"
    )

    print(
        f"Additional return vs SPY shadow: "
        f"{format_percent(advantage_percent)}"
    )


def print_trade_comparison(
    strategy_trades,
    spy_trades,
):
    print()
    print(
        "TRADE-BY-TRADE COMPARISON"
    )

    print("=" * 125)

    print(
        f"{'Signal':<8}"
        f"{'Entry':<13}"
        f"{'Exit':<13}"
        f"{'Stock Profit':>16}"
        f"{'SPY Profit':>16}"
        f"{'Advantage':>16}"
    )

    print("-" * 125)

    for strategy, spy in zip(
        strategy_trades,
        spy_trades,
    ):
        advantage = (
            strategy[
                "profit"
            ]
            - spy[
                "profit"
            ]
        )

        print(
            f"{strategy['ticker']:<8}"
            f"{strategy['entry_date']!s:<13}"
            f"{strategy['exit_date']!s:<13}"
            f"{format_money(strategy['profit']):>16}"
            f"{format_money(spy['profit']):>16}"
            f"{format_money(advantage):>16}"
        )


def main():
    candidates = get_candidates()

    schedule = (
        build_strategy_trade_schedule(
            candidates
        )
    )

    strategy_trades = schedule[
        "trades"
    ]

    spy_trades = []

    for trade in strategy_trades:
        shadow = build_shadow_trade(
            trade
        )

        if shadow is not None:
            spy_trades.append(
                shadow
            )

    print()
    print(
        f"Accepted strategy trades: "
        f"{len(strategy_trades)}"
    )

    print(
        f"SPY shadow trades: "
        f"{len(spy_trades)}"
    )

    print(
        f"Signals skipped for cash: "
        f"{schedule['skipped_cash']}"
    )

    print(
        f"Signals skipped for 20% cap: "
        f"{schedule['skipped_cap']}"
    )

    print_summary(
        strategy_trades,
        spy_trades,
    )

    print_trade_comparison(
        strategy_trades,
        spy_trades,
    )


if __name__ == "__main__":
    main()