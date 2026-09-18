from decimal import Decimal

from src.analysis.portfolio_history_candidate_report import (
    get_snapshot_months,
)
from src.analysis.portfolio_history_full_universe_simulation import (
    STARTING_VALUE,
    apply_return,
    build_period,
    format_money,
    format_percent,
)
from src.backtesting.time_split_statistics import (
    get_events,
)


CANDIDATE_UNIVERSE = "historical_sp500"

SECTOR_TESTS = (
    (
        "Baseline",
        set(),
    ),
    (
        "Without Technology",
        {
            "Technology",
        },
    ),
    (
        "Without Energy",
        {
            "Energy",
        },
    ),
    (
        "Without Technology + Energy",
        {
            "Technology",
            "Energy",
        },
    ),
)


def compound_with_sector_exclusions(
    periods,
    excluded_sectors,
):
    value = STARTING_VALUE
    periods_used = 0
    observations_used = 0

    period_results = []

    for period in periods:
        included_rows = [
            row
            for row in period[
                "candidate_returns"
            ]
            if row["sector"]
            not in excluded_sectors
        ]

        if not included_rows:
            period_results.append(
                {
                    "period":
                        (
                            f"{period['start_month']:%Y-%m}"
                            f" -> "
                            f"{period['end_month']:%Y-%m}"
                        ),
                    "count":
                        0,
                    "return_percent":
                        None,
                }
            )

            continue

        period_return = (
            sum(
                (
                    row["return_percent"]
                    for row in included_rows
                ),
                Decimal("0"),
            )
            / Decimal(
                len(included_rows)
            )
        )

        value = apply_return(
            value,
            period_return,
        )

        periods_used += 1

        observations_used += len(
            included_rows
        )

        period_results.append(
            {
                "period":
                    (
                        f"{period['start_month']:%Y-%m}"
                        f" -> "
                        f"{period['end_month']:%Y-%m}"
                    ),
                "count":
                    len(included_rows),
                "return_percent":
                    period_return,
            }
        )

    total_return = (
        (
            value
            / STARTING_VALUE
        )
        - Decimal("1")
    ) * Decimal("100")

    return {
        "ending_value":
            value,
        "return_percent":
            total_return,
        "periods_used":
            periods_used,
        "observations_used":
            observations_used,
        "period_results":
            period_results,
    }


def get_sector_counts(
    periods,
):
    counts = {}

    for period in periods:
        for row in period[
            "candidate_returns"
        ]:
            sector = (
                row["sector"]
                or "UNKNOWN"
            )

            counts[sector] = (
                counts.get(
                    sector,
                    0,
                )
                + 1
            )

    return sorted(
        counts.items(),
        key=lambda item: (
            item[1],
            item[0],
        ),
        reverse=True,
    )


def print_sector_counts(
    sector_counts,
):
    total = sum(
        count
        for _, count
        in sector_counts
    )

    print()
    print(
        "CANDIDATE OBSERVATIONS BY SECTOR"
    )

    print("=" * 100)

    print(
        f"{'Sector':<30}"
        f"{'Observations':>16}"
        f"{'Share':>14}"
    )

    print("-" * 100)

    for sector, count in sector_counts:
        share = (
            Decimal(count)
            / Decimal(total)
            * Decimal("100")
        )

        print(
            f"{sector:<30}"
            f"{count:>16}"
            f"{format_percent(
                share
            ):>14}"
        )

    print("-" * 100)

    print(
        f"{'Total':<30}"
        f"{total:>16}"
    )


def print_test_summary(
    results,
):
    print()
    print()
    print(
        "SECTOR EXCLUSION RESULTS"
    )

    print("=" * 120)

    print(
        f"{'Test':<32}"
        f"{'Observations':>16}"
        f"{'Periods':>10}"
        f"{'Ending Value':>20}"
        f"{'Compounded Return':>22}"
    )

    print("-" * 120)

    for label, result in results:
        print(
            f"{label:<32}"
            f"{result['observations_used']:>16}"
            f"{result['periods_used']:>10}"
            f"{format_money(
                result['ending_value']
            ):>20}"
            f"{format_percent(
                result['return_percent']
            ):>22}"
        )


def print_period_comparison(
    results,
):
    print()
    print()
    print(
        "PERIOD-BY-PERIOD SECTOR TEST"
    )

    print("=" * 150)

    labels = [
        label
        for label, _
        in results
    ]

    print(
        f"{'Period':<22}"
        + "".join(
            f"{label:>30}"
            for label in labels
        )
    )

    print("-" * 150)

    period_count = len(
        results[0][1][
            "period_results"
        ]
    )

    for index in range(
        period_count
    ):
        period_label = (
            results[0][1][
                "period_results"
            ][index]["period"]
        )

        line = (
            f"{period_label:<22}"
        )

        for _, result in results:
            period_result = (
                result[
                    "period_results"
                ][index]
            )

            if (
                period_result[
                    "return_percent"
                ]
                is None
            ):
                text = (
                    f"N={period_result['count']} "
                    f"N/A"
                )
            else:
                text = (
                    f"N={period_result['count']} "
                    f"{format_percent(
                        period_result[
                            'return_percent'
                        ]
                    )}"
                )

            line += (
                f"{text:>30}"
            )

        print(line)


def main():
    snapshot_months = (
        get_snapshot_months()
    )

    if len(snapshot_months) < 2:
        raise RuntimeError(
            "At least two Historical Portfolio "
            "snapshots are required."
        )

    events = get_events(
        CANDIDATE_UNIVERSE
    )

    periods = []

    for index in range(
        len(snapshot_months) - 1
    ):
        periods.append(
            build_period(
                events,
                snapshot_months[index],
                snapshot_months[
                    index + 1
                ],
            )
        )

    sector_counts = get_sector_counts(
        periods
    )

    results = []

    for (
        label,
        excluded_sectors,
    ) in SECTOR_TESTS:
        result = (
            compound_with_sector_exclusions(
                periods,
                excluded_sectors,
            )
        )

        results.append(
            (
                label,
                result,
            )
        )

    print()
    print(
        "FULL-UNIVERSE MARKET INTEL "
        "SECTOR CONCENTRATION TEST"
    )

    print("=" * 120)

    print(
        f"Candidate universe: "
        f"{CANDIDATE_UNIVERSE}"
    )

    print(
        f"Periods: "
        f"{len(periods)}"
    )

    print(
        f"Starting value: "
        f"{format_money(
            STARTING_VALUE
        )}"
    )

    print_sector_counts(
        sector_counts
    )

    print_test_summary(
        results
    )

    print_period_comparison(
        results
    )


if __name__ == "__main__":
    main()