from decimal import Decimal
import sys

from src.time_split_statistics import (
    DEFAULT_UNIVERSE,
    format_percent,
    get_events,
    get_stats,
    split_by_time,
)


def calculate_signal_score(row):
    score = 0

    revenue_growth = row.get(
        "revenue_yoy"
    )

    revenue_acceleration = row.get(
        "revenue_acceleration"
    )

    eps_growth = row.get(
        "eps_yoy"
    )

    # Revenue acceleration
    if (
        revenue_acceleration is not None
        and revenue_acceleration >= Decimal("20")
    ):
        score += 2

    # Revenue growth
    if (
        revenue_growth is not None
        and revenue_growth >= Decimal("20")
    ):
        score += 2

    elif (
        revenue_growth is not None
        and revenue_growth >= Decimal("10")
    ):
        score += 1

    # EPS growth
    if (
        eps_growth is not None
        and eps_growth >= Decimal("20")
    ):
        score += 2

    elif (
        eps_growth is not None
        and eps_growth >= Decimal("10")
    ):
        score += 1

    return score


def add_scores(rows):
    scored_rows = []

    for row in rows:
        scored_row = dict(
            row
        )

        scored_row[
            "signal_score"
        ] = calculate_signal_score(
            row
        )

        scored_rows.append(
            scored_row
        )

    return scored_rows


def get_score_bucket(score):
    if score <= 1:
        return "0-1"

    if score <= 3:
        return "2-3"

    if score <= 5:
        return "4-5"

    return "6+"


def group_by_score_bucket(rows):
    groups = {
        "0-1": [],
        "2-3": [],
        "4-5": [],
        "6+": [],
    }

    for row in rows:
        bucket = get_score_bucket(
            row["signal_score"]
        )

        groups[
            bucket
        ].append(
            row
        )

    return groups


def print_score_distribution(
    title,
    rows,
):
    groups = group_by_score_bucket(
        rows
    )

    print()
    print(title)
    print("=" * 116)

    print(
        f"{'Score':<10}"
        f"{'Events':>10}"
        f"{'30d Avg':>13}"
        f"{'30d Med':>13}"
        f"{'30d Win':>13}"
        f"{'90d Avg':>13}"
        f"{'90d Med':>13}"
        f"{'90d Win':>13}"
    )

    print("-" * 116)

    for bucket in [
        "0-1",
        "2-3",
        "4-5",
        "6+",
    ]:
        bucket_rows = groups[
            bucket
        ]

        stats_30 = get_stats(
            bucket_rows,
            "30d",
        )

        stats_90 = get_stats(
            bucket_rows,
            "90d",
        )

        print(
            f"{bucket:<10}"
            f"{len(bucket_rows):>10}"
            f"{format_percent(stats_30['average']):>13}"
            f"{format_percent(stats_30['median']):>13}"
            f"{format_percent(stats_30['win_rate']):>13}"
            f"{format_percent(stats_90['average']):>13}"
            f"{format_percent(stats_90['median']):>13}"
            f"{format_percent(stats_90['win_rate']):>13}"
        )

    print()

    print(
        f"{'Score':<10}"
        f"{'180d N':>10}"
        f"{'180d Avg':>15}"
        f"{'180d Median':>15}"
        f"{'180d Win':>15}"
        f"{'Companies':>12}"
    )

    print("-" * 77)

    for bucket in [
        "0-1",
        "2-3",
        "4-5",
        "6+",
    ]:
        bucket_rows = groups[
            bucket
        ]

        stats = get_stats(
            bucket_rows,
            "180d",
        )

        companies = {
            row["ticker"]
            for row in bucket_rows
            if row.get("ticker")
        }

        print(
            f"{bucket:<10}"
            f"{stats['n']:>10}"
            f"{format_percent(stats['average']):>15}"
            f"{format_percent(stats['median']):>15}"
            f"{format_percent(stats['win_rate']):>15}"
            f"{len(companies):>12}"
        )


def group_by_exact_score(rows):
    groups = {}

    for row in rows:
        score = row[
            "signal_score"
        ]

        groups.setdefault(
            score,
            [],
        ).append(
            row
        )

    return groups


def print_exact_scores(
    title,
    rows,
):
    groups = group_by_exact_score(
        rows
    )

    print()
    print(title)
    print("=" * 100)

    print(
        f"{'Score':<10}"
        f"{'Events':>10}"
        f"{'180d N':>10}"
        f"{'Average':>15}"
        f"{'Median':>15}"
        f"{'Win Rate':>15}"
        f"{'Companies':>12}"
    )

    print("-" * 100)

    for score in sorted(
        groups.keys()
    ):
        score_rows = groups[
            score
        ]

        stats = get_stats(
            score_rows,
            "180d",
        )

        companies = {
            row["ticker"]
            for row in score_rows
            if row.get("ticker")
        }

        print(
            f"{score:<10}"
            f"{len(score_rows):>10}"
            f"{stats['n']:>10}"
            f"{format_percent(stats['average']):>15}"
            f"{format_percent(stats['median']):>15}"
            f"{format_percent(stats['win_rate']):>15}"
            f"{len(companies):>12}"
        )


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


def split_by_score_threshold(
    rows,
    threshold,
):
    high = []
    low = []

    for row in rows:
        score = row[
            "signal_score"
        ]

        if score >= threshold:
            high.append(
                row
            )
        else:
            low.append(
                row
            )

    return high, low


def print_sector_score_validation(
    title,
    rows,
    threshold,
):
    sectors = get_sector_groups(
        rows
    )

    high_label = (
        f"{threshold}+"
    )

    low_label = (
        f"0-{threshold - 1}"
    )

    print()
    print(title)
    print("#" * 150)

    print(
        f"Comparison: Score {high_label} "
        f"vs Score {low_label} "
        f"within each sector"
    )

    print()

    print(
        f"{'Sector':<28}"
        f"{'N High/Low':>13}"
        f"{'High Avg':>12}"
        f"{'Low Avg':>12}"
        f"{'Avg Lift':>12}"
        f"{'High Med':>12}"
        f"{'Low Med':>12}"
        f"{'Med Lift':>12}"
        f"{'High Win':>12}"
        f"{'Low Win':>12}"
        f"{'Win Lift':>12}"
    )

    print("-" * 150)

    ordered_sectors = sorted(
        sectors.items(),
        key=lambda item: (
            -len(item[1]),
            item[0],
        ),
    )

    for sector, sector_rows in (
        ordered_sectors
    ):
        high, low = (
            split_by_score_threshold(
                sector_rows,
                threshold,
            )
        )

        high_stats = get_stats(
            high,
            "180d",
        )

        low_stats = get_stats(
            low,
            "180d",
        )

        samples = (
            f"{high_stats['n']}"
            f" / "
            f"{low_stats['n']}"
        )

        average_lift = subtract_values(
            high_stats["average"],
            low_stats["average"],
        )

        median_lift = subtract_values(
            high_stats["median"],
            low_stats["median"],
        )

        win_lift = subtract_values(
            high_stats["win_rate"],
            low_stats["win_rate"],
        )

        print(
            f"{sector:<28}"
            f"{samples:>13}"
            f"{format_percent(high_stats['average']):>12}"
            f"{format_percent(low_stats['average']):>12}"
            f"{format_percent(average_lift):>12}"
            f"{format_percent(high_stats['median']):>12}"
            f"{format_percent(low_stats['median']):>12}"
            f"{format_percent(median_lift):>12}"
            f"{format_percent(high_stats['win_rate']):>12}"
            f"{format_percent(low_stats['win_rate']):>12}"
            f"{format_percent(win_lift):>12}"
        )


def print_overall_threshold_validation(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 110)

    print(
        f"{'Comparison':<24}"
        f"{'N High/Low':>14}"
        f"{'Avg Lift':>14}"
        f"{'Med Lift':>14}"
        f"{'Win Lift':>14}"
        f"{'High Avg':>14}"
        f"{'High Med':>14}"
    )

    print("-" * 110)

    for threshold in [
        3,
        4,
    ]:
        high, low = (
            split_by_score_threshold(
                rows,
                threshold,
            )
        )

        high_stats = get_stats(
            high,
            "180d",
        )

        low_stats = get_stats(
            low,
            "180d",
        )

        samples = (
            f"{high_stats['n']}"
            f" / "
            f"{low_stats['n']}"
        )

        comparison = (
            f"Score {threshold}+ vs "
            f"0-{threshold - 1}"
        )

        print(
            f"{comparison:<24}"
            f"{samples:>14}"
            f"{format_percent(subtract_values(high_stats['average'], low_stats['average'])):>14}"
            f"{format_percent(subtract_values(high_stats['median'], low_stats['median'])):>14}"
            f"{format_percent(subtract_values(high_stats['win_rate'], low_stats['win_rate'])):>14}"
            f"{format_percent(high_stats['average']):>14}"
            f"{format_percent(high_stats['median']):>14}"
        )


def print_score_rules():
    print()
    print(
        "CURRENT EXPERIMENTAL SCORE RULES"
    )

    print("=" * 68)

    print(
        "Revenue acceleration >= 20%     +2"
    )

    print(
        "Revenue growth >= 20%           +2"
    )

    print(
        "Revenue growth 10% to <20%      +1"
    )

    print(
        "EPS growth >= 20%               +2"
    )

    print(
        "EPS growth 10% to <20%          +1"
    )

    print()

    print(
        "Maximum score: 6"
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

    training, testing = split_by_time(
        rows
    )

    training = add_scores(
        training
    )

    testing = add_scores(
        testing
    )

    print()
    print(
        "HISTORICAL FINANCIAL SIGNAL SCORE TEST"
    )

    print_score_rules()

    print()
    print(
        "The score rules were selected from "
        "the prior training-period signal tests."
    )

    print(
        "The out-of-sample period is used "
        "only to validate the resulting score."
    )

    print_score_distribution(
        "TRAINING PERIOD - SCORE BUCKETS",
        training,
    )

    print_score_distribution(
        "OUT-OF-SAMPLE TEST PERIOD - SCORE BUCKETS",
        testing,
    )

    print_exact_scores(
        "TRAINING PERIOD - EXACT SCORES",
        training,
    )

    print_exact_scores(
        "OUT-OF-SAMPLE TEST PERIOD - EXACT SCORES",
        testing,
    )

    print()
    print(
        "OVERALL SCORE THRESHOLD VALIDATION"
    )

    print_overall_threshold_validation(
        "TRAINING PERIOD",
        training,
    )

    print_overall_threshold_validation(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )

    print()
    print(
        "WITHIN-SECTOR SCORE VALIDATION"
    )

    print_sector_score_validation(
        "TRAINING PERIOD - SCORE 3+",
        training,
        3,
    )

    print_sector_score_validation(
        "OUT-OF-SAMPLE TEST PERIOD - SCORE 3+",
        testing,
        3,
    )

    print_sector_score_validation(
        "TRAINING PERIOD - SCORE 4+",
        training,
        4,
    )

    print_sector_score_validation(
        "OUT-OF-SAMPLE TEST PERIOD - SCORE 4+",
        testing,
        4,
    )


if __name__ == "__main__":
    main()