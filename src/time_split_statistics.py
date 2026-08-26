from decimal import Decimal
from statistics import median
from datetime import date

from src.database import get_connection


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
                    be.entry_date,
                    s.ticker;
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


def get_stats(
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


def split_signal(
    rows,
    field,
):
    positive = [
        row
        for row in rows
        if (
            row.get(field)
            is not None
            and row[field] > 0
        )
    ]

    negative = [
        row
        for row in rows
        if (
            row.get(field)
            is not None
            and row[field] < 0
        )
    ]

    return positive, negative


def calculate_difference(
    rows,
    field,
    horizon,
):
    positive, negative = (
        split_signal(
            rows,
            field,
        )
    )

    positive_stats = get_stats(
        positive,
        horizon,
    )

    negative_stats = get_stats(
        negative,
        horizon,
    )

    def difference(
        positive_value,
        negative_value,
    ):
        if (
            positive_value is None
            or negative_value is None
        ):
            return None

        return round(
            positive_value
            - negative_value,
            2,
        )

    return {
        "positive_n":
            positive_stats["n"],

        "negative_n":
            negative_stats["n"],

        "average_diff":
            difference(
                positive_stats[
                    "average"
                ],
                negative_stats[
                    "average"
                ],
            ),

        "median_diff":
            difference(
                positive_stats[
                    "median"
                ],
                negative_stats[
                    "median"
                ],
            ),

        "win_diff":
            difference(
                positive_stats[
                    "win_rate"
                ],
                negative_stats[
                    "win_rate"
                ],
            ),
    }


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_period(
    name,
    rows,
):
    print()
    print(
        name
    )

    print("=" * 105)

    print(
        "Events:",
        len(rows),
    )

    print()

    print(
        f"{'Signal':<24}"
        f"{'Horizon':>9}"
        f"{'N + / -':>13}"
        f"{'Avg Δ':>14}"
        f"{'Median Δ':>14}"
        f"{'Win Δ':>14}"
    )

    print("-" * 105)

    for signal_name, field in (
        SIGNALS.items()
    ):
        for horizon in HORIZONS:
            result = (
                calculate_difference(
                    rows,
                    field,
                    horizon,
                )
            )

            samples = (
                f"{result['positive_n']}"
                f" / "
                f"{result['negative_n']}"
            )

            print(
                f"{signal_name:<24}"
                f"{horizon:>9}"
                f"{samples:>13}"

                f"{format_percent(
                    result[
                        'average_diff'
                    ]
                ):>14}"

                f"{format_percent(
                    result[
                        'median_diff'
                    ]
                ):>14}"

                f"{format_percent(
                    result[
                        'win_diff'
                    ]
                ):>14}"
            )


def main():
    rows = get_events()

    training, testing = (
        split_by_time(
            rows
        )
    )

    print()
    print(
        "TIME-SPLIT SIGNAL TEST"
    )

    print(
        "Training through:",
        TRAIN_END,
    )

    print(
        "Testing from:",
        TEST_START,
    )

    print_period(
        "TRAINING PERIOD",
        training,
    )

    print_period(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )


if __name__ == "__main__":
    main()