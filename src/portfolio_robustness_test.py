from datetime import timedelta
from decimal import Decimal

from src.backtester import (
    get_price_on_date,
    get_price_on_or_after,
)
from src.capital_constrained_backtest import (
    STARTING_CASH,
    build_candidate_trades,
    simulate_portfolio,
)
from src.recommendation_backtest import (
    get_backtest_events,
)
from src.time_split_statistics import (
    split_by_time,
)


BENCHMARK = "SPY"


def format_money(value):
    if value is None:
        return "-"

    return f"${value:,.2f}"


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def get_strategy_result():
    rows = get_backtest_events()

    training, testing = split_by_time(
        rows
    )

    candidates = build_candidate_trades(
        testing,
        rows,
    )

    result = simulate_portfolio(
        candidates
    )

    return (
        candidates,
        result,
    )


def get_portfolio_final_value(
    result,
):
    return result[
        "cash"
    ]


def get_portfolio_profit(
    result,
):
    return (
        get_portfolio_final_value(
            result
        )
        - STARTING_CASH
    )


def get_portfolio_return(
    result,
):
    return (
        get_portfolio_profit(
            result
        )
        / STARTING_CASH
        * Decimal("100")
    )


def get_test_period_dates(
    candidates,
    result,
):
    if not candidates:
        return None, None

    start_date = min(
        row["entry_date"]
        for row in candidates
    )

    completed = result[
        "completed_positions"
    ]

    if not completed:
        return start_date, None

    end_date = max(
        row["exit_date"]
        for row in completed
    )

    return (
        start_date,
        end_date,
    )


def calculate_spy_benchmark(
    start_date,
    end_date,
):
    entry = get_price_on_date(
        BENCHMARK,
        start_date,
    )

    if entry is None:
        entry = get_price_on_or_after(
            BENCHMARK,
            start_date,
        )

        if entry is None:
            return None

        entry_date = entry[
            "trade_date"
        ]

        entry_price = entry[
            "price"
        ]

    else:
        entry_date = entry[
            "trade_date"
        ]

        entry_price = entry[
            "adjusted_open"
        ]

        if entry_price is None:
            entry_price = entry[
                "adjusted_close"
            ]

    exit_record = get_price_on_or_after(
        BENCHMARK,
        end_date,
    )

    if exit_record is None:
        return None

    exit_date = exit_record[
        "trade_date"
    ]

    exit_price = exit_record[
        "price"
    ]

    if entry_price == 0:
        return None

    shares = (
        STARTING_CASH
        / entry_price
    )

    final_value = (
        shares
        * exit_price
    )

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
        "entry_date":
            entry_date,

        "exit_date":
            exit_date,

        "entry_price":
            entry_price,

        "exit_price":
            exit_price,

        "final_value":
            final_value,

        "profit":
            profit,

        "return":
            total_return,
    }


def get_trade_profit(
    trade,
):
    return trade[
        "profit"
    ]


def print_largest_winners_and_losers(
    result,
):
    completed = result[
        "completed_positions"
    ]

    sorted_by_profit = sorted(
        completed,
        key=get_trade_profit,
        reverse=True,
    )

    print()
    print(
        "LARGEST WINNERS"
    )

    print("=" * 90)

    print(
        f"{'Ticker':<8}"
        f"{'Entry':>12}"
        f"{'Return':>12}"
        f"{'Profit':>14}"
    )

    print("-" * 90)

    for trade in sorted_by_profit[:10]:
        print(
            f"{trade['ticker']:<8}"
            f"{str(trade['entry_date']):>12}"
            f"{format_percent(trade['return']):>12}"
            f"{format_money(trade['profit']):>14}"
        )

    print()
    print(
        "LARGEST LOSERS"
    )

    print("=" * 90)

    print(
        f"{'Ticker':<8}"
        f"{'Entry':>12}"
        f"{'Return':>12}"
        f"{'Profit':>14}"
    )

    print("-" * 90)

    for trade in sorted_by_profit[-10:]:
        print(
            f"{trade['ticker']:<8}"
            f"{str(trade['entry_date']):>12}"
            f"{format_percent(trade['return']):>12}"
            f"{format_money(trade['profit']):>14}"
        )


def calculate_removed_winner_result(
    result,
    number_to_remove,
):
    completed = result[
        "completed_positions"
    ]

    sorted_by_profit = sorted(
        completed,
        key=get_trade_profit,
        reverse=True,
    )

    removed = sorted_by_profit[
        :number_to_remove
    ]

    removed_profit = sum(
        (
            trade["profit"]
            for trade in removed
        ),
        Decimal("0"),
    )

    adjusted_profit = (
        get_portfolio_profit(
            result
        )
        - removed_profit
    )

    adjusted_final_value = (
        STARTING_CASH
        + adjusted_profit
    )

    adjusted_return = (
        adjusted_profit
        / STARTING_CASH
        * Decimal("100")
    )

    return {
        "removed":
            removed,

        "removed_profit":
            removed_profit,

        "profit":
            adjusted_profit,

        "final_value":
            adjusted_final_value,

        "return":
            adjusted_return,
    }


def print_robustness_test(
    result,
):
    print()
    print(
        "ROBUSTNESS TEST"
    )

    print("=" * 110)

    print(
        "This removes the biggest winners "
        "from the historical result."
    )

    print()

    print(
        f"{'Test':<28}"
        f"{'Removed Profit':>18}"
        f"{'Final Value':>18}"
        f"{'Total Return':>16}"
    )

    print("-" * 110)

    print(
        f"{'Original strategy':<28}"
        f"{'-':>18}"
        f"{format_money(get_portfolio_final_value(result)):>18}"
        f"{format_percent(get_portfolio_return(result)):>16}"
    )

    for number_to_remove in [
        1,
        2,
        3,
        5,
    ]:
        adjusted = (
            calculate_removed_winner_result(
                result,
                number_to_remove,
            )
        )

        label = (
            f"Remove top {number_to_remove}"
        )

        print(
            f"{label:<28}"
            f"{format_money(adjusted['removed_profit']):>18}"
            f"{format_money(adjusted['final_value']):>18}"
            f"{format_percent(adjusted['return']):>16}"
        )


def print_benchmark_comparison(
    candidates,
    result,
):
    start_date, end_date = (
        get_test_period_dates(
            candidates,
            result,
        )
    )

    benchmark = (
        calculate_spy_benchmark(
            start_date,
            end_date,
        )
    )

    print()
    print(
        "STRATEGY VS SPY"
    )

    print("=" * 90)

    print(
        "Strategy test period:"
    )

    print(
        f"  Start: {start_date}"
    )

    print(
        f"  End:   {end_date}"
    )

    print()

    print(
        "Strategy:"
    )

    print(
        "  Starting value:",
        format_money(
            STARTING_CASH
        ),
    )

    print(
        "  Final value:",
        format_money(
            get_portfolio_final_value(
                result
            )
        ),
    )

    print(
        "  Profit:",
        format_money(
            get_portfolio_profit(
                result
            )
        ),
    )

    print(
        "  Return:",
        format_percent(
            get_portfolio_return(
                result
            )
        ),
    )

    print()

    if benchmark is None:
        print(
            "SPY benchmark could not be calculated."
        )

        return

    print(
        "SPY buy-and-hold:"
    )

    print(
        "  Entry date:",
        benchmark[
            "entry_date"
        ],
    )

    print(
        "  Exit date:",
        benchmark[
            "exit_date"
        ],
    )

    print(
        "  Starting value:",
        format_money(
            STARTING_CASH
        ),
    )

    print(
        "  Final value:",
        format_money(
            benchmark[
                "final_value"
            ]
        ),
    )

    print(
        "  Profit:",
        format_money(
            benchmark[
                "profit"
            ]
        ),
    )

    print(
        "  Return:",
        format_percent(
            benchmark[
                "return"
            ]
        ),
    )

    difference = (
        get_portfolio_final_value(
            result
        )
        - benchmark[
            "final_value"
        ]
    )

    return_difference = (
        get_portfolio_return(
            result
        )
        - benchmark[
            "return"
        ]
    )

    print()
    print(
        "Strategy advantage:"
    )

    print(
        "  Additional dollars:",
        format_money(
            difference
        ),
    )

    print(
        "  Additional return:",
        format_percent(
            return_difference
        ),
    )


def main():
    (
        candidates,
        result,
    ) = get_strategy_result()

    print()
    print(
        "PORTFOLIO ROBUSTNESS AND BENCHMARK TEST"
    )

    print_benchmark_comparison(
        candidates,
        result,
    )

    print_largest_winners_and_losers(
        result
    )

    print_robustness_test(
        result
    )


if __name__ == "__main__":
    main()