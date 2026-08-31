import sys

from datetime import date
from decimal import Decimal
from statistics import median


from src.database import get_connection
from src.time_split_statistics import DEFAULT_UNIVERSE


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


MARKET_SIGNALS = {
    "Pre Return 20d":
        "pre_return_20d",

    "Pre Return 60d":
        "pre_return_60d",

    "Pre Excess 20d":
        "pre_excess_20d",

    "Pre Excess 60d":
        "pre_excess_60d",

    "Volatility 20d":
        "pre_volatility_20d",

    "Opening Gap":
        "opening_gap_pct",

    "Opening Gap Excess":
        "opening_gap_excess",
}


def get_events(
    universe_name=DEFAULT_UNIVERSE,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.ticker,
                    be.entry_date,

                    be.pre_return_20d,
                    be.pre_return_60d,

                    be.pre_excess_20d,
                    be.pre_excess_60d,

                    be.pre_volatility_20d,

                    be.opening_gap_pct,
                    be.opening_gap_excess,

                    be.excess_30d,
                    be.excess_90d,
                    be.excess_180d

                FROM backtest_events be

                JOIN securities s
                    ON s.id =
                       be.security_id

                JOIN analysis_universe_members aum
                    ON aum.security_id =
                       be.security_id

                JOIN analysis_universes au
                    ON au.id =
                       aum.universe_id

                WHERE au.name = %s

                ORDER BY
                    be.entry_date,
                    s.ticker;
                """,
                (universe_name,),
            )

            rows = cursor.fetchall()

    return [
        {
            "ticker": row[0],
            "entry_date": row[1],

            "pre_return_20d": row[2],
            "pre_return_60d": row[3],

            "pre_excess_20d": row[4],
            "pre_excess_60d": row[5],

            "pre_volatility_20d": row[6],

            "opening_gap_pct": row[7],
            "opening_gap_excess": row[8],

            "excess_30d": row[9],
            "excess_90d": row[10],
            "excess_180d": row[11],
        }
        for row in rows
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


def calculate_stats(
    rows,
    horizon,
):
    field = (
        f"excess_{horizon}"
    )

    values = [
        row[field]
        for row in rows
        if row.get(field)
        is not None
    ]

    return {
        "n":
            len(values),

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


def split_positive_negative(
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

    return (
        positive,
        negative,
    )


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


def format_value(value):
    if value is None:
        return "-"

    return (
        f"{value:+.2f}%"
    )


def print_signal_table(
    title,
    rows,
):
    print()
    print(title)

    print("=" * 112)

    print(
        f"{'Signal':<24}"
        f"{'Horizon':>9}"
        f"{'N + / -':>13}"
        f"{'Avg Δ':>14}"
        f"{'Median Δ':>14}"
        f"{'Win Δ':>14}"
    )

    print("-" * 112)

    for signal_name, field in (
        MARKET_SIGNALS.items()
    ):
        positive, negative = (
            split_positive_negative(
                rows,
                field,
            )
        )

        for horizon in HORIZONS:
            positive_stats = (
                calculate_stats(
                    positive,
                    horizon,
                )
            )

            negative_stats = (
                calculate_stats(
                    negative,
                    horizon,
                )
            )

            sample_text = (
                f"{positive_stats['n']}"
                f" / "
                f"{negative_stats['n']}"
            )

            print(
                f"{signal_name:<24}"
                f"{horizon:>9}"
                f"{sample_text:>13}"

                f"{format_value(
                    difference(
                        positive_stats[
                            'average'
                        ],
                        negative_stats[
                            'average'
                        ],
                    )
                ):>14}"

                f"{format_value(
                    difference(
                        positive_stats[
                            'median'
                        ],
                        negative_stats[
                            'median'
                        ],
                    )
                ):>14}"

                f"{format_value(
                    difference(
                        positive_stats[
                            'win_rate'
                        ],
                        negative_stats[
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

    return (
        training,
        testing,
    )


def print_gap_buckets(
    rows,
    horizon,
):
    buckets = {
        "< -5%": [],
        "-5% to -2%": [],
        "-2% to 0%": [],
        "0% to +2%": [],
        "+2% to +5%": [],
        "> +5%": [],
    }

    for row in rows:
        gap = row.get(
            "opening_gap_excess"
        )

        if gap is None:
            continue

        if gap < -5:
            bucket = "< -5%"

        elif gap < -2:
            bucket = "-5% to -2%"

        elif gap < 0:
            bucket = "-2% to 0%"

        elif gap < 2:
            bucket = "0% to +2%"

        elif gap < 5:
            bucket = "+2% to +5%"

        else:
            bucket = "> +5%"

        buckets[
            bucket
        ].append(
            row
        )

    print()
    print(
        f"OPENING GAP EXCESS BUCKETS "
        f"({horizon})"
    )

    print("=" * 80)

    print(
        f"{'Gap Bucket':<18}"
        f"{'N':>8}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
    )

    print("-" * 80)

    for bucket_name, bucket_rows in (
        buckets.items()
    ):
        stats = calculate_stats(
            bucket_rows,
            horizon,
        )

        print(
            f"{bucket_name:<18}"
            f"{stats['n']:>8}"
            f"{format_value(
                stats['average']
            ):>14}"
            f"{format_value(
                stats['median']
            ):>14}"
            f"{format_value(
                stats['win_rate']
            ):>14}"
        )


def main():
    universe_name = (
        sys.argv[1]
        if len(sys.argv) >= 2
        else DEFAULT_UNIVERSE
    )

    rows = get_events(
        universe_name
    )

    training, testing = (
        split_by_time(
            rows
        )
    )

    print()
    print(
        "MARKET CONTEXT "
        "SIGNAL VALIDATION"
    )

    print(
        "Events:",
        len(rows),
    )

    print(
        "Training through:",
        TRAIN_END,
    )

    print(
        "Testing from:",
        TEST_START,
    )

    print_signal_table(
        "TRAINING PERIOD",
        training,
    )

    print_signal_table(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )

    #
    # Gap buckets are especially useful
    # because market reaction may not be
    # linear around zero.
    #
    for horizon in HORIZONS:
        print_gap_buckets(
            testing,
            horizon,
        )


if __name__ == "__main__":
    main()