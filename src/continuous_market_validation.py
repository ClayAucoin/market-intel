import sys

from collections import defaultdict
from datetime import date
from decimal import Decimal
from math import sqrt


from src.database import get_connection
from src.time_split_statistics import DEFAULT_UNIVERSE


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
                    s.ticker,
                    be.entry_date;
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


def mean(values):
    if not values:
        return None

    return (
        sum(values)
        / Decimal(len(values))
    )


def stddev(values):
    if len(values) < 2:
        return None

    average = mean(
        values
    )

    variance = (
        sum(
            (
                value - average
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

    average = mean(
        history
    )

    deviation = stddev(
        history
    )

    if (
        deviation is None
        or deviation == 0
    ):
        return None

    return (
        value - average
    ) / deviation


def add_company_z_scores(
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

        for field in (
            MARKET_SIGNALS.values()
        ):
            value = row.get(
                field
            )

            history = histories[
                ticker
            ][field]

            enriched[
                f"{field}_z"
            ] = calculate_z_score(
                value,
                history,
            )

        result.append(
            enriched
        )

        #
        # Important:
        # current observation is added only
        # after its z-score is calculated.
        #
        for field in (
            MARKET_SIGNALS.values()
        ):
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


def calculate_pearson(
    pairs,
):
    if len(pairs) < 3:
        return None

    x_values = [
        pair[0]
        for pair in pairs
    ]

    y_values = [
        pair[1]
        for pair in pairs
    ]

    x_mean = mean(
        x_values
    )

    y_mean = mean(
        y_values
    )

    numerator = sum(
        (
            x - x_mean
        )
        *
        (
            y - y_mean
        )
        for x, y in pairs
    )

    x_sum = sum(
        (
            x - x_mean
        ) ** 2
        for x in x_values
    )

    y_sum = sum(
        (
            y - y_mean
        ) ** 2
        for y in y_values
    )

    denominator = (
        Decimal(
            str(
                sqrt(
                    float(x_sum)
                )
            )
        )
        *
        Decimal(
            str(
                sqrt(
                    float(y_sum)
                )
            )
        )
    )

    if denominator == 0:
        return None

    return (
        numerator
        / denominator
    )


def rank_values(values):
    indexed = sorted(
        enumerate(values),
        key=lambda item:
            item[1],
    )

    ranks = [
        None
        for _ in values
    ]

    position = 0

    while position < len(indexed):
        end = position

        while (
            end + 1 < len(indexed)
            and indexed[
                end + 1
            ][1]
            == indexed[position][1]
        ):
            end += 1

        average_rank = Decimal(
            str(
                (
                    position
                    + end
                    + 2
                )
                / 2
            )
        )

        for index in range(
            position,
            end + 1,
        ):
            original_index = (
                indexed[index][0]
            )

            ranks[
                original_index
            ] = average_rank

        position = end + 1

    return ranks


def calculate_spearman(
    pairs,
):
    if len(pairs) < 3:
        return None

    x_values = [
        pair[0]
        for pair in pairs
    ]

    y_values = [
        pair[1]
        for pair in pairs
    ]

    x_ranks = rank_values(
        x_values
    )

    y_ranks = rank_values(
        y_values
    )

    return calculate_pearson(
        list(
            zip(
                x_ranks,
                y_ranks,
            )
        )
    )


def get_pairs(
    rows,
    field,
    horizon,
    standardized=False,
):
    signal_field = field

    if standardized:
        signal_field = (
            f"{field}_z"
        )

    return [
        (
            row[signal_field],
            row[
                f"excess_{horizon}"
            ],
        )
        for row in rows
        if (
            row.get(
                signal_field
            ) is not None
            and row.get(
                f"excess_{horizon}"
            ) is not None
        )
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

    return (
        training,
        testing,
    )


def format_correlation(value):
    if value is None:
        return "-"

    return f"{value:+.3f}"


def print_period(
    title,
    rows,
    standardized,
):
    mode = (
        "COMPANY-STANDARDIZED"
        if standardized
        else "RAW"
    )

    print()
    print(
        f"{title} - {mode}"
    )

    print("=" * 94)

    print(
        f"{'Signal':<24}"
        f"{'Horizon':>10}"
        f"{'N':>8}"
        f"{'Pearson':>14}"
        f"{'Spearman':>14}"
    )

    print("-" * 94)

    for signal_name, field in (
        MARKET_SIGNALS.items()
    ):
        for horizon in HORIZONS:
            pairs = get_pairs(
                rows,
                field,
                horizon,
                standardized=
                    standardized,
            )

            pearson = (
                calculate_pearson(
                    pairs
                )
            )

            spearman = (
                calculate_spearman(
                    pairs
                )
            )

            print(
                f"{signal_name:<24}"
                f"{horizon:>10}"
                f"{len(pairs):>8}"

                f"{format_correlation(
                    pearson
                ):>14}"

                f"{format_correlation(
                    spearman
                ):>14}"
            )


def print_company_consistency(
    rows,
):
    print()
    print(
        "PER-COMPANY RAW SPEARMAN "
        "CONSISTENCY"
    )

    print("=" * 94)

    print(
        f"{'Signal':<24}"
        f"{'Horizon':>10}"
        f"{'Positive':>10}"
        f"{'Negative':>10}"
        f"{'No Data':>10}"
        f"{'Avg Corr':>14}"
    )

    print("-" * 94)

    tickers = sorted(
        {
            row["ticker"]
            for row in rows
        }
    )

    for signal_name, field in (
        MARKET_SIGNALS.items()
    ):
        for horizon in HORIZONS:
            positive = 0
            negative = 0
            unavailable = 0

            correlations = []

            for ticker in tickers:
                company_rows = [
                    row
                    for row in rows
                    if row[
                        "ticker"
                    ] == ticker
                ]

                pairs = get_pairs(
                    company_rows,
                    field,
                    horizon,
                )

                correlation = (
                    calculate_spearman(
                        pairs
                    )
                )

                if correlation is None:
                    unavailable += 1
                    continue

                correlations.append(
                    correlation
                )

                if correlation > 0:
                    positive += 1

                elif correlation < 0:
                    negative += 1

            average = (
                mean(correlations)
                if correlations
                else None
            )

            print(
                f"{signal_name:<24}"
                f"{horizon:>10}"
                f"{positive:>10}"
                f"{negative:>10}"
                f"{unavailable:>10}"

                f"{format_correlation(
                    average
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

    rows = add_company_z_scores(
        rows
    )

    training, testing = (
        split_by_time(
            rows
        )
    )

    print()
    print(
        "CONTINUOUS MARKET "
        "CONTEXT VALIDATION"
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

    print_period(
        "TRAINING PERIOD",
        training,
        standardized=False,
    )

    print_period(
        "TRAINING PERIOD",
        training,
        standardized=True,
    )

    print_period(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
        standardized=False,
    )

    print_period(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
        standardized=True,
    )

    print_company_consistency(
        rows
    )


if __name__ == "__main__":
    main()