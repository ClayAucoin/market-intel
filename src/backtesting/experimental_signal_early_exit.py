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

EARLY_EXIT_THRESHOLDS = [
    Decimal("-10"),
    Decimal("-5"),
    Decimal("0"),
    Decimal("5"),
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


def get_fixed_horizon_values(
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


def get_early_exit_values(
    rows,
    threshold,
):
    values = []
    exited_early = 0
    held_to_45 = 0

    for row in rows:
        excess_30d = get_excess_return(
            row["ticker"],
            row["entry_date"],
            30,
        )

        excess_45d = get_excess_return(
            row["ticker"],
            row["entry_date"],
            45,
        )

        if (
            excess_30d is None
            or excess_45d is None
        ):
            continue

        if excess_30d <= threshold:
            values.append(
                excess_30d
            )
            exited_early += 1
        else:
            values.append(
                excess_45d
            )
            held_to_45 += 1

    return {
        "values": values,
        "exited_early": exited_early,
        "held_to_45": held_to_45,
    }


def print_stats(
    label,
    values,
    exited_early=None,
    held_to_45=None,
):
    average = calculate_average(
        values
    )

    median_value = calculate_median(
        values
    )

    win_rate = calculate_win_rate(
        values
    )

    print(
        f"{label:<26}"
        f"{len(values):>7}"
        f"{format_percent(average):>14}"
        f"{format_percent(median_value):>14}"
        f"{format_win_rate(win_rate):>14}"
        f"{(
            str(exited_early)
            if exited_early is not None
            else '-'
        ):>12}"
        f"{(
            str(held_to_45)
            if held_to_45 is not None
            else '-'
        ):>12}"
    )


def print_period_results(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 100)

    print(
        f"{'Strategy':<26}"
        f"{'N':>7}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
        f"{'Exit 30':>12}"
        f"{'Hold 45':>12}"
    )

    print("-" * 100)

    values_30d = get_fixed_horizon_values(
        rows,
        30,
    )

    values_45d = get_fixed_horizon_values(
        rows,
        45,
    )

    print_stats(
        "Always exit 30d",
        values_30d,
    )

    print_stats(
        "Always exit 45d",
        values_45d,
    )

    for threshold in EARLY_EXIT_THRESHOLDS:
        result = get_early_exit_values(
            rows,
            threshold,
        )

        label = (
            f"30d <= {threshold:+.0f}%"
        )

        print_stats(
            label,
            result["values"],
            result["exited_early"],
            result["held_to_45"],
        )


def main():
    universe_name = get_universe_name()

    print()
    print(
        "EXPERIMENTAL SIGNAL EARLY-EXIT TEST"
    )
    print(
        f"Universe: {universe_name}"
    )

    print()
    print(
        "Rule being tested:"
    )
    print(
        "At day 30, exit weak trades immediately; "
        "otherwise continue holding until day 45."
    )
    print(
        "Thresholds are evaluated on TRAINING first "
        "and then checked out-of-sample."
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

    print_period_results(
        "TRAINING PERIOD",
        training,
    )

    print_period_results(
        "OUT-OF-SAMPLE PERIOD",
        testing,
    )

    print()
    print(
        "Do not choose a threshold from the OOS results. "
        "The training period must determine whether an "
        "early-exit rule deserves further testing."
    )
    print()


if __name__ == "__main__":
    main()