import sys

from decimal import Decimal
from statistics import median

from src.backtesting.time_split_statistics import (
    DEFAULT_UNIVERSE,
    TRAIN_END,
    TEST_START,
    get_events,
    split_by_time,
)


HORIZON = "30d"


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


def is_present(row, field):
    return row.get(field) is not None


def revenue_acceleration_only(row):
    return (
        is_present(row, "revenue_acceleration")
        and row["revenue_acceleration"] >= Decimal("20")
    )


def revenue_acceleration_and_margin(row):
    return (
        revenue_acceleration_only(row)
        and is_present(row, "operating_margin_change")
        and row["operating_margin_change"] > 0
    )


def revenue_acceleration_and_momentum(row):
    return (
        revenue_acceleration_only(row)
        and is_present(row, "pre_excess_20d")
        and row["pre_excess_20d"] > 0
    )


def exact_three_part_signal(row):
    return (
        revenue_acceleration_only(row)
        and is_present(row, "operating_margin_change")
        and row["operating_margin_change"] > 0
        and is_present(row, "pre_excess_20d")
        and row["pre_excess_20d"] > 0
    )


STRATEGIES = [
    (
        "Revenue Accel >=20%",
        revenue_acceleration_only,
    ),
    (
        "Accel + Margin",
        revenue_acceleration_and_margin,
    ),
    (
        "Accel + Momentum",
        revenue_acceleration_and_momentum,
    ),
    (
        "Exact 3-Part Signal",
        exact_three_part_signal,
    ),
]


def calculate_average(values):
    if not values:
        return None

    return (
        sum(values, Decimal("0"))
        / Decimal(len(values))
    )


def calculate_median(values):
    if not values:
        return None

    return Decimal(
        str(
            median(values)
        )
    )


def calculate_win_rate(values):
    if not values:
        return None

    wins = sum(
        1
        for value in values
        if value > 0
    )

    return (
        Decimal(wins)
        / Decimal(len(values))
        * Decimal("100")
    )


def calculate_stats(rows):
    values = [
        row[f"excess_{HORIZON}"]
        for row in rows
        if row.get(f"excess_{HORIZON}") is not None
    ]

    return {
        "n": len(values),
        "average": calculate_average(values),
        "median": calculate_median(values),
        "win_rate": calculate_win_rate(values),
    }


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def get_matches(rows, strategy):
    return [
        row
        for row in rows
        if strategy(row)
    ]


def print_header():
    print(
        f"{'Strategy':<28}"
        f"{'N':>8}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
    )

    print("-" * 78)


def print_strategy_row(label, rows):
    stats = calculate_stats(rows)

    print(
        f"{label:<28}"
        f"{stats['n']:>8}"
        f"{format_percent(stats['average']):>14}"
        f"{format_percent(stats['median']):>14}"
        f"{format_percent(stats['win_rate']):>14}"
    )


def print_period(title, rows):
    print()
    print(title)
    print("=" * 78)

    print_header()

    for label, strategy in STRATEGIES:
        matches = get_matches(
            rows,
            strategy,
        )

        print_strategy_row(
            label,
            matches,
        )


def print_oos_by_year(testing):
    print()
    print("OUT-OF-SAMPLE BY YEAR")
    print("=" * 78)

    years = sorted(
        {
            row["entry_date"].year
            for row in testing
        }
    )

    for year in years:
        year_rows = [
            row
            for row in testing
            if row["entry_date"].year == year
        ]

        print()
        print(year)
        print_header()

        for label, strategy in STRATEGIES:
            matches = get_matches(
                year_rows,
                strategy,
            )

            print_strategy_row(
                label,
                matches,
            )


def main():
    universe_name = get_universe_name()

    rows = get_events(
        universe_name
    )

    training, testing = split_by_time(
        rows
    )

    print()
    print("EXPERIMENTAL STRATEGY COMPARISON")
    print("=" * 78)
    print("Universe:", universe_name)
    print("Horizon:", HORIZON)
    print("Training through:", TRAIN_END)
    print("Out-of-sample from:", TEST_START)

    print_period(
        "TRAINING",
        training,
    )

    print_period(
        "OUT-OF-SAMPLE",
        testing,
    )

    print_oos_by_year(
        testing
    )


if __name__ == "__main__":
    main()