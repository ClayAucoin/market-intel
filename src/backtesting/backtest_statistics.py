from decimal import Decimal
from statistics import median

from src.backtesting.historical_backtest import (
    BENCHMARK,
    TICKER,
    build_historical_backtest,
)


HORIZONS = [
    "30d",
    "90d",
    "180d",
]


def get_horizon_key(horizon):
    return f"excess_{horizon}"


def get_valid_values(
    results,
    horizon,
):
    key = get_horizon_key(
        horizon
    )

    return [
        row[key]
        for row in results
        if row.get(key) is not None
    ]


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
            str(
                median(values)
            )
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
        (
            Decimal(wins)
            / Decimal(len(values))
        )
        * Decimal("100"),
        2,
    )


def calculate_summary(
    results,
    horizon,
):
    values = get_valid_values(
        results,
        horizon,
    )

    if not values:
        return {
            "sample_size": 0,
            "win_rate": None,
            "average": None,
            "median": None,
            "best": None,
            "worst": None,
        }

    return {
        "sample_size": len(values),

        "win_rate": calculate_win_rate(
            values
        ),

        "average": calculate_average(
            values
        ),

        "median": calculate_median(
            values
        ),

        "best": max(values),

        "worst": min(values),
    }


def filter_complete_signals(
    results,
):
    required = [
        "revenue_yoy",
        "revenue_acceleration",
        "eps_yoy",
        "gross_margin_change",
        "operating_margin_change",
    ]

    return [
        row
        for row in results
        if all(
            row.get(field)
            is not None
            for field in required
        )
    ]


def build_signal_buckets(
    results,
):
    complete = filter_complete_signals(
        results
    )

    return {
        "all_complete": complete,

        "revenue_growth_positive": [
            row
            for row in complete
            if row["revenue_yoy"] > 0
        ],

        "revenue_accelerating": [
            row
            for row in complete
            if (
                row[
                    "revenue_acceleration"
                ]
                > 0
            )
        ],

        "eps_growth_positive": [
            row
            for row in complete
            if row["eps_yoy"] > 0
        ],

        "gross_margin_expanding": [
            row
            for row in complete
            if (
                row[
                    "gross_margin_change"
                ]
                > 0
            )
        ],

        "operating_margin_expanding": [
            row
            for row in complete
            if (
                row[
                    "operating_margin_change"
                ]
                > 0
            )
        ],

        "revenue_and_eps_positive": [
            row
            for row in complete
            if (
                row["revenue_yoy"] > 0
                and row["eps_yoy"] > 0
            )
        ],

        "revenue_accel_and_eps_positive": [
            row
            for row in complete
            if (
                row[
                    "revenue_acceleration"
                ]
                > 0
                and row["eps_yoy"] > 0
            )
        ],

        "revenue_accel_and_op_margin": [
            row
            for row in complete
            if (
                row[
                    "revenue_acceleration"
                ]
                > 0
                and row[
                    "operating_margin_change"
                ]
                > 0
            )
        ],

        "triple_positive": [
            row
            for row in complete
            if (
                row[
                    "revenue_acceleration"
                ]
                > 0
                and row["eps_yoy"] > 0
                and row[
                    "operating_margin_change"
                ]
                > 0
            )
        ],
    }


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_overall_summary(
    results,
):
    print()
    print(
        f"{TICKER} BACKTEST SUMMARY"
    )
    print("=" * 86)

    print(
        f"{'Horizon':<10}"
        f"{'N':>6}"
        f"{'Win Rate':>14}"
        f"{'Avg Excess':>16}"
        f"{'Median':>14}"
        f"{'Best':>14}"
        f"{'Worst':>14}"
    )

    print("-" * 86)

    for horizon in HORIZONS:
        summary = calculate_summary(
            results,
            horizon,
        )

        print(
            f"{horizon:<10}"
            f"{summary['sample_size']:>6}"
            f"{format_percent(
                summary['win_rate']
            ):>14}"
            f"{format_percent(
                summary['average']
            ):>16}"
            f"{format_percent(
                summary['median']
            ):>14}"
            f"{format_percent(
                summary['best']
            ):>14}"
            f"{format_percent(
                summary['worst']
            ):>14}"
        )


def print_bucket_summary(
    results,
):
    buckets = build_signal_buckets(
        results
    )

    print()
    print(
        "SIGNAL BUCKET PERFORMANCE"
    )
    print("=" * 116)

    print(
        f"{'Signal':<34}"
        f"{'30d N':>7}"
        f"{'30d Avg':>12}"
        f"{'30d Win':>12}"
        f"{'90d N':>8}"
        f"{'90d Avg':>12}"
        f"{'90d Win':>12}"
        f"{'180d N':>9}"
        f"{'180d Avg':>13}"
        f"{'180d Win':>12}"
    )

    print("-" * 116)

    for name, rows in buckets.items():
        summaries = {
            horizon: calculate_summary(
                rows,
                horizon,
            )
            for horizon in HORIZONS
        }

        label = (
            name
            .replace("_", " ")
            .title()
        )

        print(
            f"{label:<34}"

            f"{summaries['30d'][
                'sample_size'
            ]:>7}"

            f"{format_percent(
                summaries['30d'][
                    'average'
                ]
            ):>12}"

            f"{format_percent(
                summaries['30d'][
                    'win_rate'
                ]
            ):>12}"

            f"{summaries['90d'][
                'sample_size'
            ]:>8}"

            f"{format_percent(
                summaries['90d'][
                    'average'
                ]
            ):>12}"

            f"{format_percent(
                summaries['90d'][
                    'win_rate'
                ]
            ):>12}"

            f"{summaries['180d'][
                'sample_size'
            ]:>9}"

            f"{format_percent(
                summaries['180d'][
                    'average'
                ]
            ):>13}"

            f"{format_percent(
                summaries['180d'][
                    'win_rate'
                ]
            ):>12}"
        )


if __name__ == "__main__":
    results = build_historical_backtest(
        TICKER,
        BENCHMARK,
    )

    print_overall_summary(
        results
    )

    print_bucket_summary(
        results
    )