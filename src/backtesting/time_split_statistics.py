import sys

from datetime import date
from decimal import Decimal
from statistics import median

from src.database import get_connection


TRAIN_END = date(2023, 12, 31)
TEST_START = date(2024, 1, 1)

DEFAULT_UNIVERSE = "historical_sp500"


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


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


def get_events(universe_name=DEFAULT_UNIVERSE):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            if universe_name == "historical_sp500":
                cursor.execute(
                    """
                    WITH sector_data AS (
                        SELECT
                            security_id,
                            MAX(sector) AS sector

                        FROM analysis_universe_members

                        WHERE sector IS NOT NULL

                        GROUP BY security_id
                    )

                    SELECT
                        s.ticker,
                        COALESCE(
                            sd.sector,
                            'UNKNOWN'
                        ) AS sector,

                        be.period_end,
                        be.entry_date,

                        be.revenue_yoy,
                        be.revenue_acceleration,
                        be.eps_yoy,
                        be.gross_margin_change,
                        be.operating_margin_change,

                        be.pre_excess_20d,

                        be.exit_date_30d,
                        be.excess_30d,

                        be.exit_date_90d,
                        be.excess_90d,

                        be.exit_date_180d,
                        be.excess_180d

                    FROM backtest_events be

                    JOIN securities s
                        ON s.id = be.security_id

                    JOIN index_membership_history imh
                        ON imh.security_id =
                           be.security_id
                       AND imh.index_name =
                           'S&P 500'
                       AND imh.effective_from <=
                           be.entry_date
                       AND (
                           imh.effective_to IS NULL
                           OR imh.effective_to >=
                              be.entry_date
                       )

                    LEFT JOIN sector_data sd
                        ON sd.security_id =
                           be.security_id

                    ORDER BY
                        be.entry_date,
                        s.ticker;
                    """
                )

            else:
                cursor.execute(
                    """
                    WITH sector_data AS (
                        SELECT
                            security_id,
                            MAX(sector) AS sector

                        FROM analysis_universe_members

                        WHERE sector IS NOT NULL

                        GROUP BY security_id
                    )

                    SELECT
                        s.ticker,
                        COALESCE(
                            aum.sector,
                            sd.sector,
                            'UNKNOWN'
                        ) AS sector,

                        be.period_end,
                        be.entry_date,

                        be.revenue_yoy,
                        be.revenue_acceleration,
                        be.eps_yoy,
                        be.gross_margin_change,
                        be.operating_margin_change,

                        be.pre_excess_20d,

                        be.exit_date_30d,
                        be.excess_30d,

                        be.exit_date_90d,
                        be.excess_90d,

                        be.exit_date_180d,
                        be.excess_180d

                    FROM backtest_events be

                    JOIN securities s
                        ON s.id = be.security_id

                    JOIN analysis_universe_members aum
                        ON aum.security_id = s.id

                    JOIN analysis_universes au
                        ON au.id = aum.universe_id
                       AND au.name = %s

                    LEFT JOIN sector_data sd
                        ON sd.security_id =
                           be.security_id

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
            "ticker": row[0],
            "sector": row[1],

            "period_end": row[2],
            "entry_date": row[3],

            "revenue_yoy": row[4],
            "revenue_acceleration": row[5],
            "eps_yoy": row[6],
            "gross_margin_change": row[7],
            "operating_margin_change": row[8],

            "pre_excess_20d": row[9],

            "exit_date_30d": row[10],
            "excess_30d": row[11],

            "exit_date_90d": row[12],
            "excess_90d": row[13],

            "exit_date_180d": row[14],
            "excess_180d": row[15],
        }
        for row in rows
    ]
    

def split_by_time(rows):
    training = [
        row
        for row in rows
        if row["entry_date"] <= TRAIN_END
    ]

    testing = [
        row
        for row in rows
        if row["entry_date"] >= TEST_START
    ]

    return training, testing


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
        Decimal(wins)
        / Decimal(len(values))
        * Decimal("100"),
        2,
    )


def get_stats(rows, horizon):
    key = f"excess_{horizon}"

    values = [
        row[key]
        for row in rows
        if row.get(key) is not None
    ]

    return {
        "n": len(values),
        "average": calculate_average(values),
        "median": calculate_median(values),
        "win_rate": calculate_win_rate(values),
    }


def split_signal(rows, field):
    positive = [
        row
        for row in rows
        if (
            row.get(field) is not None
            and row[field] > 0
        )
    ]

    negative = [
        row
        for row in rows
        if (
            row.get(field) is not None
            and row[field] < 0
        )
    ]

    return positive, negative


def calculate_difference(rows, field, horizon):
    positive, negative = split_signal(
        rows,
        field,
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
            positive_value - negative_value,
            2,
        )

    return {
        "positive_n":
            positive_stats["n"],

        "negative_n":
            negative_stats["n"],

        "average_diff":
            difference(
                positive_stats["average"],
                negative_stats["average"],
            ),

        "median_diff":
            difference(
                positive_stats["median"],
                negative_stats["median"],
            ),

        "win_diff":
            difference(
                positive_stats["win_rate"],
                negative_stats["win_rate"],
            ),
    }


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_period(name, rows):
    print()
    print(name)
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

    for signal_name, field in SIGNALS.items():
        for horizon in HORIZONS:
            result = calculate_difference(
                rows,
                field,
                horizon,
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
                f"{format_percent(result['average_diff']):>14}"
                f"{format_percent(result['median_diff']):>14}"
                f"{format_percent(result['win_diff']):>14}"
            )


def get_bucket(value):
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


def print_bucket_period(name, rows):
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
    print(name)
    print("#" * 108)

    print(
        "Events:",
        len(rows),
    )

    for signal_name, field in bucket_signals.items():
        print()
        print(
            signal_name.upper()
        )

        print("-" * 108)

        print(
            f"{'Bucket':<18}"
            f"{'Horizon':>10}"
            f"{'N':>8}"
            f"{'Average':>14}"
            f"{'Median':>14}"
            f"{'Win Rate':>14}"
        )

        print("-" * 108)

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
                stats = get_stats(
                    bucket_rows,
                    horizon,
                )

                print(
                    f"{bucket:<18}"
                    f"{horizon:>10}"
                    f"{stats['n']:>8}"
                    f"{format_percent(stats['average']):>14}"
                    f"{format_percent(stats['median']):>14}"
                    f"{format_percent(stats['win_rate']):>14}"
                )

            print()


def get_high_acceleration_events(rows):
    return [
        row
        for row in rows
        if (
            row.get(
                "revenue_acceleration"
            )
            is not None

            and row[
                "revenue_acceleration"
            ] >= Decimal("20")
        )
    ]


def print_group_concentration(
    title,
    rows,
    field,
):
    groups = {}

    for row in rows:
        name = row.get(
            field
        )

        if not name:
            name = "UNKNOWN"

        groups.setdefault(
            name,
            [],
        ).append(
            row
        )

    print()
    print(title)
    print("-" * 108)

    print(
        f"{'Group':<28}"
        f"{'Events':>8}"
        f"{'Share':>10}"
        f"{'180d N':>10}"
        f"{'180d Avg':>14}"
        f"{'180d Med':>14}"
        f"{'180d Win':>14}"
    )

    print("-" * 108)

    total = len(rows)

    ordered_groups = sorted(
        groups.items(),
        key=lambda item: (
            -len(item[1]),
            item[0],
        ),
    )

    for name, group_rows in ordered_groups:
        stats = get_stats(
            group_rows,
            "180d",
        )

        share = None

        if total > 0:
            share = (
                Decimal(len(group_rows))
                / Decimal(total)
                * Decimal("100")
            )

        print(
            f"{name:<28}"
            f"{len(group_rows):>8}"
            f"{format_percent(share):>10}"
            f"{stats['n']:>10}"
            f"{format_percent(stats['average']):>14}"
            f"{format_percent(stats['median']):>14}"
            f"{format_percent(stats['win_rate']):>14}"
        )


def print_acceleration_concentration(
    name,
    rows,
):
    high_acceleration = (
        get_high_acceleration_events(
            rows
        )
    )

    print()
    print(name)
    print("#" * 108)

    print(
        "Revenue acceleration >= 20% "
        "events:",
        len(high_acceleration),
    )

    print_group_concentration(
        "BY COMPANY",
        high_acceleration,
        "ticker",
    )

    print_group_concentration(
        "BY SECTOR",
        high_acceleration,
        "sector",
    )


def get_sector_groups(rows):
    sectors = {}

    for row in rows:
        sector = row.get(
            "sector"
        )

        if not sector:
            sector = "UNKNOWN"

        sectors.setdefault(
            sector,
            [],
        ).append(
            row
        )

    return sectors


def split_acceleration_threshold(rows):
    high = []
    lower = []

    for row in rows:
        value = row.get(
            "revenue_acceleration"
        )

        if value is None:
            continue

        if value >= Decimal("20"):
            high.append(
                row
            )
        else:
            lower.append(
                row
            )

    return high, lower


def subtract_values(
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


def print_within_sector_period(
    name,
    rows,
):
    sectors = get_sector_groups(
        rows
    )

    print()
    print(name)
    print("#" * 132)

    print(
        "Comparison: revenue acceleration "
        ">= 20% vs < 20% within each sector"
    )

    print()

    print(
        f"{'Sector':<28}"
        f"{'N High/Low':>13}"
        f"{'High Avg':>12}"
        f"{'Low Avg':>12}"
        f"{'Avg Δ':>12}"
        f"{'High Med':>12}"
        f"{'Low Med':>12}"
        f"{'Med Δ':>12}"
        f"{'Win Δ':>12}"
    )

    print("-" * 132)

    ordered_sectors = sorted(
        sectors.items(),
        key=lambda item: (
            -len(item[1]),
            item[0],
        ),
    )

    for sector, sector_rows in ordered_sectors:
        high, lower = (
            split_acceleration_threshold(
                sector_rows
            )
        )

        high_stats = get_stats(
            high,
            "180d",
        )

        lower_stats = get_stats(
            lower,
            "180d",
        )

        samples = (
            f"{high_stats['n']}"
            f" / "
            f"{lower_stats['n']}"
        )

        average_diff = subtract_values(
            high_stats["average"],
            lower_stats["average"],
        )

        median_diff = subtract_values(
            high_stats["median"],
            lower_stats["median"],
        )

        win_diff = subtract_values(
            high_stats["win_rate"],
            lower_stats["win_rate"],
        )

        print(
            f"{sector:<28}"
            f"{samples:>13}"
            f"{format_percent(high_stats['average']):>12}"
            f"{format_percent(lower_stats['average']):>12}"
            f"{format_percent(average_diff):>12}"
            f"{format_percent(high_stats['median']):>12}"
            f"{format_percent(lower_stats['median']):>12}"
            f"{format_percent(median_diff):>12}"
            f"{format_percent(win_diff):>12}"
        )


def calculate_percentile(
    values,
    percentile,
):
    if not values:
        return None

    ordered = sorted(
        values
    )

    if len(ordered) == 1:
        return round(
            ordered[0],
            2,
        )

    position = (
        Decimal(len(ordered) - 1)
        * percentile
    )

    lower_index = int(
        position
    )

    upper_index = min(
        lower_index + 1,
        len(ordered) - 1,
    )

    fraction = (
        position
        - Decimal(lower_index)
    )

    lower_value = ordered[
        lower_index
    ]

    upper_value = ordered[
        upper_index
    ]

    result = (
        lower_value
        + (
            upper_value
            - lower_value
        )
        * fraction
    )

    return round(
        result,
        2,
    )


def calculate_trimmed_average(
    values,
    trim_percent=Decimal("0.10"),
):
    if not values:
        return None

    ordered = sorted(
        values
    )

    trim_count = int(
        Decimal(len(ordered))
        * trim_percent
    )

    if trim_count == 0:
        return calculate_average(
            ordered
        )

    if (
        trim_count * 2
        >= len(ordered)
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


def get_distribution_stats(
    rows,
    horizon,
):
    key = (
        f"excess_{horizon}"
    )

    values = [
        row[key]
        for row in rows
        if row.get(key) is not None
    ]

    if not values:
        return {
            "n": 0,
            "minimum": None,
            "p10": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p90": None,
            "maximum": None,
            "average": None,
            "trimmed_average": None,
        }

    return {
        "n":
            len(values),

        "minimum":
            round(
                min(values),
                2,
            ),

        "p10":
            calculate_percentile(
                values,
                Decimal("0.10"),
            ),

        "p25":
            calculate_percentile(
                values,
                Decimal("0.25"),
            ),

        "median":
            calculate_percentile(
                values,
                Decimal("0.50"),
            ),

        "p75":
            calculate_percentile(
                values,
                Decimal("0.75"),
            ),

        "p90":
            calculate_percentile(
                values,
                Decimal("0.90"),
            ),

        "maximum":
            round(
                max(values),
                2,
            ),

        "average":
            calculate_average(
                values
            ),

        "trimmed_average":
            calculate_trimmed_average(
                values
            ),
    }


def print_distribution_period(
    name,
    rows,
):
    high_acceleration = (
        get_high_acceleration_events(
            rows
        )
    )

    print()
    print(name)
    print("#" * 142)

    print(
        "Revenue acceleration >= 20%"
    )

    print(
        "Trimmed average removes "
        "10% of observations from "
        "each end of the return distribution."
    )

    print()

    print(
        f"{'Horizon':<10}"
        f"{'N':>7}"
        f"{'Min':>13}"
        f"{'P10':>13}"
        f"{'P25':>13}"
        f"{'Median':>13}"
        f"{'P75':>13}"
        f"{'P90':>13}"
        f"{'Max':>13}"
        f"{'Average':>14}"
        f"{'Trim Avg':>14}"
    )

    print("-" * 142)

    for horizon in HORIZONS:
        stats = get_distribution_stats(
            high_acceleration,
            horizon,
        )

        print(
            f"{horizon:<10}"
            f"{stats['n']:>7}"
            f"{format_percent(stats['minimum']):>13}"
            f"{format_percent(stats['p10']):>13}"
            f"{format_percent(stats['p25']):>13}"
            f"{format_percent(stats['median']):>13}"
            f"{format_percent(stats['p75']):>13}"
            f"{format_percent(stats['p90']):>13}"
            f"{format_percent(stats['maximum']):>13}"
            f"{format_percent(stats['average']):>14}"
            f"{format_percent(stats['trimmed_average']):>14}"
        )


def combination_matches(
    row,
    combination,
):
    acceleration = row.get(
        "revenue_acceleration"
    )

    if (
        acceleration is None
        or acceleration < Decimal("20")
    ):
        return False

    if combination == "base":
        return True

    if combination == "revenue_positive":
        value = row.get(
            "revenue_yoy"
        )

        return (
            value is not None
            and value > 0
        )

    if combination == "revenue_10":
        value = row.get(
            "revenue_yoy"
        )

        return (
            value is not None
            and value >= Decimal("10")
        )

    if combination == "eps_positive":
        value = row.get(
            "eps_yoy"
        )

        return (
            value is not None
            and value > 0
        )

    if combination == "gross_margin_positive":
        value = row.get(
            "gross_margin_change"
        )

        return (
            value is not None
            and value > 0
        )

    if combination == "operating_margin_positive":
        value = row.get(
            "operating_margin_change"
        )

        return (
            value is not None
            and value > 0
        )

    if combination == "revenue_10_eps_positive":
        revenue = row.get(
            "revenue_yoy"
        )

        eps = row.get(
            "eps_yoy"
        )

        return (
            revenue is not None
            and revenue >= Decimal("10")
            and eps is not None
            and eps > 0
        )

    if combination == "revenue_positive_eps_positive":
        revenue = row.get(
            "revenue_yoy"
        )

        eps = row.get(
            "eps_yoy"
        )

        return (
            revenue is not None
            and revenue > 0
            and eps is not None
            and eps > 0
        )

    if combination == "eps_operating_positive":
        eps = row.get(
            "eps_yoy"
        )

        operating_margin = row.get(
            "operating_margin_change"
        )

        return (
            eps is not None
            and eps > 0
            and operating_margin is not None
            and operating_margin > 0
        )

    return False


def get_combination_rows(
    rows,
    combination,
):
    return [
        row
        for row in rows
        if combination_matches(
            row,
            combination,
        )
    ]


def print_combination_period(
    name,
    rows,
):
    combinations = [
        (
            "base",
            "Acceleration >= 20%",
        ),
        (
            "revenue_positive",
            "+ Revenue Growth > 0",
        ),
        (
            "revenue_10",
            "+ Revenue Growth >= 10%",
        ),
        (
            "eps_positive",
            "+ EPS Growth > 0",
        ),
        (
            "gross_margin_positive",
            "+ Gross Margin Improving",
        ),
        (
            "operating_margin_positive",
            "+ Operating Margin Improving",
        ),
        (
            "revenue_10_eps_positive",
            "+ Revenue >= 10% + EPS > 0",
        ),
        (
            "revenue_positive_eps_positive",
            "+ Revenue > 0 + EPS > 0",
        ),
        (
            "eps_operating_positive",
            "+ EPS > 0 + Op Margin Improving",
        ),
    ]
    
    print()
    print(name)
    print("#" * 125)

    print(
        f"{'Combination':<32}"
        f"{'Horizon':>10}"
        f"{'N':>8}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
    )

    print("-" * 125)

    for combination, label in combinations:
        combination_rows = (
            get_combination_rows(
                rows,
                combination,
            )
        )

        first = True

        for horizon in HORIZONS:
            stats = get_stats(
                combination_rows,
                horizon,
            )

            display_label = (
                label
                if first
                else ""
            )

            print(
                f"{display_label:<32}"
                f"{horizon:>10}"
                f"{stats['n']:>8}"
                f"{format_percent(stats['average']):>14}"
                f"{format_percent(stats['median']):>14}"
                f"{format_percent(stats['win_rate']):>14}"
            )

            first = False

        print()


def get_strong_combination_events(rows):
    return [
        row
        for row in rows
        if (
            row.get("revenue_acceleration") is not None
            and row["revenue_acceleration"] >= Decimal("20")

            and row.get("revenue_yoy") is not None
            and row["revenue_yoy"] >= Decimal("10")

            and row.get("eps_yoy") is not None
            and row["eps_yoy"] > 0
        )
    ]


def format_date(value):
    if value is None:
        return "-"

    return value.isoformat()


def print_strong_combination_events(
    name,
    rows,
):
    events = get_strong_combination_events(
        rows
    )

    print()
    print(name)
    print("#" * 160)

    print(
        "Revenue acceleration >= 20% "
        "+ revenue growth >= 10% "
        "+ EPS growth > 0"
    )

    print(
        "Qualifying events:",
        len(events),
    )

    print()

    print(
        f"{'Ticker':<8}"
        f"{'Sector':<25}"
        f"{'Period End':>12}"
        f"{'Entry Date':>12}"
        f"{'Rev Growth':>13}"
        f"{'Rev Accel':>13}"
        f"{'EPS Growth':>13}"
        f"{'30d':>12}"
        f"{'90d':>12}"
        f"{'180d':>12}"
    )

    print("-" * 160)

    for row in events:
        print(
            f"{row['ticker']:<8}"
            f"{(row['sector'] or 'UNKNOWN'):<25}"
            f"{format_date(row['period_end']):>12}"
            f"{format_date(row['entry_date']):>12}"
            f"{format_percent(row['revenue_yoy']):>13}"
            f"{format_percent(row['revenue_acceleration']):>13}"
            f"{format_percent(row['eps_yoy']):>13}"
            f"{format_percent(row['excess_30d']):>12}"
            f"{format_percent(row['excess_90d']):>12}"
            f"{format_percent(row['excess_180d']):>12}"
        )

    unique_companies = {
        row["ticker"]
        for row in events
    }

    print()
    print(
        "Unique companies:",
        len(unique_companies),
    )

    print(
        "Companies:",
        ", ".join(
            sorted(unique_companies)
        ),
    )


def group_events_by_year(rows):
    years = {}

    for row in rows:
        entry_date = row.get(
            "entry_date"
        )

        if entry_date is None:
            continue

        year = entry_date.year

        years.setdefault(
            year,
            [],
        ).append(
            row
        )

    return years


def print_yearly_signal_stability(
    name,
    rows,
):
    qualifying = (
        get_strong_combination_events(
            rows
        )
    )

    years = group_events_by_year(
        qualifying
    )

    print()
    print(name)
    print("#" * 112)

    print(
        "Revenue acceleration >= 20% "
        "+ revenue growth >= 10% "
        "+ EPS growth > 0"
    )

    print()

    print(
        f"{'Year':<8}"
        f"{'Events':>8}"
        f"{'180d N':>10}"
        f"{'Average':>14}"
        f"{'Median':>14}"
        f"{'Win Rate':>14}"
        f"{'Companies':>12}"
    )

    print("-" * 112)

    for year in sorted(
        years.keys()
    ):
        year_rows = years[
            year
        ]

        stats = get_stats(
            year_rows,
            "180d",
        )

        companies = {
            row["ticker"]
            for row in year_rows
        }

        print(
            f"{year:<8}"
            f"{len(year_rows):>8}"
            f"{stats['n']:>10}"
            f"{format_percent(stats['average']):>14}"
            f"{format_percent(stats['median']):>14}"
            f"{format_percent(stats['win_rate']):>14}"
            f"{len(companies):>12}"
        )
        
        

def get_positive_signal_rows(rows, field):
    return [
        row
        for row in rows
        if (
            row.get(field) is not None
            and row[field] > 0
        )
    ]


def get_robustness_candidates(rows):
    return [
        (
            "Revenue Growth > 0",
            get_positive_signal_rows(
                rows,
                "revenue_yoy",
            ),
        ),
        (
            "Revenue Acceleration > 0",
            get_positive_signal_rows(
                rows,
                "revenue_acceleration",
            ),
        ),
        (
            "Revenue Acceleration >= 20%",
            get_high_acceleration_events(
                rows
            ),
        ),
        (
            "EPS Growth > 0",
            get_positive_signal_rows(
                rows,
                "eps_yoy",
            ),
        ),
        (
            "Gross Margin Improving",
            get_positive_signal_rows(
                rows,
                "gross_margin_change",
            ),
        ),
        (
            "Operating Margin Improving",
            get_positive_signal_rows(
                rows,
                "operating_margin_change",
            ),
        ),
        (
            "Accel >=20% + Revenue >=10%",
            [
                row
                for row in rows
                if (
                    row.get("revenue_acceleration") is not None
                    and row["revenue_acceleration"] >= Decimal("20")
                    and row.get("revenue_yoy") is not None
                    and row["revenue_yoy"] >= Decimal("10")
                )
            ],
        ),
        (
            "Accel >=20% + EPS > 0",
            [
                row
                for row in rows
                if (
                    row.get("revenue_acceleration") is not None
                    and row["revenue_acceleration"] >= Decimal("20")
                    and row.get("eps_yoy") is not None
                    and row["eps_yoy"] > 0
                )
            ],
        ),
        (
            "Accel >=20% + Op Margin Improving",
            [
                row
                for row in rows
                if (
                    row.get("revenue_acceleration") is not None
                    and row["revenue_acceleration"] >= Decimal("20")
                    and row.get("operating_margin_change") is not None
                    and row["operating_margin_change"] > 0
                )
            ],
        ),
        (
            "Strong Combination",
            get_strong_combination_events(
                rows
            ),
        ),
        (
            "Pre Excess 20d > 0",
            [
                row
                for row in rows
                if (
                    row.get("pre_excess_20d") is not None
                    and row["pre_excess_20d"] > 0
                )
            ],
        ),
        (
            "Accel >=20% + Op Margin + Momentum",
            [
                row
                for row in rows
                if (
                    row.get("revenue_acceleration") is not None
                    and row["revenue_acceleration"] >= Decimal("20")
                    and row.get("operating_margin_change") is not None
                    and row["operating_margin_change"] > 0
                    and row.get("pre_excess_20d") is not None
                    and row["pre_excess_20d"] > 0
                )
            ],
        ),
        (
            "Strong Combination + Momentum",
            [
                row
                for row in get_strong_combination_events(
                    rows
                )
                if (
                    row.get("pre_excess_20d") is not None
                    and row["pre_excess_20d"] > 0
                )
            ],
        ),
    ]


def print_candidate_concentration(
    title,
    rows,
):
    candidate_rows = [
        row
        for row in rows
        if (
            row.get("revenue_acceleration") is not None
            and row["revenue_acceleration"] >= Decimal("20")
            and row.get("operating_margin_change") is not None
            and row["operating_margin_change"] > 0
            and row.get("pre_excess_20d") is not None
            and row["pre_excess_20d"] > 0
        )
    ]

    print()
    print(title)
    print("#" * 110)

    for field, heading in (
        ("ticker", "BY COMPANY"),
        ("sector", "BY SECTOR"),
    ):
        groups = {}

        for row in candidate_rows:
            name = row.get(field) or "UNKNOWN"
            groups.setdefault(name, []).append(row)

        print()
        print(heading)
        print("-" * 110)

        print(
            f"{'Group':<30}"
            f"{'Events':>8}"
            f"{'Share':>10}"
            f"{'30d Avg':>14}"
            f"{'30d Med':>14}"
            f"{'30d Win':>14}"
        )

        print("-" * 110)

        total = len(candidate_rows)

        for name, group_rows in sorted(
            groups.items(),
            key=lambda item: (-len(item[1]), item[0]),
        ):
            stats = get_stats(group_rows, "30d")

            share = (
                Decimal(len(group_rows))
                / Decimal(total)
                * Decimal("100")
                if total
                else None
            )

            print(
                f"{name:<30}"
                f"{len(group_rows):>8}"
                f"{format_percent(share):>10}"
                f"{format_percent(stats['average']):>14}"
                f"{format_percent(stats['median']):>14}"
                f"{format_percent(stats['win_rate']):>14}"
            )



def print_candidate_sector_exclusion(
    title,
    rows,
):
    candidate_rows = [
        row
        for row in rows
        if (
            row.get("revenue_acceleration") is not None
            and row["revenue_acceleration"] >= Decimal("20")
            and row.get("operating_margin_change") is not None
            and row["operating_margin_change"] > 0
            and row.get("pre_excess_20d") is not None
            and row["pre_excess_20d"] > 0
        )
    ]

    sectors = sorted(
        {
            row.get("sector") or "UNKNOWN"
            for row in candidate_rows
        }
    )

    print()
    print(title)
    print("#" * 110)

    print(
        f"{'Excluded Sector':<30}"
        f"{'N':>8}"
        f"{'30d Avg':>14}"
        f"{'30d Med':>14}"
        f"{'30d Win':>14}"
        f"{'Trim Avg':>14}"
    )

    print("-" * 110)

    for sector in sectors:
        remaining = [
            row
            for row in candidate_rows
            if (
                row.get("sector") or "UNKNOWN"
            ) != sector
        ]

        stats = get_stats(
            remaining,
            "30d",
        )

        distribution = get_distribution_stats(
            remaining,
            "30d",
        )

        print(
            f"{sector:<30}"
            f"{stats['n']:>8}"
            f"{format_percent(stats['average']):>14}"
            f"{format_percent(stats['median']):>14}"
            f"{format_percent(stats['win_rate']):>14}"
            f"{format_percent(distribution['trimmed_average']):>14}"
        )



def get_candidate_year_stats(rows, horizon):
    years = group_events_by_year(rows)

    positive_years = 0
    negative_years = 0
    usable_years = 0

    for year_rows in years.values():
        stats = get_stats(
            year_rows,
            horizon,
        )

        if stats["n"] == 0:
            continue

        usable_years += 1

        if (
            stats["median"] is not None
            and stats["median"] > 0
        ):
            positive_years += 1
        else:
            negative_years += 1

    return {
        "usable_years": usable_years,
        "positive_years": positive_years,
        "negative_years": negative_years,
    }


def print_robustness_period(
    name,
    rows,
):
    print()
    print(name)
    print("#" * 170)

    print(
        f"{'Candidate':<38}"
        f"{'Horizon':>9}"
        f"{'N':>7}"
        f"{'Average':>12}"
        f"{'Median':>12}"
        f"{'Win':>10}"
        f"{'Trim Avg':>12}"
        f"{'+Med Yrs':>11}"
        f"{'Years':>8}"
    )

    print("-" * 170)

    for candidate_name, candidate_rows in (
        get_robustness_candidates(rows)
    ):
        first = True

        for horizon in HORIZONS:
            stats = get_stats(
                candidate_rows,
                horizon,
            )

            distribution = get_distribution_stats(
                candidate_rows,
                horizon,
            )

            year_stats = get_candidate_year_stats(
                candidate_rows,
                horizon,
            )

            display_name = (
                candidate_name
                if first
                else ""
            )

            print(
                f"{display_name:<38}"
                f"{horizon:>9}"
                f"{stats['n']:>7}"
                f"{format_percent(stats['average']):>12}"
                f"{format_percent(stats['median']):>12}"
                f"{format_percent(stats['win_rate']):>10}"
                f"{format_percent(distribution['trimmed_average']):>12}"
                f"{year_stats['positive_years']:>11}"
                f"{year_stats['usable_years']:>8}"
            )

            first = False

        print()


def print_signal_robustness_comparison(
    training,
    testing,
):
    print()
    print(
        "SIGNAL ROBUSTNESS COMPARISON"
    )

    print(
        "Compares raw average, median, win rate, "
        "10% trimmed average, and year-by-year "
        "median consistency."
    )

    print_robustness_period(
        "TRAINING PERIOD",
        training,
    )

    print_robustness_period(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )

def main():
    universe_name = get_universe_name()

    rows = get_events(
        universe_name
    )

    training, testing = split_by_time(
        rows
    )

    print()
    print(
        "TIME-SPLIT SIGNAL TEST"
    )

    print(
        "Universe:",
        universe_name,
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

    print()
    print(
        "TIME-SPLIT SIGNAL "
        "BUCKET VALIDATION"
    )

    print_bucket_period(
        "TRAINING PERIOD BUCKETS",
        training,
    )

    print_bucket_period(
        "OUT-OF-SAMPLE TEST PERIOD BUCKETS",
        testing,
    )

    print()
    print(
        "REVENUE ACCELERATION "
        "CONCENTRATION TEST"
    )

    print_acceleration_concentration(
        "TRAINING PERIOD",
        training,
    )

    print_acceleration_concentration(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )

    print()
    print(
        "WITHIN-SECTOR REVENUE "
        "ACCELERATION VALIDATION"
    )

    print_within_sector_period(
        "TRAINING PERIOD",
        training,
    )

    print_within_sector_period(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )

    print()
    print(
        "REVENUE ACCELERATION "
        "OUTLIER ROBUSTNESS TEST"
    )

    print_distribution_period(
        "TRAINING PERIOD",
        training,
    )

    print_distribution_period(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )

    print()
    print(
        "REVENUE ACCELERATION "
        "COMBINATION TEST"
    )

    print_combination_period(
        "TRAINING PERIOD",
        training,
    )

    print_combination_period(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )
    
    print()
    print(
        "STRONG COMBINATION "
        "EVENT DETAILS"
    )

    print_strong_combination_events(
        "TRAINING PERIOD",
        training,
    )

    print_strong_combination_events(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )

    print()
    print(
        "YEAR-BY-YEAR SIGNAL "
        "STABILITY TEST"
    )

    print_yearly_signal_stability(
        "TRAINING PERIOD",
        training,
    )

    print_yearly_signal_stability(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )

    print_signal_robustness_comparison(
        training,
        testing,
    )

    print_candidate_concentration(
        "TRAINING CANDIDATE CONCENTRATION",
        training,
    )

    print_candidate_concentration(
        "OUT-OF-SAMPLE CANDIDATE CONCENTRATION",
        testing,
    )

    print_candidate_sector_exclusion(
        "OUT-OF-SAMPLE LEAVE-ONE-SECTOR-OUT",
        testing,
    )
        
if __name__ == "__main__":
    main()