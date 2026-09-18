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

REMOVE_COUNTS = (
    1,
    3,
    5,
    10,
)


def compound_period_returns(
    periods,
    excluded_observations=None,
    excluded_tickers=None,
):
    if excluded_observations is None:
        excluded_observations = set()

    if excluded_tickers is None:
        excluded_tickers = set()

    value = STARTING_VALUE
    periods_used = 0

    for period_index, period in enumerate(
        periods
    ):
        included_rows = []

        for row in period[
            "candidate_returns"
        ]:
            observation_key = (
                period_index,
                row["ticker"],
            )

            if (
                observation_key
                in excluded_observations
            ):
                continue

            if (
                row["ticker"]
                in excluded_tickers
            ):
                continue

            included_rows.append(
                row
            )

        if not included_rows:
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
    }


def get_observations(
    periods,
):
    observations = []

    for period_index, period in enumerate(
        periods
    ):
        for row in period[
            "candidate_returns"
        ]:
            observations.append(
                {
                    "period_index":
                        period_index,
                    "period":
                        (
                            f"{period['start_month']:%Y-%m}"
                            f" -> "
                            f"{period['end_month']:%Y-%m}"
                        ),
                    "ticker":
                        row["ticker"],
                    "priority":
                        row["priority"],
                    "score":
                        row["score"],
                    "sector":
                        row["sector"],
                    "return_percent":
                        row[
                            "return_percent"
                        ],
                }
            )

    return observations


def get_ticker_impacts(
    periods,
    baseline,
):
    tickers = sorted(
        {
            row["ticker"]
            for period in periods
            for row in period[
                "candidate_returns"
            ]
        }
    )

    results = []

    for ticker in tickers:
        result = compound_period_returns(
            periods,
            excluded_tickers={
                ticker
            },
        )

        impact = (
            baseline["return_percent"]
            - result["return_percent"]
        )

        results.append(
            {
                "ticker":
                    ticker,
                "without_return":
                    result[
                        "return_percent"
                    ],
                "impact":
                    impact,
            }
        )

    results.sort(
        key=lambda row: (
            row["impact"],
            row["ticker"],
        ),
        reverse=True,
    )

    return results


def print_baseline(
    periods,
    observations,
    baseline,
):
    print()
    print(
        "FULL-UNIVERSE MARKET INTEL "
        "CONCENTRATION TEST"
    )

    print("=" * 120)

    print(
        f"Periods: "
        f"{len(periods)}"
    )

    print(
        f"Candidate observations: "
        f"{len(observations)}"
    )

    print(
        f"Unique tickers: "
        f"{len({
            row['ticker']
            for row in observations
        })}"
    )

    print(
        f"Baseline ending value: "
        f"{format_money(
            baseline['ending_value']
        )}"
    )

    print(
        f"Baseline compounded return: "
        f"{format_percent(
            baseline['return_percent']
        )}"
    )


def print_top_observations(
    observations,
):
    ranked = sorted(
        observations,
        key=lambda row: (
            row["return_percent"],
            row["ticker"],
        ),
        reverse=True,
    )

    print()
    print()
    print(
        "TOP INDIVIDUAL "
        "CANDIDATE OBSERVATIONS"
    )

    print("=" * 120)

    print(
        f"{'Rank':>5}"
        f"{'Ticker':>10}"
        f"{'Period':>24}"
        f"{'Priority':>10}"
        f"{'Score':>8}"
        f"{'Sector':>24}"
        f"{'Return':>12}"
    )

    print("-" * 120)

    for rank, row in enumerate(
        ranked[:20],
        start=1,
    ):
        print(
            f"{rank:>5}"
            f"{row['ticker']:>10}"
            f"{row['period']:>24}"
            f"{row['priority']:>10}"
            f"{row['score']:>8}"
            f"{row['sector']:>24}"
            f"{format_percent(
                row['return_percent']
            ):>12}"
        )


def print_observation_removal_test(
    periods,
    observations,
):
    ranked = sorted(
        observations,
        key=lambda row: (
            row["return_percent"],
            row["ticker"],
        ),
        reverse=True,
    )

    print()
    print()
    print(
        "REMOVE BEST INDIVIDUAL "
        "OBSERVATIONS"
    )

    print("=" * 120)

    print(
        f"{'Removed':>10}"
        f"{'Ending Value':>20}"
        f"{'Compounded Return':>22}"
    )

    print("-" * 120)

    for remove_count in REMOVE_COUNTS:
        excluded = {
            (
                row["period_index"],
                row["ticker"],
            )
            for row in ranked[
                :remove_count
            ]
        }

        result = compound_period_returns(
            periods,
            excluded_observations=excluded,
        )

        print(
            f"{remove_count:>10}"
            f"{format_money(
                result['ending_value']
            ):>20}"
            f"{format_percent(
                result['return_percent']
            ):>22}"
        )


def print_ticker_impacts(
    ticker_impacts,
):
    print()
    print()
    print(
        "TICKER-LEVEL IMPACT"
    )

    print("=" * 120)

    print(
        "Impact = baseline compounded "
        "return minus compounded return "
        "when that ticker is excluded "
        "from every period."
    )

    print()

    print(
        f"{'Rank':>5}"
        f"{'Ticker':>10}"
        f"{'Without Ticker':>20}"
        f"{'Impact':>16}"
    )

    print("-" * 120)

    for rank, row in enumerate(
        ticker_impacts[:20],
        start=1,
    ):
        print(
            f"{rank:>5}"
            f"{row['ticker']:>10}"
            f"{format_percent(
                row['without_return']
            ):>20}"
            f"{format_percent(
                row['impact']
            ):>16}"
        )


def print_top_ticker_removal_test(
    periods,
    ticker_impacts,
):
    print()
    print()
    print(
        "REMOVE MOST HELPFUL "
        "TICKERS ENTIRELY"
    )

    print("=" * 120)

    print(
        f"{'Removed':>10}"
        f"{'Tickers':<55}"
        f"{'Ending Value':>18}"
        f"{'Return':>14}"
    )

    print("-" * 120)

    for remove_count in REMOVE_COUNTS:
        selected = (
            ticker_impacts[
                :remove_count
            ]
        )

        tickers = {
            row["ticker"]
            for row in selected
        }

        result = compound_period_returns(
            periods,
            excluded_tickers=tickers,
        )

        ticker_text = ", ".join(
            row["ticker"]
            for row in selected
        )

        print(
            f"{remove_count:>10}"
            f"{ticker_text:<55}"
            f"{format_money(
                result['ending_value']
            ):>18}"
            f"{format_percent(
                result['return_percent']
            ):>14}"
        )


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

    observations = get_observations(
        periods
    )

    baseline = compound_period_returns(
        periods
    )

    ticker_impacts = get_ticker_impacts(
        periods,
        baseline,
    )

    print_baseline(
        periods,
        observations,
        baseline,
    )

    print_top_observations(
        observations
    )

    print_observation_removal_test(
        periods,
        observations,
    )

    print_ticker_impacts(
        ticker_impacts
    )

    print_top_ticker_removal_test(
        periods,
        ticker_impacts,
    )


if __name__ == "__main__":
    main()