import sys

from decimal import Decimal
from statistics import median

from src.analysis.experimental_signal import (
    SIGNAL_DESCRIPTION,
    get_experimental_signal_events,
)
from src.backtesting.time_split_statistics import (
    DEFAULT_UNIVERSE,
    TRAIN_END,
    TEST_START,
)
from src.database import get_connection


HORIZON = "30d"


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


def get_events(
    universe_name,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.ticker,
                    aum.sector,

                    be.entry_date,

                    be.revenue_acceleration,
                    be.operating_margin_change,
                    be.pre_excess_20d,

                    be.pre_return_60d,
                    be.pre_volatility_20d,
                    be.opening_gap_excess,

                    be.excess_30d

                FROM backtest_events be

                JOIN securities s
                    ON s.id = be.security_id

                JOIN analysis_universe_members aum
                    ON aum.security_id = s.id

                JOIN analysis_universes au
                    ON au.id = aum.universe_id
                   AND au.name = %s

                ORDER BY
                    be.entry_date,
                    s.ticker;
                """,
                (
                    universe_name,
                ),
            )

            rows = cursor.fetchall()

    return [
        {
            "ticker":
                row[0],

            "sector":
                row[1],

            "entry_date":
                row[2],

            "revenue_acceleration":
                row[3],

            "operating_margin_change":
                row[4],

            "pre_excess_20d":
                row[5],

            "pre_return_60d":
                row[6],

            "pre_volatility_20d":
                row[7],

            "opening_gap_excess":
                row[8],

            "excess_30d":
                row[9],
        }
        for row in rows
    ]


def split_by_time(
    rows,
):
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


def calculate_average(
    values,
):
    if not values:
        return None

    return (
        sum(
            values,
            Decimal("0"),
        )
        / Decimal(
            len(values)
        )
    )


def calculate_median(
    values,
):
    if not values:
        return None

    return Decimal(
        str(
            median(values)
        )
    )


def calculate_win_rate(
    values,
):
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


def calculate_stats(
    rows,
):
    values = [
        row[
            f"excess_{HORIZON}"
        ]
        for row in rows
        if row.get(
            f"excess_{HORIZON}"
        ) is not None
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


def format_percent(
    value,
):
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
        f"{label:<34}"
        f"{stats['n']:>8}"
        f"{format_percent(
            stats['average']
        ):>14}"
        f"{format_percent(
            stats['median']
        ):>14}"
        f"{format_percent(
            stats['win_rate']
        ):>14}"
    )


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


def get_training_median(
    rows,
    field,
):
    values = [
        row[field]
        for row in rows
        if row.get(field)
        is not None
    ]

    if not values:
        return None

    return Decimal(
        str(
            median(values)
        )
    )


def split_at_threshold(
    rows,
    field,
    threshold,
):
    lower = [
        row
        for row in rows
        if (
            row.get(field)
            is not None
            and row[field]
            <= threshold
        )
    ]

    higher = [
        row
        for row in rows
        if (
            row.get(field)
            is not None
            and row[field]
            > threshold
        )
    ]

    return (
        lower,
        higher,
    )


def print_zero_regime(
    title,
    training,
    testing,
    field,
    positive_label,
    negative_label,
):
    print()
    print(title)

    print("=" * 84)

    print(
        f"{'Period / Regime':<34}"
        f"{'N':>8}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
    )

    print("-" * 84)

    train_positive, train_negative = (
        split_positive_negative(
            training,
            field,
        )
    )

    test_positive, test_negative = (
        split_positive_negative(
            testing,
            field,
        )
    )

    print_stats(
        f"Training - {positive_label}",
        train_positive,
    )

    print_stats(
        f"Training - {negative_label}",
        train_negative,
    )

    print_stats(
        f"OOS - {positive_label}",
        test_positive,
    )

    print_stats(
        f"OOS - {negative_label}",
        test_negative,
    )


def print_volatility_regime(
    training,
    testing,
):
    field = (
        "pre_volatility_20d"
    )

    threshold = (
        get_training_median(
            training,
            field,
        )
    )

    print()
    print(
        "20-DAY VOLATILITY REGIME"
    )

    print(
        "Threshold derived only from "
        "training signal matches:",
        format_percent(
            threshold
        ),
    )

    print("=" * 84)

    print(
        f"{'Period / Regime':<34}"
        f"{'N':>8}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
    )

    print("-" * 84)

    if threshold is None:
        print(
            "No usable volatility data."
        )
        return

    train_low, train_high = (
        split_at_threshold(
            training,
            field,
            threshold,
        )
    )

    test_low, test_high = (
        split_at_threshold(
            testing,
            field,
            threshold,
        )
    )

    print_stats(
        "Training - Lower Volatility",
        train_low,
    )

    print_stats(
        "Training - Higher Volatility",
        train_high,
    )

    print_stats(
        "OOS - Lower Volatility",
        test_low,
    )

    print_stats(
        "OOS - Higher Volatility",
        test_high,
    )


def print_year_regime(
    testing,
):
    print()
    print(
        "OUT-OF-SAMPLE REGIME BY YEAR"
    )

    print("=" * 84)

    print(
        f"{'Year':<34}"
        f"{'N':>8}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
    )

    print("-" * 84)

    years = sorted(
        {
            row["entry_date"].year
            for row in testing
        }
    )

    for year in years:
        rows = [
            row
            for row in testing
            if row[
                "entry_date"
            ].year == year
        ]

        print_stats(
            str(year),
            rows,
        )


def main():
    universe_name = (
        get_universe_name()
    )

    rows = get_events(
        universe_name
    )

    training, testing = (
        split_by_time(
            rows
        )
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
        "EXPERIMENTAL SIGNAL "
        "REGIME TEST"
    )

    print("=" * 84)

    print(
        "Universe:",
        universe_name,
    )

    print(
        "Signal:",
        SIGNAL_DESCRIPTION,
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
        "Training matches:",
        len(training_matches),
    )

    print(
        "Out-of-sample matches:",
        len(testing_matches),
    )

    print_zero_regime(
        title=(
            "PRIOR 60-DAY STOCK TREND"
        ),
        training=training_matches,
        testing=testing_matches,
        field="pre_return_60d",
        positive_label="Positive Trend",
        negative_label="Negative Trend",
    )

    print_zero_regime(
        title=(
            "OPENING GAP EXCESS VS SPY"
        ),
        training=training_matches,
        testing=testing_matches,
        field="opening_gap_excess",
        positive_label="Positive Gap Excess",
        negative_label="Negative Gap Excess",
    )

    print_volatility_regime(
        training_matches,
        testing_matches,
    )

    print_year_regime(
        testing_matches
    )


if __name__ == "__main__":
    main()