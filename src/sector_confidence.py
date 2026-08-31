import sys

from src.time_split_statistics import (
    DEFAULT_UNIVERSE,
    get_events,
    get_stats,
    get_strong_combination_events,
    split_by_time,
)


MIN_TRAINING_EVENTS = 3
MIN_TEST_EVENTS = 3


def get_strong_sector_stats(
    rows,
    sector,
):
    strong_rows = (
        get_strong_combination_events(
            rows
        )
    )

    matching_rows = [
        row
        for row in strong_rows
        if (
            row.get("sector")
            or "UNKNOWN"
        ) == sector
    ]

    return get_stats(
        matching_rows,
        "180d",
    )


def stats_are_positive(stats):
    return (
        stats["average"] is not None
        and stats["median"] is not None
        and stats["average"] > 0
        and stats["median"] > 0
    )


def stats_are_negative(stats):
    return (
        stats["average"] is not None
        and stats["median"] is not None
        and stats["average"] < 0
        and stats["median"] < 0
    )


def classify_sector(
    training_stats,
    testing_stats,
):
    training_n = training_stats["n"]
    testing_n = testing_stats["n"]

    training_positive = (
        stats_are_positive(
            training_stats
        )
    )

    training_negative = (
        stats_are_negative(
            training_stats
        )
    )

    testing_positive = (
        stats_are_positive(
            testing_stats
        )
    )

    testing_negative = (
        stats_are_negative(
            testing_stats
        )
    )

    if (
        training_n < MIN_TRAINING_EVENTS
    ):
        return "No Evidence"

    if training_positive:
        if (
            testing_n >= MIN_TEST_EVENTS
            and testing_positive
        ):
            return "Supported"

        if (
            testing_n > 0
            and testing_negative
        ):
            return "Caution"

        return "Unconfirmed"

    if training_negative:
        if (
            testing_n >= MIN_TEST_EVENTS
            and testing_positive
        ):
            return "Mixed"

        return "Unsupported"

    return "Mixed"


def get_sector_confidence(
    training,
    testing,
    sector,
):
    training_stats = (
        get_strong_sector_stats(
            training,
            sector,
        )
    )

    testing_stats = (
        get_strong_sector_stats(
            testing,
            sector,
        )
    )

    label = classify_sector(
        training_stats,
        testing_stats,
    )

    return {
        "sector": sector,
        "label": label,

        "training_n":
            training_stats["n"],

        "training_average":
            training_stats["average"],

        "training_median":
            training_stats["median"],

        "training_win_rate":
            training_stats["win_rate"],

        "testing_n":
            testing_stats["n"],

        "testing_average":
            testing_stats["average"],

        "testing_median":
            testing_stats["median"],

        "testing_win_rate":
            testing_stats["win_rate"],
    }


def get_all_sectors(
    training,
    testing,
):
    sectors = set()

    for row in training + testing:
        sector = (
            row.get("sector")
            or "UNKNOWN"
        )

        sectors.add(
            sector
        )

    return sorted(
        sectors
    )


def get_all_sector_confidence(
    training,
    testing,
):
    results = []

    for sector in get_all_sectors(
        training,
        testing,
    ):
        results.append(
            get_sector_confidence(
                training,
                testing,
                sector,
            )
        )

    return results


def build_sector_confidence_map(
    training,
    testing,
):
    results = (
        get_all_sector_confidence(
            training,
            testing,
        )
    )

    return {
        result["sector"]: result
        for result in results
    }


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


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

    results = (
        get_all_sector_confidence(
            training,
            testing,
        )
    )

    print()
    print(
        "STRONG SIGNAL SECTOR CONFIDENCE"
    )

    print(
        "Signal: Revenue acceleration >= 20% "
        "+ revenue growth >= 10% "
        "+ EPS growth > 0"
    )

    print()

    print(
        "Training minimum:",
        MIN_TRAINING_EVENTS,
        "completed 180d events",
    )

    print(
        "Test minimum:",
        MIN_TEST_EVENTS,
        "completed 180d events",
    )

    print("=" * 150)

    print(
        f"{'Sector':<28}"
        f"{'Confidence':<14}"
        f"{'Train N':>9}"
        f"{'Train Avg':>12}"
        f"{'Train Med':>12}"
        f"{'Train Win':>12}"
        f"{'Test N':>9}"
        f"{'Test Avg':>12}"
        f"{'Test Med':>12}"
        f"{'Test Win':>12}"
    )

    print("-" * 150)

    for result in results:
        print(
            f"{result['sector']:<28}"
            f"{result['label']:<14}"

            f"{result['training_n']:>9}"

            f"{format_percent(
                result['training_average']
            ):>12}"

            f"{format_percent(
                result['training_median']
            ):>12}"

            f"{format_percent(
                result['training_win_rate']
            ):>12}"

            f"{result['testing_n']:>9}"

            f"{format_percent(
                result['testing_average']
            ):>12}"

            f"{format_percent(
                result['testing_median']
            ):>12}"

            f"{format_percent(
                result['testing_win_rate']
            ):>12}"
        )


if __name__ == "__main__":
    main()