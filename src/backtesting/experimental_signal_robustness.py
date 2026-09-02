import sys

from collections import defaultdict
from decimal import Decimal
from statistics import median

from src.analysis.experimental_signal import (
    HORIZON,
    SIGNAL_DESCRIPTION,
    get_experimental_signal_events,
)
from src.backtesting.time_split_statistics import (
    DEFAULT_UNIVERSE,
    TRAIN_END,
    TEST_START,
    get_events,
    split_by_time,
)


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


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


def calculate_trimmed_average(
    values,
    trim_fraction=Decimal("0.10"),
):
    if not values:
        return None

    ordered = sorted(values)

    trim_count = int(
        Decimal(len(ordered))
        * trim_fraction
    )

    if (
        trim_count == 0
        or trim_count * 2 >= len(ordered)
    ):
        return calculate_average(
            ordered
        )

    trimmed = ordered[
        trim_count:
        len(ordered) - trim_count
    ]

    return calculate_average(
        trimmed
    )


def calculate_win_rate(values):
    if not values:
        return None

    winners = sum(
        1
        for value in values
        if value > 0
    )

    return (
        Decimal(winners)
        / Decimal(len(values))
        * Decimal("100")
    )


def get_excess_values(rows):
    key = f"excess_{HORIZON}"

    return [
        row[key]
        for row in rows
        if row.get(key) is not None
    ]


def calculate_stats(rows):
    values = get_excess_values(
        rows
    )

    if not values:
        return {
            "n": 0,
            "average": None,
            "median": None,
            "trimmed_average": None,
            "win_rate": None,
            "minimum": None,
            "maximum": None,
        }

    return {
        "n":
            len(values),

        "average":
            calculate_average(values),

        "median":
            calculate_median(values),

        "trimmed_average":
            calculate_trimmed_average(
                values
            ),

        "win_rate":
            calculate_win_rate(
                values
            ),

        "minimum":
            min(values),

        "maximum":
            max(values),
    }


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_stats(
    label,
    rows,
):
    stats = calculate_stats(
        rows
    )

    print(
        f"{label:<28}"
        f"{stats['n']:>8}"
        f"{format_percent(stats['average']):>14}"
        f"{format_percent(stats['median']):>14}"
        f"{format_percent(stats['trimmed_average']):>14}"
        f"{format_percent(stats['win_rate']):>14}"
        f"{format_percent(stats['minimum']):>14}"
        f"{format_percent(stats['maximum']):>14}"
    )


def print_period_summary(
    training_matches,
    testing_matches,
):
    print()
    print(
        "EXACT SIGNAL RESULTS"
    )

    print("=" * 120)

    print(
        f"{'Period':<28}"
        f"{'N':>8}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'10% Trim':>14}"
        f"{'Win Rate':>14}"
        f"{'Worst':>14}"
        f"{'Best':>14}"
    )

    print("-" * 120)

    print_stats(
        "Development / Training",
        training_matches,
    )

    print_stats(
        "Out-of-Sample",
        testing_matches,
    )


def group_by_year(rows):
    groups = defaultdict(list)

    for row in rows:
        groups[
            row["entry_date"].year
        ].append(
            row
        )

    return groups


def print_yearly_results(
    rows,
):
    print()
    print(
        "OUT-OF-SAMPLE YEAR-BY-YEAR"
    )

    print("=" * 120)

    print(
        f"{'Year':<28}"
        f"{'N':>8}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'10% Trim':>14}"
        f"{'Win Rate':>14}"
        f"{'Worst':>14}"
        f"{'Best':>14}"
    )

    print("-" * 120)

    groups = group_by_year(
        rows
    )

    for year in sorted(groups):
        print_stats(
            str(year),
            groups[year],
        )


def group_by_sector(rows):
    groups = defaultdict(list)

    for row in rows:
        sector = (
            row.get("sector")
            or "UNKNOWN"
        )

        groups[
            sector
        ].append(
            row
        )

    return groups


def print_sector_results(
    rows,
):
    print()
    print(
        "OUT-OF-SAMPLE SECTOR ROBUSTNESS"
    )

    print("=" * 120)

    print(
        f"{'Sector':<28}"
        f"{'N':>8}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'10% Trim':>14}"
        f"{'Win Rate':>14}"
        f"{'Worst':>14}"
        f"{'Best':>14}"
    )

    print("-" * 120)

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
        print_stats(
            sector,
            sector_rows,
        )


def group_by_ticker(rows):
    groups = defaultdict(list)

    for row in rows:
        groups[
            row["ticker"]
        ].append(
            row
        )

    return groups


def print_company_concentration(
    rows,
):
    print()
    print(
        "OUT-OF-SAMPLE COMPANY CONCENTRATION"
    )

    print("=" * 80)

    groups = group_by_ticker(
        rows
    )

    ordered = sorted(
        groups.items(),
        key=lambda item: (
            -len(item[1]),
            item[0],
        ),
    )

    total = len(rows)

    unique_companies = len(
        groups
    )

    print(
        "Signal events:",
        total,
    )

    print(
        "Unique companies:",
        unique_companies,
    )

    print()

    print(
        f"{'Ticker':<12}"
        f"{'Events':>10}"
        f"{'% of Signals':>16}"
    )

    print("-" * 40)

    for ticker, ticker_rows in ordered[:20]:
        count = len(
            ticker_rows
        )

        share = (
            Decimal(count)
            / Decimal(total)
            * Decimal("100")
            if total
            else Decimal("0")
        )

        print(
            f"{ticker:<12}"
            f"{count:>10}"
            f"{format_percent(share):>16}"
        )


def print_removed_winner_test(
    rows,
):
    values = get_excess_values(
        rows
    )

    print()
    print(
        "OUT-OF-SAMPLE BIG-WINNER DEPENDENCE"
    )

    print("=" * 82)

    print(
        "Removes the strongest individual "
        "30-day excess-return outcomes."
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

    for remove_count in [
        0,
        1,
        2,
        3,
        5,
        10,
    ]:
        if remove_count >= len(
            values
        ):
            continue

        ordered = sorted(
            values,
            reverse=True,
        )

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
            f"{format_percent(
                calculate_average(
                    remaining
                )
            ):>14}"
            f"{format_percent(
                calculate_median(
                    remaining
                )
            ):>14}"
            f"{format_percent(
                calculate_win_rate(
                    remaining
                )
            ):>14}"
        )


def print_signal_details(
    rows,
):
    print()
    print(
        "OUT-OF-SAMPLE SIGNAL EVENTS"
    )

    print("=" * 128)

    print(
        f"{'Ticker':<8}"
        f"{'Sector':<25}"
        f"{'Entry Date':>12}"
        f"{'Rev Accel':>14}"
        f"{'Op Margin':>14}"
        f"{'Pre Excess':>14}"
        f"{'30d Excess':>14}"
    )

    print("-" * 128)

    ordered = sorted(
        rows,
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        ),
    )

    for row in ordered:
        print(
            f"{row['ticker']:<8}"
            f"{(row.get('sector') or 'UNKNOWN'):<25}"
            f"{str(row['entry_date']):>12}"
            f"{format_percent(
                row.get(
                    'revenue_acceleration'
                )
            ):>14}"
            f"{format_percent(
                row.get(
                    'operating_margin_change'
                )
            ):>14}"
            f"{format_percent(
                row.get(
                    'pre_excess_20d'
                )
            ):>14}"
            f"{format_percent(
                row.get(
                    f'excess_{HORIZON}'
                )
            ):>14}"
        )


def main():
    universe_name = (
        get_universe_name()
    )

    rows = get_events(
        universe_name
    )

    training, testing = split_by_time(
        rows
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
        "EXPERIMENTAL SIGNAL ROBUSTNESS TEST"
    )

    print("=" * 120)

    print(
        "Universe:",
        universe_name,
    )

    print(
        "Signal:",
        SIGNAL_DESCRIPTION,
    )

    print(
        "Evaluation horizon:",
        HORIZON,
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
        "Total backtest events:",
        len(rows),
    )

    print(
        "Training signal matches:",
        len(training_matches),
    )

    print(
        "Out-of-sample signal matches:",
        len(testing_matches),
    )

    print_period_summary(
        training_matches,
        testing_matches,
    )

    print_yearly_results(
        testing_matches
    )

    print_sector_results(
        testing_matches
    )

    print_company_concentration(
        testing_matches
    )

    print_removed_winner_test(
        testing_matches
    )

    print_signal_details(
        testing_matches
    )


if __name__ == "__main__":
    main()