from collections import defaultdict
from decimal import Decimal

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


def format_money(value):
    return f"${value:,.2f}"


def format_percent(value):
    return f"{value:+.2f}%"


def get_candidates():
    rows = get_backtest_events()

    training, testing = split_by_time(
        rows
    )

    return build_candidate_trades(
        testing,
        rows,
    )


def calculate_result(candidates):
    result = simulate_portfolio(
        candidates
    )

    final_value = result["cash"]

    profit = (
        final_value
        - STARTING_CASH
    )

    total_return = (
        profit
        / STARTING_CASH
        * Decimal("100")
    )

    completed = result[
        "completed_positions"
    ]

    winners = sum(
        1
        for trade in completed
        if trade["profit"] > 0
    )

    win_rate = (
        Decimal(winners)
        / Decimal(len(completed))
        * Decimal("100")
        if completed
        else Decimal("0")
    )

    return {
        "final_value":
            final_value,

        "profit":
            profit,

        "return":
            total_return,

        "completed":
            len(completed),

        "skipped":
            len(
                result[
                    "skipped_signals"
                ]
            ),

        "win_rate":
            win_rate,

        "result":
            result,
    }


def remove_tickers(
    candidates,
    excluded_tickers,
):
    excluded = {
        ticker.upper()
        for ticker in excluded_tickers
    }

    return [
        row
        for row in candidates
        if row["ticker"].upper()
        not in excluded
    ]


def one_trade_per_ticker_per_year(
    candidates,
):
    selected = []

    used = set()

    for row in candidates:
        key = (
            row["ticker"],
            row["entry_date"].year,
        )

        if key in used:
            continue

        used.add(
            key
        )

        selected.append(
            row
        )

    return selected


def no_overlapping_same_ticker(
    candidates,
):
    selected = []

    last_exit_by_ticker = {}

    for row in candidates:
        ticker = row[
            "ticker"
        ]

        entry_date = row[
            "entry_date"
        ]

        previous_exit = (
            last_exit_by_ticker.get(
                ticker
            )
        )

        if (
            previous_exit is not None
            and entry_date < previous_exit
        ):
            continue

        selected.append(
            row
        )

        last_exit_by_ticker[
            ticker
        ] = (
            entry_date
            + __import__(
                "datetime"
            ).timedelta(
                days=180
            )
        )

    return selected


def print_test_results(
    tests,
):
    print()
    print(
        "PORTFOLIO CONCENTRATION TEST"
    )

    print("=" * 125)

    print(
        f"{'Test':<38}"
        f"{'Trades':>10}"
        f"{'Skipped':>10}"
        f"{'Win Rate':>14}"
        f"{'Profit':>16}"
        f"{'Final Value':>18}"
        f"{'Return':>14}"
    )

    print("-" * 125)

    for name, candidates in tests:
        stats = calculate_result(
            candidates
        )

        print(
            f"{name:<38}"
            f"{stats['completed']:>10}"
            f"{stats['skipped']:>10}"
            f"{format_percent(stats['win_rate']):>14}"
            f"{format_money(stats['profit']):>16}"
            f"{format_money(stats['final_value']):>18}"
            f"{format_percent(stats['return']):>14}"
        )


def get_profit_by_ticker(
    result,
):
    totals = defaultdict(
        lambda: {
            "trades": 0,
            "profit": Decimal("0"),
        }
    )

    for trade in result[
        "completed_positions"
    ]:
        ticker = trade[
            "ticker"
        ]

        totals[ticker][
            "trades"
        ] += 1

        totals[ticker][
            "profit"
        ] += trade[
            "profit"
        ]

    return totals


def print_ticker_concentration(
    candidates,
):
    stats = calculate_result(
        candidates
    )

    totals = get_profit_by_ticker(
        stats["result"]
    )

    ordered = sorted(
        totals.items(),
        key=lambda item: (
            item[1]["profit"]
        ),
        reverse=True,
    )

    total_profit = stats[
        "profit"
    ]

    print()
    print(
        "PROFIT BY TICKER"
    )

    print("=" * 90)

    print(
        f"{'Ticker':<10}"
        f"{'Trades':>10}"
        f"{'Profit':>18}"
        f"{'% of Profit':>16}"
    )

    print("-" * 90)

    for ticker, values in ordered:
        if total_profit != 0:
            contribution = (
                values["profit"]
                / total_profit
                * Decimal("100")
            )
        else:
            contribution = (
                Decimal("0")
            )

        print(
            f"{ticker:<10}"
            f"{values['trades']:>10}"
            f"{format_money(values['profit']):>18}"
            f"{format_percent(contribution):>16}"
        )


def main():
    candidates = get_candidates()

    tests = [
        (
            "Normal strategy",
            candidates,
        ),

        (
            "No overlapping same ticker",
            no_overlapping_same_ticker(
                candidates
            ),
        ),

        (
            "Max 1 trade/ticker/year",
            one_trade_per_ticker_per_year(
                candidates
            ),
        ),

        (
            "Remove AMD",
            remove_tickers(
                candidates,
                {
                    "AMD",
                },
            ),
        ),

        (
            "Remove NEM",
            remove_tickers(
                candidates,
                {
                    "NEM",
                },
            ),
        ),

        (
            "Remove AMD + NEM",
            remove_tickers(
                candidates,
                {
                    "AMD",
                    "NEM",
                },
            ),
        ),
    ]

    print_test_results(
        tests
    )

    print_ticker_concentration(
        candidates
    )


if __name__ == "__main__":
    main()