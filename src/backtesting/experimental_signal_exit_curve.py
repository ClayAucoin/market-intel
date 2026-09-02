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

EXIT_DAYS = [
    30,
    35,
    40,
    45,
    50,
    55,
    60,
]


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


def calculate_trimmed_average(values):
    if len(values) < 10:
        return calculate_average(values)

    sorted_values = sorted(values)

    trim_count = max(
        1,
        int(len(sorted_values) * 0.10),
    )

    trimmed = sorted_values[
        trim_count:-trim_count
    ]

    if not trimmed:
        return None

    return calculate_average(trimmed)


def format_percent(value):
    if value is None:
        return "N/A"

    return f"{value:+.2f}%"


def format_win_rate(value):
    if value is None:
        return "N/A"

    return f"{value:.2f}%"


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


def get_horizon_values(
    rows,
    days,
):
    values = []

    for row in rows:
        value = get_excess_return(
            row["ticker"],
            row["entry_date"],
            days,
        )

        if value is not None:
            values.append(value)

    return values


def print_curve(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 96)

    print(
        f"{'Exit':<10}"
        f"{'N':>8}"
        f"{'Average':>15}"
        f"{'Median':>15}"
        f"{'Trim Avg':>15}"
        f"{'Win Rate':>15}"
        f"{'Worst':>15}"
    )

    print("-" * 96)

    results = []

    for days in EXIT_DAYS:
        values = get_horizon_values(
            rows,
            days,
        )

        average = calculate_average(
            values
        )

        median_value = calculate_median(
            values
        )

        trimmed_average = (
            calculate_trimmed_average(
                values
            )
        )

        win_rate = calculate_win_rate(
            values
        )

        worst = (
            min(values)
            if values
            else None
        )

        results.append(
            {
                "days": days,
                "n": len(values),
                "average": average,
                "median": median_value,
                "trimmed_average": (
                    trimmed_average
                ),
                "win_rate": win_rate,
                "worst": worst,
            }
        )

        print(
            f"{str(days) + 'd':<10}"
            f"{len(values):>8}"
            f"{format_percent(average):>15}"
            f"{format_percent(median_value):>15}"
            f"{format_percent(trimmed_average):>15}"
            f"{format_win_rate(win_rate):>15}"
            f"{format_percent(worst):>15}"
        )

    return results


def print_best_training_results(
    results,
):
    valid_results = [
        result
        for result in results
        if result["average"] is not None
    ]

    if not valid_results:
        return

    best_average = max(
        valid_results,
        key=lambda result: result["average"],
    )

    best_median = max(
        valid_results,
        key=lambda result: result["median"],
    )

    best_trimmed = max(
        valid_results,
        key=lambda result: (
            result["trimmed_average"]
        ),
    )

    best_win_rate = max(
        valid_results,
        key=lambda result: result["win_rate"],
    )

    print()
    print("TRAINING LEADERS")
    print("=" * 60)

    print(
        "Best average: "
        f"{best_average['days']}d "
        f"({format_percent(best_average['average'])})"
    )

    print(
        "Best median: "
        f"{best_median['days']}d "
        f"({format_percent(best_median['median'])})"
    )

    print(
        "Best trimmed average: "
        f"{best_trimmed['days']}d "
        f"({format_percent(best_trimmed['trimmed_average'])})"
    )

    print(
        "Best win rate: "
        f"{best_win_rate['days']}d "
        f"({format_win_rate(best_win_rate['win_rate'])})"
    )


def main():
    universe_name = get_universe_name()

    print()
    print(
        "EXPERIMENTAL SIGNAL EXIT CURVE"
    )

    print(
        f"Universe: {universe_name}"
    )

    print()
    print(
        "Testing fixed exits every 5 calendar days "
        "from day 30 through day 60."
    )

    print(
        "Entry = adjusted open on the event entry date."
    )

    print(
        "Exit = adjusted close on the first trading day "
        "on or after the target date."
    )

    print(
        "Returns shown are excess returns versus SPY."
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

    training_results = print_curve(
        "TRAINING PERIOD",
        training,
    )

    print_best_training_results(
        training_results
    )

    print_curve(
        "OUT-OF-SAMPLE PERIOD",
        testing,
    )

    print()
    print(
        "Use the training curve to judge the exit window. "
        "The OOS results are confirmation only."
    )
    print()


if __name__ == "__main__":
    main()