from collections import defaultdict
from decimal import Decimal
from math import sqrt
from statistics import median
from datetime import date

from src.database import get_connection


MIN_HISTORY = 4


TRAIN_END = date(
    2023,
    12,
    31,
)

TEST_START = date(
    2024,
    1,
    1,
)

HORIZONS = [
    "30d",
    "90d",
    "180d",
]


SIGNALS = {
    "Revenue Growth":
        "revenue_yoy",

    "Revenue Acceleration":
        "revenue_acceleration",

    "EPS Growth":
        "eps_yoy",

    "Gross Margin":
        "gross_margin_change",

    "Operating Margin":
        "operating_margin_change",
}


def get_events():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.ticker,
                    be.period_end,
                    be.entry_date,

                    be.revenue_yoy,
                    be.revenue_acceleration,
                    be.eps_yoy,
                    be.gross_margin_change,
                    be.operating_margin_change,

                    be.excess_30d,
                    be.excess_90d,
                    be.excess_180d

                FROM backtest_events be

                JOIN securities s
                    ON s.id =
                       be.security_id

                ORDER BY
                    s.ticker,
                    be.entry_date;
                """
            )

            rows = cursor.fetchall()

    return [
        {
            "ticker": row[0],
            "period_end": row[1],
            "entry_date": row[2],

            "revenue_yoy": row[3],
            "revenue_acceleration":
                row[4],
            "eps_yoy": row[5],
            "gross_margin_change":
                row[6],
            "operating_margin_change":
                row[7],

            "excess_30d": row[8],
            "excess_90d": row[9],
            "excess_180d": row[10],
        }
        for row in rows
    ]


def decimal_mean(values):
    if not values:
        return None

    return (
        sum(values)
        / Decimal(len(values))
    )


def decimal_stddev(values):
    if len(values) < 2:
        return None

    mean = decimal_mean(
        values
    )

    variance = (
        sum(
            (
                value - mean
            ) ** 2
            for value in values
        )
        / Decimal(
            len(values) - 1
        )
    )

    return Decimal(
        str(
            sqrt(
                float(variance)
            )
        )
    )


def calculate_z_score(
    value,
    history,
):
    if value is None:
        return None

    if len(history) < MIN_HISTORY:
        return None

    mean = decimal_mean(
        history
    )

    stddev = decimal_stddev(
        history
    )

    if (
        stddev is None
        or stddev == 0
    ):
        return None

    return round(
        (
            value - mean
        )
        / stddev,
        4,
    )


def add_standardized_signals(
    rows,
):
    histories = defaultdict(
        lambda: defaultdict(list)
    )

    result = []

    for row in rows:
        enriched = dict(
            row
        )

        ticker = row[
            "ticker"
        ]

        for field in SIGNALS.values():
            value = row.get(
                field
            )

            prior_values = histories[
                ticker
            ][field]

            enriched[
                f"{field}_z"
            ] = calculate_z_score(
                value,
                prior_values,
            )

        result.append(
            enriched
        )

        #
        # Add current observation only
        # AFTER calculating its z-score.
        #
        # This prevents look-ahead bias.
        #
        for field in SIGNALS.values():
            value = row.get(
                field
            )

            if value is not None:
                histories[
                    ticker
                ][field].append(
                    value
                )

    return result


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
        Decimal(wins)
        / Decimal(len(values))
        * Decimal("100"),
        2,
    )


def calculate_stats(
    rows,
    horizon,
):
    key = (
        f"excess_{horizon}"
    )

    values = [
        row[key]
        for row in rows
        if row.get(key)
        is not None
    ]

    return {
        "n": len(values),

        "average":
            calculate_average(
                values
            ),

        "median":
            calculate_median(
                values
            ),

        "win_rate":
            calculate_win_rate(
                values
            ),
    }


def split_z_score(
    rows,
    field,
    threshold,
):
    z_field = (
        f"{field}_z"
    )

    strong = [
        row
        for row in rows
        if (
            row.get(z_field)
            is not None
            and row[z_field]
            >= threshold
        )
    ]

    weak = [
        row
        for row in rows
        if (
            row.get(z_field)
            is not None
            and row[z_field]
            <= -threshold
        )
    ]

    return strong, weak


def difference(
    first,
    second,
):
    if (
        first is None
        or second is None
    ):
        return None

    return round(
        first - second,
        2,
    )


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_threshold_test(
    rows,
    threshold,
):
    print()
    print(
        f"Z-SCORE THRESHOLD: "
        f"±{threshold}"
    )

    print("=" * 110)

    print(
        f"{'Signal':<24}"
        f"{'Horizon':>9}"
        f"{'N + / -':>13}"
        f"{'Avg Δ':>14}"
        f"{'Median Δ':>14}"
        f"{'Win Δ':>14}"
    )

    print("-" * 110)

    for signal_name, field in (
        SIGNALS.items()
    ):
        strong, weak = split_z_score(
            rows,
            field,
            Decimal(
                str(threshold)
            ),
        )

        for horizon in HORIZONS:
            strong_stats = (
                calculate_stats(
                    strong,
                    horizon,
                )
            )

            weak_stats = (
                calculate_stats(
                    weak,
                    horizon,
                )
            )

            samples = (
                f"{strong_stats['n']}"
                f" / "
                f"{weak_stats['n']}"
            )

            print(
                f"{signal_name:<24}"
                f"{horizon:>9}"
                f"{samples:>13}"

                f"{format_percent(
                    difference(
                        strong_stats[
                            'average'
                        ],
                        weak_stats[
                            'average'
                        ],
                    )
                ):>14}"

                f"{format_percent(
                    difference(
                        strong_stats[
                            'median'
                        ],
                        weak_stats[
                            'median'
                        ],
                    )
                ):>14}"

                f"{format_percent(
                    difference(
                        strong_stats[
                            'win_rate'
                        ],
                        weak_stats[
                            'win_rate'
                        ],
                    )
                ):>14}"
            )


def split_by_time(rows):
    training = [
        row
        for row in rows
        if row["entry_date"]
        <= TRAIN_END
    ]

    testing = [
        row
        for row in rows
        if row["entry_date"]
        >= TEST_START
    ]

    return training, testing


def main():
    rows = get_events()

    rows = add_standardized_signals(
        rows
    )

    training, testing = split_by_time(
        rows
    )

    print()
    print(
        "COMPANY-STANDARDIZED "
        "TIME-SPLIT SIGNAL TEST"
    )

    print(
        "Events:",
        len(rows),
    )

    print(
        "Minimum prior observations:",
        MIN_HISTORY,
    )

    print(
        "Training through:",
        TRAIN_END,
    )

    print(
        "Testing from:",
        TEST_START,
    )

    periods = [
        (
            "TRAINING PERIOD",
            training,
        ),
        (
            "OUT-OF-SAMPLE TEST PERIOD",
            testing,
        ),
    ]

    for period_name, period_rows in periods:
        print()
        print()
        print(period_name)
        print("#" * 110)

        print(
            "Events:",
            len(period_rows),
        )

        usable = sum(
            1
            for row in period_rows
            if row.get(
                "revenue_acceleration_z"
            ) is not None
        )

        print(
            "Events with standardized "
            "revenue acceleration:",
            usable,
        )

        for threshold in [
            0.5,
            1.0,
        ]:
            print_threshold_test(
                period_rows,
                threshold,
            )


if __name__ == "__main__":
    main()