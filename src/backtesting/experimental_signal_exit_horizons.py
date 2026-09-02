import sys

from datetime import timedelta
from decimal import Decimal
from statistics import median

from src.analysis.experimental_signal import (
    qualifies_experimental_signal,
)
from src.backtesting.backtester import (
    calculate_return,
    get_price_on_date,
    get_price_on_or_after,
)
from src.backtesting.time_split_statistics import (
    get_events,
    split_by_time,
)


DEFAULT_UNIVERSE = "expanded_500"
BENCHMARK = "SPY"

EXIT_HORIZONS = {
    "10d": 10,
    "20d": 20,
    "30d": 30,
    "45d": 45,
    "60d": 60,
    "90d": 90,
}


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


def calculate_average(values):
    if not values:
        return None

    return round(
        sum(values) / Decimal(len(values)),
        2,
    )


def calculate_median(values):
    if not values:
        return None

    return round(
        Decimal(str(median(values))),
        2,
    )


def calculate_win_rate(values):
    if not values:
        return None

    wins = sum(
        1
        for value in values
        if value > 0
    )

    return round(
        (
            Decimal(wins)
            / Decimal(len(values))
        )
        * Decimal("100"),
        2,
    )


def get_excess_return(
    ticker,
    entry_date,
    days,
):
    stock_entry = get_price_on_date(
        ticker,
        entry_date,
    )

    benchmark_entry = get_price_on_date(
        BENCHMARK,
        entry_date,
    )

    if (
        stock_entry is None
        or benchmark_entry is None
    ):
        return None

    stock_entry_price = stock_entry[
        "adjusted_open"
    ]

    benchmark_entry_price = benchmark_entry[
        "adjusted_open"
    ]

    if (
        stock_entry_price is None
        or benchmark_entry_price is None
    ):
        return None

    target_date = (
        entry_date
        + timedelta(days=days)
    )

    stock_exit = get_price_on_or_after(
        ticker,
        target_date,
    )

    benchmark_exit = get_price_on_or_after(
        BENCHMARK,
        target_date,
    )

    if (
        stock_exit is None
        or benchmark_exit is None
    ):
        return None

    stock_return = calculate_return(
        stock_entry_price,
        stock_exit["price"],
    )

    benchmark_return = calculate_return(
        benchmark_entry_price,
        benchmark_exit["price"],
    )

    if (
        stock_return is None
        or benchmark_return is None
    ):
        return None

    return round(
        stock_return - benchmark_return,
        2,
    )


def calculate_horizon_results(rows):
    results = {}

    for name, days in EXIT_HORIZONS.items():
        values = []

        for row in rows:
            value = get_excess_return(
                row["ticker"],
                row["entry_date"],
                days,
            )

            if value is not None:
                values.append(value)

        results[name] = {
            "n": len(values),
            "average": calculate_average(
                values
            ),
            "median": calculate_median(
                values
            ),
            "win_rate": calculate_win_rate(
                values
            ),
        }

    return results


def format_number(value):
    if value is None:
        return "N/A"

    return f"{value:+.2f}%"


def format_win_rate(value):
    if value is None:
        return "N/A"

    return f"{value:.2f}%"


def print_results(
    title,
    results,
):
    print()
    print(title)
    print(
        "=" * 72
    )

    print(
        f"{'Exit':<10}"
        f"{'N':>8}"
        f"{'Avg Excess':>18}"
        f"{'Median':>18}"
        f"{'Win Rate':>18}"
    )

    print(
        "-" * 72
    )

    for name in EXIT_HORIZONS:
        stats = results[name]

        print(
            f"{name:<10}"
            f"{stats['n']:>8}"
            f"{format_number(stats['average']):>18}"
            f"{format_number(stats['median']):>18}"
            f"{format_win_rate(stats['win_rate']):>18}"
        )


def main():
    universe_name = get_universe_name()

    print()
    print(
        "EXPERIMENTAL SIGNAL EXIT HORIZON TEST"
    )
    print(
        f"Universe: {universe_name}"
    )
    print(
        "Signal: Revenue acceleration >= 20% + "
        "operating margin improving + "
        "20-day excess return vs. SPY > 0"
    )

    rows = get_events(
        universe_name
    )

    signal_rows = [
        row
        for row in rows
        if qualifies_experimental_signal(
            row
        )
    ]

    training, testing = split_by_time(
        signal_rows
    )

    print()
    print(
        f"Total events: {len(rows)}"
    )
    print(
        f"Signal matches: {len(signal_rows)}"
    )
    print(
        f"Training matches: {len(training)}"
    )
    print(
        f"OOS matches: {len(testing)}"
    )

    training_results = (
        calculate_horizon_results(
            training
        )
    )

    testing_results = (
        calculate_horizon_results(
            testing
        )
    )

    print_results(
        "TRAINING PERIOD",
        training_results,
    )

    print_results(
        "OUT-OF-SAMPLE PERIOD",
        testing_results,
    )

    print()
    print(
        "Exit dates use the first trading day's "
        "adjusted close on or after each calendar-day target."
    )
    print()


if __name__ == "__main__":
    main()