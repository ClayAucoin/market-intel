from decimal import Decimal

from src.analysis.portfolio_history_market_intel_comparison import (
    STARTING_VALUE,
    apply_return,
    build_transition,
    format_money,
    format_percent,
    get_snapshot_months,
    weighted_average,
)


REMOVE_COUNTS = [
    1,
    3,
    5,
    10,
]

TICKER_REMOVE_COUNTS = [
    1,
    3,
]


def get_priority_observations(
    transitions,
):
    observations = []

    for transition in transitions:
        for row in transition["rows"]:
            if (
                row["priority"] is None
                or row["priority"] < 3
                or row["return_percent"] is None
            ):
                continue

            observations.append(
                {
                    "start_month":
                        transition[
                            "start_month"
                        ],
                    "end_month":
                        transition[
                            "end_month"
                        ],
                    "ticker":
                        row["ticker"],
                    "market_value":
                        row["market_value"],
                    "return_percent":
                        row[
                            "return_percent"
                        ],
                }
            )

    return observations


def get_top_winners(
    observations,
):
    return sorted(
        observations,
        key=lambda row:
            row["return_percent"],
        reverse=True,
    )


def get_removed_keys(
    observations,
    remove_count,
):
    winners = get_top_winners(
        observations
    )

    return {
        (
            row["start_month"],
            row["end_month"],
            row["ticker"],
        )
        for row in winners[
            :remove_count
        ]
    }


def get_transition_priority_rows(
    transition,
    removed_keys=None,
    removed_tickers=None,
):
    if removed_keys is None:
        removed_keys = set()

    if removed_tickers is None:
        removed_tickers = set()

    rows = []

    for row in transition["rows"]:
        if (
            row["priority"] is None
            or row["priority"] < 3
            or row["return_percent"] is None
        ):
            continue

        if row["ticker"] in removed_tickers:
            continue

        key = (
            transition["start_month"],
            transition["end_month"],
            row["ticker"],
        )

        if key in removed_keys:
            continue

        rows.append(
            row
        )

    return rows


def compound_priority_strategy(
    transitions,
    removed_keys=None,
    removed_tickers=None,
):
    if removed_keys is None:
        removed_keys = set()

    if removed_tickers is None:
        removed_tickers = set()

    value = STARTING_VALUE
    periods_used = 0
    period_results = []

    for transition in transitions:
        rows = get_transition_priority_rows(
            transition,
            removed_keys,
            removed_tickers,
        )

        period_return = weighted_average(
            rows
        )

        if period_return is None:
            continue

        periods_used += 1

        value = apply_return(
            value,
            period_return,
        )

        period_results.append(
            {
                "start_month":
                    transition[
                        "start_month"
                    ],
                "end_month":
                    transition[
                        "end_month"
                    ],
                "count":
                    len(rows),
                "return_percent":
                    period_return,
                "ending_value":
                    value,
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
        "total_return":
            total_return,
        "periods_used":
            periods_used,
        "period_results":
            period_results,
    }


def get_ticker_names(
    observations,
):
    return sorted(
        {
            row["ticker"]
            for row in observations
        }
    )


def get_ticker_observation_count(
    observations,
    ticker,
):
    return sum(
        1
        for row in observations
        if row["ticker"] == ticker
    )


def build_ticker_impact_results(
    transitions,
    observations,
    baseline,
):
    results = []

    for ticker in get_ticker_names(
        observations
    ):
        stressed = (
            compound_priority_strategy(
                transitions,
                removed_tickers={
                    ticker
                },
            )
        )

        impact = (
            baseline["total_return"]
            - stressed["total_return"]
        )

        results.append(
            {
                "ticker":
                    ticker,
                "observations":
                    get_ticker_observation_count(
                        observations,
                        ticker,
                    ),
                "ending_value":
                    stressed[
                        "ending_value"
                    ],
                "total_return":
                    stressed[
                        "total_return"
                    ],
                "impact":
                    impact,
            }
        )

    return sorted(
        results,
        key=lambda row:
            row["impact"],
        reverse=True,
    )


def print_top_winners(
    observations,
):
    winners = get_top_winners(
        observations
    )

    print()
    print(
        "LARGEST PRIORITY 3+ "
        "WINNING OBSERVATIONS"
    )
    print("=" * 100)

    print(
        f"{'Rank':>4}  "
        f"{'Period':<22}"
        f"{'Ticker':<10}"
        f"{'Start Value':>15}"
        f"{'Return':>12}"
    )

    print("-" * 100)

    for index, row in enumerate(
        winners[:15],
        start=1,
    ):
        period = (
            f"{row['start_month']:%Y-%m}"
            f" -> "
            f"{row['end_month']:%Y-%m}"
        )

        print(
            f"{index:>4}  "
            f"{period:<22}"
            f"{row['ticker']:<10}"
            f"{format_money(
                row['market_value']
            ):>15}"
            f"{format_percent(
                row['return_percent']
            ):>12}"
        )


def print_baseline(
    transitions,
):
    result = compound_priority_strategy(
        transitions
    )

    print()
    print()
    print(
        "BASELINE PRIORITY 3+"
    )
    print("=" * 100)

    print(
        f"Periods used: "
        f"{result['periods_used']}"
    )

    print(
        f"Starting value: "
        f"{format_money(
            STARTING_VALUE
        )}"
    )

    print(
        f"Ending value: "
        f"{format_money(
            result['ending_value']
        )}"
    )

    print(
        f"Compounded return: "
        f"{format_percent(
            result['total_return']
        )}"
    )

    return result


def print_removal_test(
    transitions,
    observations,
    baseline,
):
    print()
    print()
    print(
        "TOP-WINNER REMOVAL STRESS TEST"
    )
    print("=" * 100)

    print(
        f"{'Removed':>10}"
        f"{'Ending Value':>18}"
        f"{'Return':>14}"
        f"{'Change vs Base':>18}"
        f"{'Periods':>10}"
    )

    print("-" * 100)

    for remove_count in REMOVE_COUNTS:
        removed_keys = get_removed_keys(
            observations,
            remove_count,
        )

        result = compound_priority_strategy(
            transitions,
            removed_keys,
        )

        change_vs_base = (
            result["total_return"]
            - baseline["total_return"]
        )

        print(
            f"{remove_count:>10}"
            f"{format_money(
                result['ending_value']
            ):>18}"
            f"{format_percent(
                result['total_return']
            ):>14}"
            f"{format_percent(
                change_vs_base
            ):>18}"
            f"{result['periods_used']:>10}"
        )


def print_period_concentration(
    transitions,
):
    print()
    print()
    print(
        "PRIORITY 3+ PERIOD CONCENTRATION"
    )
    print("=" * 100)

    print(
        f"{'Period':<22}"
        f"{'N':>5}"
        f"{'Best Ticker':>14}"
        f"{'Best Return':>15}"
        f"{'Period Return':>17}"
    )

    print("-" * 100)

    for transition in transitions:
        rows = get_transition_priority_rows(
            transition
        )

        if not rows:
            continue

        best = max(
            rows,
            key=lambda row:
                row["return_percent"],
        )

        period_return = weighted_average(
            rows
        )

        period = (
            f"{transition['start_month']:%Y-%m}"
            f" -> "
            f"{transition['end_month']:%Y-%m}"
        )

        print(
            f"{period:<22}"
            f"{len(rows):>5}"
            f"{best['ticker']:>14}"
            f"{format_percent(
                best['return_percent']
            ):>15}"
            f"{format_percent(
                period_return
            ):>17}"
        )


def print_ticker_impact(
    ticker_results,
):
    print()
    print()
    print(
        "PRIORITY 3+ TICKER-LEVEL IMPACT"
    )
    print("=" * 100)

    print(
        "Each row removes that ticker from "
        "every period in which it was "
        "Priority 3+."
    )

    print()

    print(
        f"{'Rank':>4}  "
        f"{'Ticker':<10}"
        f"{'Obs':>6}"
        f"{'Return Without':>18}"
        f"{'Impact':>14}"
        f"{'Ending Value':>18}"
    )

    print("-" * 100)

    for index, row in enumerate(
        ticker_results,
        start=1,
    ):
        print(
            f"{index:>4}  "
            f"{row['ticker']:<10}"
            f"{row['observations']:>6}"
            f"{format_percent(
                row['total_return']
            ):>18}"
            f"{format_percent(
                row['impact']
            ):>14}"
            f"{format_money(
                row['ending_value']
            ):>18}"
        )


def print_ticker_removal_stress(
    transitions,
    ticker_results,
    baseline,
):
    print()
    print()
    print(
        "MOST-INFLUENTIAL-TICKER "
        "REMOVAL STRESS TEST"
    )
    print("=" * 100)

    print(
        f"{'Removed':>10}"
        f"{'Tickers':<36}"
        f"{'Ending Value':>18}"
        f"{'Return':>14}"
        f"{'Change vs Base':>18}"
    )

    print("-" * 100)

    for remove_count in (
        TICKER_REMOVE_COUNTS
    ):
        selected = ticker_results[
            :remove_count
        ]

        removed_tickers = {
            row["ticker"]
            for row in selected
        }

        result = compound_priority_strategy(
            transitions,
            removed_tickers=
                removed_tickers,
        )

        change_vs_base = (
            result["total_return"]
            - baseline["total_return"]
        )

        ticker_text = ", ".join(
            row["ticker"]
            for row in selected
        )

        print(
            f"{remove_count:>10}"
            f"{ticker_text:<36}"
            f"{format_money(
                result['ending_value']
            ):>18}"
            f"{format_percent(
                result['total_return']
            ):>14}"
            f"{format_percent(
                change_vs_base
            ):>18}"
        )


def build_transitions():
    snapshot_months = (
        get_snapshot_months()
    )

    if len(snapshot_months) < 2:
        raise RuntimeError(
            "At least two Historical Portfolio "
            "snapshots are required."
        )

    transitions = []

    for index in range(
        len(snapshot_months) - 1
    ):
        transitions.append(
            build_transition(
                snapshot_months[index],
                snapshot_months[
                    index + 1
                ],
            )
        )

    return transitions


def main():
    transitions = build_transitions()

    observations = (
        get_priority_observations(
            transitions
        )
    )

    print(
        "MARKET-INTEL PRIORITY 3+ "
        "CONCENTRATION STRESS TEST"
    )
    print("=" * 100)

    print(
        f"Priority 3+ observations: "
        f"{len(observations)}"
    )

    print_top_winners(
        observations
    )

    baseline = print_baseline(
        transitions
    )

    print_removal_test(
        transitions,
        observations,
        baseline,
    )

    print_period_concentration(
        transitions
    )

    ticker_results = (
        build_ticker_impact_results(
            transitions,
            observations,
            baseline,
        )
    )

    print_ticker_impact(
        ticker_results
    )

    print_ticker_removal_stress(
        transitions,
        ticker_results,
        baseline,
    )


if __name__ == "__main__":
    main()