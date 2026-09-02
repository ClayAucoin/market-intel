import sys

from collections import defaultdict
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


def get_30d_45d_changes(rows):
    changes = []

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

        changes.append(
            round(
                excess_45d - excess_30d,
                2,
            )
        )

    return changes


def calculate_horizon_results(rows):
    results = {}

    for name, days in EXIT_HORIZONS.items():
        values = get_horizon_values(
            rows,
            days,
        )

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
    print("=" * 72)

    print(
        f"{'Exit':<10}"
        f"{'N':>8}"
        f"{'Avg Excess':>18}"
        f"{'Median':>18}"
        f"{'Win Rate':>18}"
    )

    print("-" * 72)

    for name in EXIT_HORIZONS:
        stats = results[name]

        print(
            f"{name:<10}"
            f"{stats['n']:>8}"
            f"{format_number(stats['average']):>18}"
            f"{format_number(stats['median']):>18}"
            f"{format_win_rate(stats['win_rate']):>18}"
        )


def print_removed_winner_test(
    rows,
    horizon_name,
    days,
):
    values = get_horizon_values(
        rows,
        days,
    )

    print()
    print(
        f"OUT-OF-SAMPLE BIG-WINNER DEPENDENCE: "
        f"{horizon_name}"
    )
    print("=" * 82)

    print(
        f"Removes the strongest individual "
        f"{horizon_name} excess-return outcomes."
    )

    print()

    print(
        f"{'Test':<26}"
        f"{'N':>8}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
    )

    print("-" * 82)

    ordered = sorted(
        values,
        reverse=True,
    )

    for remove_count in [
        0,
        1,
        2,
        3,
        5,
        10,
    ]:
        if remove_count >= len(
            ordered
        ):
            continue

        remaining = (
            ordered[remove_count:]
            if remove_count
            else ordered
        )

        label = (
            "Original"
            if remove_count == 0
            else f"Remove top {remove_count}"
        )

        print(
            f"{label:<26}"
            f"{len(remaining):>8}"
            f"{format_number(
                calculate_average(
                    remaining
                )
            ):>14}"
            f"{format_number(
                calculate_median(
                    remaining
                )
            ):>14}"
            f"{format_win_rate(
                calculate_win_rate(
                    remaining
                )
            ):>14}"
        )


def group_by_year(rows):
    groups = defaultdict(list)

    for row in rows:
        groups[
            row["entry_date"].year
        ].append(row)

    return groups


def group_by_sector(rows):
    groups = defaultdict(list)

    for row in rows:
        sector = (
            row.get("sector")
            or "UNKNOWN"
        )

        groups[sector].append(row)

    return groups


def print_yearly_horizon_comparison(
    rows,
):
    print()
    print(
        "OUT-OF-SAMPLE YEAR-BY-YEAR EXIT COMPARISON"
    )
    print("=" * 112)

    print(
        f"{'Year':<8}"
        f"{'Exit':<10}"
        f"{'N':>8}"
        f"{'Avg Excess':>18}"
        f"{'Median':>18}"
        f"{'Win Rate':>18}"
    )

    print("-" * 112)

    groups = group_by_year(
        rows
    )

    for year in sorted(groups):
        year_rows = groups[year]

        for horizon_name in [
            "30d",
            "45d",
            "60d",
            "90d",
        ]:
            days = EXIT_HORIZONS[
                horizon_name
            ]

            values = get_horizon_values(
                year_rows,
                days,
            )

            print(
                f"{year:<8}"
                f"{horizon_name:<10}"
                f"{len(values):>8}"
                f"{format_number(
                    calculate_average(
                        values
                    )
                ):>18}"
                f"{format_number(
                    calculate_median(
                        values
                    )
                ):>18}"
                f"{format_win_rate(
                    calculate_win_rate(
                        values
                    )
                ):>18}"
            )

        print("-" * 112)


def print_change_summary(
    title,
    rows,
):
    changes = get_30d_45d_changes(
        rows
    )

    print()
    print(title)
    print("=" * 88)

    improved = sum(
        1
        for value in changes
        if value > 0
    )

    worsened = sum(
        1
        for value in changes
        if value < 0
    )

    unchanged = sum(
        1
        for value in changes
        if value == 0
    )

    improvement_rate = None

    if changes:
        improvement_rate = round(
            (
                Decimal(improved)
                / Decimal(len(changes))
            )
            * Decimal("100"),
            2,
        )

    print(
        f"{'N':<24}{len(changes)}"
    )

    print(
        f"{'Average change':<24}"
        f"{format_number(
            calculate_average(
                changes
            )
        )}"
    )

    print(
        f"{'Median change':<24}"
        f"{format_number(
            calculate_median(
                changes
            )
        )}"
    )

    print(
        f"{'Improved':<24}{improved}"
    )

    print(
        f"{'Worsened':<24}{worsened}"
    )

    print(
        f"{'Unchanged':<24}{unchanged}"
    )

    print(
        f"{'Improvement rate':<24}"
        f"{format_win_rate(
            improvement_rate
        )}"
    )


def print_sector_30d_vs_45d(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 122)

    print(
        f"{'Sector':<28}"
        f"{'N':>6}"
        f"{'30d Avg':>14}"
        f"{'45d Avg':>14}"
        f"{'Change':>14}"
        f"{'Median Δ':>14}"
        f"{'Improved':>14}"
    )

    print("-" * 122)

    groups = group_by_sector(
        rows
    )

    ordered = sorted(
        groups.items(),
        key=lambda item: (
            -len(item[1]),
            item[0],
        ),
    )

    for sector, sector_rows in ordered:
        values_30d = []
        values_45d = []
        changes = []

        for row in sector_rows:
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

            values_30d.append(
                excess_30d
            )

            values_45d.append(
                excess_45d
            )

            changes.append(
                round(
                    excess_45d
                    - excess_30d,
                    2,
                )
            )

        if not changes:
            continue

        improved = sum(
            1
            for value in changes
            if value > 0
        )

        improvement_rate = round(
            (
                Decimal(improved)
                / Decimal(len(changes))
            )
            * Decimal("100"),
            2,
        )

        average_30d = calculate_average(
            values_30d
        )

        average_45d = calculate_average(
            values_45d
        )

        average_change = round(
            average_45d
            - average_30d,
            2,
        )

        print(
            f"{sector:<28}"
            f"{len(changes):>6}"
            f"{format_number(
                average_30d
            ):>14}"
            f"{format_number(
                average_45d
            ):>14}"
            f"{format_number(
                average_change
            ):>14}"
            f"{format_number(
                calculate_median(
                    changes
                )
            ):>14}"
            f"{format_win_rate(
                improvement_rate
            ):>14}"
        )


def print_30d_vs_45d_details(
    rows,
):
    comparisons = []

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

        change = round(
            excess_45d - excess_30d,
            2,
        )

        comparisons.append(
            {
                "ticker": row["ticker"],
                "entry_date": row["entry_date"],
                "excess_30d": excess_30d,
                "excess_45d": excess_45d,
                "change": change,
            }
        )

    comparisons.sort(
        key=lambda item: item["change"],
        reverse=True,
    )

    print()
    print(
        "OUT-OF-SAMPLE 30d VS 45d INDIVIDUAL TRADES"
    )
    print("=" * 82)

    print(
        f"{'Ticker':<10}"
        f"{'Entry Date':<14}"
        f"{'30d':>14}"
        f"{'45d':>14}"
        f"{'Change':>14}"
    )

    print("-" * 82)

    for item in comparisons:
        print(
            f"{item['ticker']:<10}"
            f"{str(item['entry_date']):<14}"
            f"{format_number(
                item['excess_30d']
            ):>14}"
            f"{format_number(
                item['excess_45d']
            ):>14}"
            f"{format_number(
                item['change']
            ):>14}"
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

    print_change_summary(
        "TRAINING 30d TO 45d CHANGE",
        training,
    )

    print_change_summary(
        "OUT-OF-SAMPLE 30d TO 45d CHANGE",
        testing,
    )

    print_sector_30d_vs_45d(
        "TRAINING 30d VS 45d BY SECTOR",
        training,
    )

    print_sector_30d_vs_45d(
        "OUT-OF-SAMPLE 30d VS 45d BY SECTOR",
        testing,
    )

    print_yearly_horizon_comparison(
        testing
    )

    print_removed_winner_test(
        testing,
        "30d",
        30,
    )

    print_removed_winner_test(
        testing,
        "45d",
        45,
    )

    print_removed_winner_test(
        testing,
        "60d",
        60,
    )

    print_removed_winner_test(
        testing,
        "90d",
        90,
    )

    print_30d_vs_45d_details(
        testing
    )

    print()
    print(
        "Exit dates use the first trading day's "
        "adjusted close on or after each calendar-day target."
    )
    print()


if __name__ == "__main__":
    main()