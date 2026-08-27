from src.time_split_statistics import (
    format_percent,
    get_events,
    get_stats,
    get_strong_combination_events,
    split_by_time,
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


def group_by_sector(rows):
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


def print_sector_test(
    title,
    rows,
):
    strong_rows = (
        get_strong_combination_events(
            rows
        )
    )

    strong_ids = {
        (
            row["ticker"],
            row["entry_date"],
        )
        for row in strong_rows
    }

    sectors = group_by_sector(
        rows
    )

    print()
    print(title)
    print("=" * 150)

    print(
        "Strong signal:"
    )

    print(
        "Revenue acceleration >= 20% "
        "+ revenue growth >= 10% "
        "+ EPS growth > 0"
    )

    print()

    print(
        f"{'Sector':<28}"
        f"{'N Strong/Other':>16}"
        f"{'Strong Avg':>13}"
        f"{'Other Avg':>13}"
        f"{'Avg Lift':>13}"
        f"{'Strong Med':>13}"
        f"{'Other Med':>13}"
        f"{'Med Lift':>13}"
        f"{'Win Lift':>13}"
    )

    print("-" * 150)

    ordered = sorted(
        sectors.items(),
        key=lambda item: (
            -len(item[1]),
            item[0],
        ),
    )

    for sector, sector_rows in ordered:
        strong = []

        other = []

        for row in sector_rows:
            key = (
                row["ticker"],
                row["entry_date"],
            )

            if key in strong_ids:
                strong.append(
                    row
                )
            else:
                other.append(
                    row
                )

        strong_stats = get_stats(
            strong,
            "180d",
        )

        other_stats = get_stats(
            other,
            "180d",
        )

        samples = (
            f"{strong_stats['n']}"
            f" / "
            f"{other_stats['n']}"
        )

        average_lift = subtract_values(
            strong_stats["average"],
            other_stats["average"],
        )

        median_lift = subtract_values(
            strong_stats["median"],
            other_stats["median"],
        )

        win_lift = subtract_values(
            strong_stats["win_rate"],
            other_stats["win_rate"],
        )

        print(
            f"{sector:<28}"
            f"{samples:>16}"
            f"{format_percent(strong_stats['average']):>13}"
            f"{format_percent(other_stats['average']):>13}"
            f"{format_percent(average_lift):>13}"
            f"{format_percent(strong_stats['median']):>13}"
            f"{format_percent(other_stats['median']):>13}"
            f"{format_percent(median_lift):>13}"
            f"{format_percent(win_lift):>13}"
        )


def main():
    rows = get_events()

    training, testing = split_by_time(
        rows
    )

    print()
    print(
        "STRONG SIGNAL WITHIN-SECTOR TEST"
    )

    print_sector_test(
        "TRAINING PERIOD",
        training,
    )

    print_sector_test(
        "OUT-OF-SAMPLE TEST PERIOD",
        testing,
    )


if __name__ == "__main__":
    main()