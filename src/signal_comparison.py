from decimal import Decimal
from statistics import median

from src.historical_backtest import (
    BENCHMARK,
    TICKER,
    build_historical_backtest,
)


HORIZONS = [
    "30d",
    "90d",
    "180d",
]


SIGNALS = {
    "Revenue Growth": "revenue_yoy",
    "Revenue Acceleration": "revenue_acceleration",
    "EPS Growth": "eps_yoy",
    "Gross Margin": "gross_margin_change",
    "Operating Margin": "operating_margin_change",
}


def get_excess_key(horizon):
    return f"excess_{horizon}"


def calculate_average(values):
    if not values:
        return None

    return round(
        sum(values)
        / Decimal(len(values)),
        2,
    )


def calculate_median(values):
    if not values:
        return None

    return round(
        Decimal(
            str(median(values))
        ),
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
        Decimal(wins)
        / Decimal(len(values))
        * Decimal("100"),
        2,
    )


def calculate_statistics(
    rows,
    horizon,
):
    key = get_excess_key(
        horizon
    )

    values = [
        row[key]
        for row in rows
        if row.get(key) is not None
    ]

    if not values:
        return {
            "n": 0,
            "average": None,
            "median": None,
            "win_rate": None,
        }

    return {
        "n": len(values),

        "average":
            calculate_average(values),

        "median":
            calculate_median(values),

        "win_rate":
            calculate_win_rate(values),
    }


def split_signal(
    results,
    field,
):
    positive = []
    negative = []
    zero = []

    for row in results:
        value = row.get(field)

        if value is None:
            continue

        if value > 0:
            positive.append(row)

        elif value < 0:
            negative.append(row)

        else:
            zero.append(row)

    return {
        "positive": positive,
        "negative": negative,
        "zero": zero,
    }


def get_labels(signal_name):
    labels = {
        "Revenue Growth": (
            "Revenue Growing",
            "Revenue Declining",
        ),

        "Revenue Acceleration": (
            "Revenue Accelerating",
            "Revenue Decelerating",
        ),

        "EPS Growth": (
            "EPS Growing",
            "EPS Declining",
        ),

        "Gross Margin": (
            "Gross Margin Expanding",
            "Gross Margin Contracting",
        ),

        "Operating Margin": (
            "Operating Margin Expanding",
            "Operating Margin Contracting",
        ),
    }

    return labels[signal_name]


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_horizon_header(horizon):
    print()
    print(
        f"{horizon.upper()} EXCESS RETURN"
    )

    print("-" * 94)

    print(
        f"{'Condition':<30}"
        f"{'N':>6}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
    )

    print("-" * 94)


def print_signal_comparison(
    results,
):
    print()

    print(
        f"{TICKER} SIGNAL COMPARISON"
    )

    print("=" * 94)

    for horizon in HORIZONS:
        print_horizon_header(
            horizon
        )

        for signal_name, field in SIGNALS.items():
            groups = split_signal(
                results,
                field,
            )

            positive_label, negative_label = (
                get_labels(
                    signal_name
                )
            )

            positive_stats = (
                calculate_statistics(
                    groups["positive"],
                    horizon,
                )
            )

            negative_stats = (
                calculate_statistics(
                    groups["negative"],
                    horizon,
                )
            )

            print(
                f"{positive_label:<30}"

                f"{positive_stats['n']:>6}"

                f"{format_percent(
                    positive_stats[
                        'average'
                    ]
                ):>14}"

                f"{format_percent(
                    positive_stats[
                        'median'
                    ]
                ):>14}"

                f"{format_percent(
                    positive_stats[
                        'win_rate'
                    ]
                ):>14}"
            )

            print(
                f"{negative_label:<30}"

                f"{negative_stats['n']:>6}"

                f"{format_percent(
                    negative_stats[
                        'average'
                    ]
                ):>14}"

                f"{format_percent(
                    negative_stats[
                        'median'
                    ]
                ):>14}"

                f"{format_percent(
                    negative_stats[
                        'win_rate'
                    ]
                ):>14}"
            )

            print()


def print_signal_differences(
    results,
):
    print()

    print(
        "POSITIVE VS NEGATIVE DIFFERENCE"
    )

    print("=" * 100)

    print(
        f"{'Signal':<24}"
        f"{'Horizon':>10}"
        f"{'Avg Δ':>14}"
        f"{'Median Δ':>14}"
        f"{'Win Rate Δ':>16}"
        f"{'N + / -':>14}"
    )

    print("-" * 100)

    for signal_name, field in SIGNALS.items():
        groups = split_signal(
            results,
            field,
        )

        for horizon in HORIZONS:
            positive = (
                calculate_statistics(
                    groups["positive"],
                    horizon,
                )
            )

            negative = (
                calculate_statistics(
                    groups["negative"],
                    horizon,
                )
            )

            if (
                positive["average"] is None
                or negative["average"] is None
            ):
                average_difference = None

            else:
                average_difference = round(
                    positive["average"]
                    - negative["average"],
                    2,
                )

            if (
                positive["median"] is None
                or negative["median"] is None
            ):
                median_difference = None

            else:
                median_difference = round(
                    positive["median"]
                    - negative["median"],
                    2,
                )

            if (
                positive["win_rate"] is None
                or negative["win_rate"] is None
            ):
                win_difference = None

            else:
                win_difference = round(
                    positive["win_rate"]
                    - negative["win_rate"],
                    2,
                )

            sample_text = (
                f"{positive['n']} / "
                f"{negative['n']}"
            )

            print(
                f"{signal_name:<24}"

                f"{horizon:>10}"

                f"{format_percent(
                    average_difference
                ):>14}"

                f"{format_percent(
                    median_difference
                ):>14}"

                f"{format_percent(
                    win_difference
                ):>16}"

                f"{sample_text:>14}"
            )


if __name__ == "__main__":
    results = build_historical_backtest(
        TICKER,
        BENCHMARK,
    )

    print_signal_comparison(
        results
    )

    print_signal_differences(
        results
    )