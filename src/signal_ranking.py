from decimal import Decimal
import sys

from src.time_split_statistics import (
    DEFAULT_UNIVERSE,
    format_percent,
    get_events,
    get_stats,
    split_by_time,
)


HORIZON = "180d"


SIGNAL_TESTS = [
    {
        "name": "Revenue Growth > 0%",
        "field": "revenue_yoy",
        "operator": ">",
        "threshold": Decimal("0"),
    },
    {
        "name": "Revenue Growth >= 10%",
        "field": "revenue_yoy",
        "operator": ">=",
        "threshold": Decimal("10"),
    },
    {
        "name": "Revenue Growth >= 20%",
        "field": "revenue_yoy",
        "operator": ">=",
        "threshold": Decimal("20"),
    },
    {
        "name": "Revenue Acceleration > 0%",
        "field": "revenue_acceleration",
        "operator": ">",
        "threshold": Decimal("0"),
    },
    {
        "name": "Revenue Acceleration >= 10%",
        "field": "revenue_acceleration",
        "operator": ">=",
        "threshold": Decimal("10"),
    },
    {
        "name": "Revenue Acceleration >= 20%",
        "field": "revenue_acceleration",
        "operator": ">=",
        "threshold": Decimal("20"),
    },
    {
        "name": "EPS Growth > 0%",
        "field": "eps_yoy",
        "operator": ">",
        "threshold": Decimal("0"),
    },
    {
        "name": "EPS Growth >= 10%",
        "field": "eps_yoy",
        "operator": ">=",
        "threshold": Decimal("10"),
    },
    {
        "name": "EPS Growth >= 20%",
        "field": "eps_yoy",
        "operator": ">=",
        "threshold": Decimal("20"),
    },
    {
        "name": "Gross Margin Improving",
        "field": "gross_margin_change",
        "operator": ">",
        "threshold": Decimal("0"),
    },
    {
        "name": "Operating Margin Improving",
        "field": "operating_margin_change",
        "operator": ">",
        "threshold": Decimal("0"),
    },
]


def matches_signal(row, signal):
    value = row.get(
        signal["field"]
    )

    if value is None:
        return False

    threshold = signal[
        "threshold"
    ]

    operator = signal[
        "operator"
    ]

    if operator == ">":
        return value > threshold

    if operator == ">=":
        return value >= threshold

    raise ValueError(
        f"Unknown operator: {operator}"
    )


def split_signal_groups(
    rows,
    signal,
):
    matching = []
    nonmatching = []

    for row in rows:
        value = row.get(
            signal["field"]
        )

        if value is None:
            continue

        if matches_signal(
            row,
            signal,
        ):
            matching.append(
                row
            )
        else:
            nonmatching.append(
                row
            )

    return matching, nonmatching


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


def analyze_signal(
    rows,
    signal,
):
    matching, nonmatching = (
        split_signal_groups(
            rows,
            signal,
        )
    )

    match_stats = get_stats(
        matching,
        HORIZON,
    )

    nonmatch_stats = get_stats(
        nonmatching,
        HORIZON,
    )

    return {
        "name":
            signal["name"],

        "match_n":
            match_stats["n"],

        "nonmatch_n":
            nonmatch_stats["n"],

        "match_average":
            match_stats["average"],

        "nonmatch_average":
            nonmatch_stats["average"],

        "average_lift":
            difference(
                match_stats["average"],
                nonmatch_stats["average"],
            ),

        "match_median":
            match_stats["median"],

        "nonmatch_median":
            nonmatch_stats["median"],

        "median_lift":
            difference(
                match_stats["median"],
                nonmatch_stats["median"],
            ),

        "match_win_rate":
            match_stats["win_rate"],

        "nonmatch_win_rate":
            nonmatch_stats["win_rate"],

        "win_rate_lift":
            difference(
                match_stats["win_rate"],
                nonmatch_stats["win_rate"],
            ),
    }


def analyze_all_signals(rows):
    return [
        analyze_signal(
            rows,
            signal,
        )
        for signal in SIGNAL_TESTS
    ]


def clamp(
    value,
    minimum,
    maximum,
):
    if value < minimum:
        return minimum

    if value > maximum:
        return maximum

    return value


def calculate_sample_score(
    match_n,
):
    if match_n <= 0:
        return Decimal("0")

    score = (
        Decimal(match_n)
        / Decimal("200")
        * Decimal("100")
    )

    return clamp(
        score,
        Decimal("0"),
        Decimal("100"),
    )


def calculate_component_score(
    value,
    full_score_value,
):
    if value is None:
        return Decimal("0")

    score = (
        value
        / full_score_value
        * Decimal("100")
    )

    return clamp(
        score,
        Decimal("-100"),
        Decimal("100"),
    )


def calculate_quality_score(result):
    average_score = (
        calculate_component_score(
            result["average_lift"],
            Decimal("10"),
        )
    )

    median_score = (
        calculate_component_score(
            result["median_lift"],
            Decimal("7.5"),
        )
    )

    win_score = (
        calculate_component_score(
            result["win_rate_lift"],
            Decimal("10"),
        )
    )

    sample_score = (
        calculate_sample_score(
            result["match_n"]
        )
    )

    quality_score = (
        average_score
        * Decimal("0.35")

        + median_score
        * Decimal("0.30")

        + win_score
        * Decimal("0.20")

        + sample_score
        * Decimal("0.15")
    )

    return round(
        quality_score,
        2,
    )


def add_quality_scores(results):
    scored = []

    for result in results:
        scored_result = dict(
            result
        )

        scored_result[
            "quality_score"
        ] = calculate_quality_score(
            result
        )

        scored.append(
            scored_result
        )

    return scored


def rank_training_signals(training):
    results = analyze_all_signals(
        training
    )

    scored = add_quality_scores(
        results
    )

    return sorted(
        scored,
        key=lambda result:
            result["quality_score"],
        reverse=True,
    )


def get_signal_by_name(name):
    for signal in SIGNAL_TESTS:
        if signal["name"] == name:
            return signal

    raise ValueError(
        f"Signal not found: {name}"
    )


def analyze_testing_in_training_order(
    testing,
    training_ranking,
):
    results = []

    for training_result in (
        training_ranking
    ):
        signal = get_signal_by_name(
            training_result["name"]
        )

        testing_result = (
            analyze_signal(
                testing,
                signal,
            )
        )

        testing_result[
            "quality_score"
        ] = calculate_quality_score(
            testing_result
        )

        results.append(
            testing_result
        )

    return results


def get_validation_status(
    training,
    testing,
):
    positive_train = (
        training["average_lift"] is not None
        and training["average_lift"] > 0

        and training["median_lift"] is not None
        and training["median_lift"] > 0
    )

    positive_test = (
        testing["average_lift"] is not None
        and testing["average_lift"] > 0

        and testing["median_lift"] is not None
        and testing["median_lift"] > 0
    )

    if (
        positive_train
        and positive_test
    ):
        return "PASS"

    if positive_test:
        return "MIXED"

    return "FAIL"


def print_quality_ranking(
    title,
    results,
):
    print()
    print(title)
    print("=" * 158)

    print(
        f"{'Rank':<6}"
        f"{'Signal':<32}"
        f"{'N Yes/No':>12}"
        f"{'Avg Lift':>12}"
        f"{'Med Lift':>12}"
        f"{'Win Lift':>12}"
        f"{'Quality':>12}"
        f"{'Yes Avg':>12}"
        f"{'Yes Med':>12}"
        f"{'Yes Win':>12}"
    )

    print("-" * 158)

    for index, result in enumerate(
        results,
        start=1,
    ):
        samples = (
            f"{result['match_n']}"
            f" / "
            f"{result['nonmatch_n']}"
        )

        print(
            f"{index:<6}"
            f"{result['name']:<32}"
            f"{samples:>12}"
            f"{format_percent(result['average_lift']):>12}"
            f"{format_percent(result['median_lift']):>12}"
            f"{format_percent(result['win_rate_lift']):>12}"
            f"{result['quality_score']:>12.2f}"
            f"{format_percent(result['match_average']):>12}"
            f"{format_percent(result['match_median']):>12}"
            f"{format_percent(result['match_win_rate']):>12}"
        )


def print_validation_summary(
    training_results,
    testing_results,
):
    print()
    print(
        "TRAINING QUALITY RANKING VS "
        "OUT-OF-SAMPLE VALIDATION"
    )

    print("=" * 148)

    print(
        f"{'Rank':<6}"
        f"{'Signal':<32}"
        f"{'Train Q':>10}"
        f"{'Test Q':>10}"
        f"{'Train Avg':>12}"
        f"{'Test Avg':>12}"
        f"{'Train Med':>12}"
        f"{'Test Med':>12}"
        f"{'Test N':>9}"
        f"{'Status':>10}"
    )

    print("-" * 148)

    for index, (
        training,
        testing,
    ) in enumerate(
        zip(
            training_results,
            testing_results,
        ),
        start=1,
    ):
        status = get_validation_status(
            training,
            testing,
        )

        print(
            f"{index:<6}"
            f"{training['name']:<32}"
            f"{training['quality_score']:>10.2f}"
            f"{testing['quality_score']:>10.2f}"
            f"{format_percent(training['average_lift']):>12}"
            f"{format_percent(testing['average_lift']):>12}"
            f"{format_percent(training['median_lift']):>12}"
            f"{format_percent(testing['median_lift']):>12}"
            f"{testing['match_n']:>9}"
            f"{status:>10}"
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

    training_ranking = (
        rank_training_signals(
            training
        )
    )

    testing_results = (
        analyze_testing_in_training_order(
            testing,
            training_ranking,
        )
    )

    print()
    print(
        "FINANCIAL SIGNAL QUALITY TEST"
    )

    print(
        "Ranking horizon:",
        HORIZON,
    )

    print()

    print(
        "Training quality score weights:"
    )

    print(
        "  Average lift:  35%"
    )

    print(
        "  Median lift:   30%"
    )

    print(
        "  Win-rate lift: 20%"
    )

    print(
        "  Sample size:   15%"
    )

    print()

    print(
        "Training data alone determines "
        "the ranking."
    )

    print(
        "Out-of-sample results are used "
        "only for validation."
    )

    print_quality_ranking(
        "TRAINING PERIOD QUALITY RANKING",
        training_ranking,
    )

    print_quality_ranking(
        "OUT-OF-SAMPLE RESULTS "
        "IN TRAINING RANK ORDER",
        testing_results,
    )

    print_validation_summary(
        training_ranking,
        testing_results,
    )


if __name__ == "__main__":
    main()