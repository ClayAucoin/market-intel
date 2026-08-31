import sys

from decimal import Decimal
from statistics import median

from src.database import get_connection
from src.time_split_statistics import DEFAULT_UNIVERSE


HORIZONS = [
    "30d",
    "90d",
    "180d",
]


SIGNALS = {
    "Revenue Growth": "revenue_yoy",
    "Revenue Acceleration":
        "revenue_acceleration",
    "EPS Growth": "eps_yoy",
    "Gross Margin": "gross_margin_change",
    "Operating Margin":
        "operating_margin_change",
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
            "period_end": row[1],
            "entry_date": row[2],

            "revenue_yoy": row[3],
            "revenue_acceleration": row[4],
            "eps_yoy": row[5],
            "gross_margin_change": row[6],
            "operating_margin_change": row[7],

            "excess_30d": row[8],
            "excess_90d": row[9],
            "excess_180d": row[10],
        }
        for row in rows
    ]


def get_horizon_key(horizon):
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


def calculate_statistics(
    rows,
    horizon,
):
    key = get_horizon_key(
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
            "best": None,
            "worst": None,
        }

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

        "best":
            max(values),

        "worst":
            min(values),
    }


def split_signal(
    rows,
    field,
):
    positive = []
    negative = []
    zero = []

    for row in rows:
        value = row.get(
            field
        )

        if value is None:
            continue

        if value > 0:
            positive.append(
                row
            )

        elif value < 0:
            negative.append(
                row
            )

        else:
            zero.append(
                row
            )

    return {
        "positive": positive,
        "negative": negative,
        "zero": zero,
    }


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_overall_summary(rows):
    print()
    print(
        "CROSS-COMPANY BACKTEST SUMMARY"
    )

    print("=" * 90)

    print(
        f"{'Horizon':<10}"
        f"{'N':>7}"
        f"{'Win Rate':>14}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Best':>14}"
        f"{'Worst':>14}"
    )

    print("-" * 90)

    for horizon in HORIZONS:
        stats = calculate_statistics(
            rows,
            horizon,
        )

        print(
            f"{horizon:<10}"
            f"{stats['n']:>7}"

            f"{format_percent(
                stats['win_rate']
            ):>14}"

            f"{format_percent(
                stats['average']
            ):>14}"

            f"{format_percent(
                stats['median']
            ):>14}"

            f"{format_percent(
                stats['best']
            ):>14}"

            f"{format_percent(
                stats['worst']
            ):>14}"
        )


def print_company_summary(rows):
    tickers = sorted(
        {
            row["ticker"]
            for row in rows
        }
    )

    print()
    print(
        "PER-COMPANY EXCESS RETURN"
    )

    print("=" * 106)

    print(
        f"{'Ticker':<10}"

        f"{'30d N':>7}"
        f"{'30d Med':>12}"
        f"{'30d Win':>12}"

        f"{'90d N':>8}"
        f"{'90d Med':>12}"
        f"{'90d Win':>12}"

        f"{'180d N':>9}"
        f"{'180d Med':>13}"
        f"{'180d Win':>12}"
    )

    print("-" * 106)

    for ticker in tickers:
        company_rows = [
            row
            for row in rows
            if row["ticker"]
            == ticker
        ]

        stats = {
            horizon:
                calculate_statistics(
                    company_rows,
                    horizon,
                )

            for horizon
            in HORIZONS
        }

        print(
            f"{ticker:<10}"

            f"{stats['30d']['n']:>7}"

            f"{format_percent(
                stats['30d'][
                    'median'
                ]
            ):>12}"

            f"{format_percent(
                stats['30d'][
                    'win_rate'
                ]
            ):>12}"

            f"{stats['90d']['n']:>8}"

            f"{format_percent(
                stats['90d'][
                    'median'
                ]
            ):>12}"

            f"{format_percent(
                stats['90d'][
                    'win_rate'
                ]
            ):>12}"

            f"{stats['180d']['n']:>9}"

            f"{format_percent(
                stats['180d'][
                    'median'
                ]
            ):>13}"

            f"{format_percent(
                stats['180d'][
                    'win_rate'
                ]
            ):>12}"
        )


def print_signal_comparison(rows):
    print()
    print(
        "POSITIVE VS NEGATIVE "
        "SIGNAL PERFORMANCE"
    )

    print("=" * 108)

    print(
        f"{'Signal':<24}"
        f"{'Horizon':>9}"
        f"{'N + / -':>12}"
        f"{'Avg Δ':>14}"
        f"{'Median Δ':>14}"
        f"{'Win Δ':>14}"
    )

    print("-" * 108)

    for signal_name, field in (
        SIGNALS.items()
    ):
        groups = split_signal(
            rows,
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

            average_difference = None
            median_difference = None
            win_difference = None

            if (
                positive["average"]
                is not None
                and negative["average"]
                is not None
            ):
                average_difference = round(
                    positive["average"]
                    - negative["average"],
                    2,
                )

            if (
                positive["median"]
                is not None
                and negative["median"]
                is not None
            ):
                median_difference = round(
                    positive["median"]
                    - negative["median"],
                    2,
                )

            if (
                positive["win_rate"]
                is not None
                and negative["win_rate"]
                is not None
            ):
                win_difference = round(
                    positive["win_rate"]
                    - negative["win_rate"],
                    2,
                )

            samples = (
                f"{positive['n']} / "
                f"{negative['n']}"
            )

            print(
                f"{signal_name:<24}"
                f"{horizon:>9}"
                f"{samples:>12}"

                f"{format_percent(
                    average_difference
                ):>14}"

                f"{format_percent(
                    median_difference
                ):>14}"

                f"{format_percent(
                    win_difference
                ):>14}"
            )


def print_signal_detail(rows):
    print()
    print(
        "SIGNAL GROUP DETAILS"
    )

    print("=" * 112)

    print(
        f"{'Condition':<32}"
        f"{'Horizon':>9}"
        f"{'N':>7}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
    )

    print("-" * 112)

    for signal_name, field in (
        SIGNALS.items()
    ):
        groups = split_signal(
            rows,
            field,
        )

        for group_name in [
            "positive",
            "negative",
        ]:
            if group_name == "positive":
                label = (
                    f"{signal_name} +"
                )
            else:
                label = (
                    f"{signal_name} -"
                )

            for horizon in HORIZONS:
                stats = (
                    calculate_statistics(
                        groups[
                            group_name
                        ],
                        horizon,
                    )
                )

                print(
                    f"{label:<32}"
                    f"{horizon:>9}"
                    f"{stats['n']:>7}"

                    f"{format_percent(
                        stats['average']
                    ):>14}"

                    f"{format_percent(
                        stats['median']
                    ):>14}"

                    f"{format_percent(
                        stats[
                            'win_rate'
                        ]
                    ):>14}"
                )

            print()


def get_bucket(
    value,
):
    if value is None:
        return None

    if value < Decimal("-10"):
        return "< -10%"

    if value < Decimal("0"):
        return "-10% to 0%"

    if value < Decimal("5"):
        return "0% to 5%"

    if value < Decimal("10"):
        return "5% to 10%"

    if value < Decimal("20"):
        return "10% to 20%"

    return ">= 20%"


def print_signal_buckets(
    rows,
):
    bucket_signals = {
        "Revenue Growth":
            "revenue_yoy",

        "Revenue Acceleration":
            "revenue_acceleration",
    }

    bucket_order = [
        "< -10%",
        "-10% to 0%",
        "0% to 5%",
        "5% to 10%",
        "10% to 20%",
        ">= 20%",
    ]

    print()
    print(
        "SIGNAL BUCKET PERFORMANCE"
    )

    print("=" * 100)

    for signal_name, field in (
        bucket_signals.items()
    ):
        print()
        print(signal_name.upper())

        print("-" * 100)

        print(
            f"{'Bucket':<18}"
            f"{'Horizon':>10}"
            f"{'N':>8}"
            f"{'Average':>14}"
            f"{'Median':>14}"
            f"{'Win Rate':>14}"
        )

        print("-" * 100)

        buckets = {
            bucket: []
            for bucket in bucket_order
        }

        for row in rows:
            bucket = get_bucket(
                row.get(field)
            )

            if bucket is None:
                continue

            buckets[bucket].append(
                row
            )

        for bucket in bucket_order:
            bucket_rows = buckets[
                bucket
            ]

            for horizon in HORIZONS:
                stats = (
                    calculate_statistics(
                        bucket_rows,
                        horizon,
                    )
                )

                print(
                    f"{bucket:<18}"
                    f"{horizon:>10}"
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

            print()
            
            
def main():
    universe_name = (
        sys.argv[1]
        if len(sys.argv) >= 2
        else DEFAULT_UNIVERSE
    )

    rows = get_events(
        universe_name
    )

    print()
    print(
        "Events loaded:",
        len(rows),
    )

    print_overall_summary(
        rows
    )

    print_company_summary(
        rows
    )

    print_signal_comparison(
        rows
    )

    print_signal_detail(
        rows
    )
    
    print_signal_buckets(
        rows
    )


if __name__ == "__main__":
    main()