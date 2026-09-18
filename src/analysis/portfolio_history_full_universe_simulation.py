from decimal import Decimal

from src.analysis.portfolio_history_candidate_report import (
    get_candidates,
    get_snapshot_months,
)
from src.analysis.portfolio_history_market_intel_comparison import (
    STARTING_VALUE,
    actual_portfolio_return,
    format_money,
    format_percent,
    get_price_return,
)
from src.analysis.portfolio_history_snapshot_report import (
    build_analysis,
    get_snapshot,
)
from src.analysis.portfolio_history_stock_performance import (
    get_daily_price_columns,
)
from src.backtesting.time_split_statistics import (
    get_events,
)
from src.database import get_connection


CANDIDATE_UNIVERSE = "historical_sp500"


def get_candidate_returns(
    candidates,
    start_date,
    end_date,
):
    rows = []

    with get_connection() as conn:
        with conn.cursor() as cursor:
            (
                date_column,
                price_column,
            ) = get_daily_price_columns(
                cursor
            )

            for candidate in candidates:
                price_result = get_price_return(
                    cursor,
                    candidate["ticker"],
                    start_date,
                    end_date,
                    date_column,
                    price_column,
                )

                if price_result is None:
                    continue

                rows.append(
                    {
                        **candidate,
                        "return_percent":
                            price_result[
                                "return_percent"
                            ],
                        "start_price_date":
                            price_result[
                                "start_price_date"
                            ],
                        "end_price_date":
                            price_result[
                                "end_price_date"
                            ],
                    }
                )

    return rows


def equal_weight_return(rows):
    if not rows:
        return None

    total = sum(
        (
            row["return_percent"]
            for row in rows
        ),
        Decimal("0"),
    )

    return (
        total
        / Decimal(len(rows))
    )


def get_actual_return(
    snapshot_month,
    end_date,
):
    (
        start_snapshot,
        results,
        _,
    ) = build_analysis(
        snapshot_month
    )

    rows = []

    with get_connection() as conn:
        with conn.cursor() as cursor:
            (
                date_column,
                price_column,
            ) = get_daily_price_columns(
                cursor
            )

            for item in results:
                price_result = get_price_return(
                    cursor,
                    item["ticker"],
                    start_snapshot[
                        "as_of_date"
                    ],
                    end_date,
                    date_column,
                    price_column,
                )

                if price_result is None:
                    return_percent = None
                else:
                    return_percent = (
                        price_result[
                            "return_percent"
                        ]
                    )

                rows.append(
                    {
                        "ticker":
                            item["ticker"],
                        "market_value":
                            item["market_value"],
                        "return_percent":
                            return_percent,
                    }
                )

    return actual_portfolio_return(
        rows,
        start_snapshot["cash"],
    )


def apply_return(
    value,
    return_percent,
):
    if return_percent is None:
        return value

    return (
        value
        * (
            Decimal("1")
            + (
                return_percent
                / Decimal("100")
            )
        )
    )


def build_period(
    events,
    start_month,
    end_month,
):
    start_snapshot = get_snapshot(
        start_month
    )

    end_snapshot = get_snapshot(
        end_month
    )

    start_date = start_snapshot[
        "as_of_date"
    ]

    end_date = end_snapshot[
        "as_of_date"
    ]

    (
        candidates,
        member_count,
        latest_event_count,
    ) = get_candidates(
        events,
        start_date,
    )

    candidate_returns = (
        get_candidate_returns(
            candidates,
            start_date,
            end_date,
        )
    )

    market_intel_return = (
        equal_weight_return(
            candidate_returns
        )
    )

    actual_return = get_actual_return(
        start_month,
        end_date,
    )

    difference = None

    if (
        market_intel_return is not None
        and actual_return is not None
    ):
        difference = (
            market_intel_return
            - actual_return
        )

    return {
        "start_month":
            start_month,
        "end_month":
            end_month,
        "start_date":
            start_date,
        "end_date":
            end_date,
        "as_of_source":
            start_snapshot[
                "as_of_source"
            ],
        "member_count":
            member_count,
        "latest_event_count":
            latest_event_count,
        "candidate_count":
            len(candidates),
        "measured_count":
            len(candidate_returns),
        "candidate_returns":
            candidate_returns,
        "market_intel_return":
            market_intel_return,
        "actual_return":
            actual_return,
        "difference":
            difference,
    }


def print_period(
    period,
):
    print()
    print("=" * 120)

    print(
        f"{period['start_month']:%Y-%m}"
        f" -> "
        f"{period['end_month']:%Y-%m}"
    )

    print(
        f"Analysis date: "
        f"{period['start_date']}"
    )

    print(
        f"Observation date: "
        f"{period['end_date']}"
    )

    print(
        f"As-of source: "
        f"{period['as_of_source']}"
    )

    print(
        f"S&P 500 members: "
        f"{period['member_count']}"
    )

    print(
        f"Companies with latest event: "
        f"{period['latest_event_count']}"
    )

    print(
        f"Priority 3+ candidates: "
        f"{period['candidate_count']}"
    )

    print(
        f"Candidates with measured return: "
        f"{period['measured_count']}"
    )

    print("-" * 120)

    print(
        f"Market Intel equal-weight return: "
        f"{format_percent(
            period['market_intel_return']
        )}"
    )

    print(
        f"Actual portfolio return: "
        f"{format_percent(
            period['actual_return']
        )}"
    )

    print(
        f"Market Intel vs actual: "
        f"{format_percent(
            period['difference']
        )}"
    )


def print_compounded_summary(
    periods,
):
    market_intel_value = (
        STARTING_VALUE
    )

    actual_value = (
        STARTING_VALUE
    )

    periods_used = 0

    print()
    print()
    print(
        "COMPOUNDED FULL-UNIVERSE "
        "SIMULATION"
    )

    print("=" * 120)

    print(
        f"{'Period':<22}"
        f"{'MI Return':>14}"
        f"{'Actual':>14}"
        f"{'Difference':>14}"
        f"{'MI Value':>16}"
        f"{'Actual Value':>16}"
    )

    print("-" * 120)

    for period in periods:
        market_intel_return = (
            period[
                "market_intel_return"
            ]
        )

        actual_return = (
            period[
                "actual_return"
            ]
        )

        if (
            market_intel_return is None
            or actual_return is None
        ):
            continue

        periods_used += 1

        market_intel_value = (
            apply_return(
                market_intel_value,
                market_intel_return,
            )
        )

        actual_value = apply_return(
            actual_value,
            actual_return,
        )

        period_label = (
            f"{period['start_month']:%Y-%m}"
            f" -> "
            f"{period['end_month']:%Y-%m}"
        )

        print(
            f"{period_label:<22}"
            f"{format_percent(
                market_intel_return
            ):>14}"
            f"{format_percent(
                actual_return
            ):>14}"
            f"{format_percent(
                period['difference']
            ):>14}"
            f"{format_money(
                market_intel_value
            ):>16}"
            f"{format_money(
                actual_value
            ):>16}"
        )

    market_intel_total_return = (
        (
            market_intel_value
            / STARTING_VALUE
        )
        - Decimal("1")
    ) * Decimal("100")

    actual_total_return = (
        (
            actual_value
            / STARTING_VALUE
        )
        - Decimal("1")
    ) * Decimal("100")

    return_difference = (
        market_intel_total_return
        - actual_total_return
    )

    dollar_difference = (
        market_intel_value
        - actual_value
    )

    print("-" * 120)

    print(
        f"Periods compared: "
        f"{periods_used}"
    )

    print(
        f"Starting value: "
        f"{format_money(
            STARTING_VALUE
        )}"
    )

    print()

    print(
        f"Market Intel ending value: "
        f"{format_money(
            market_intel_value
        )}"
    )

    print(
        f"Market Intel compounded return: "
        f"{format_percent(
            market_intel_total_return
        )}"
    )

    print()

    print(
        f"Actual portfolio ending value: "
        f"{format_money(
            actual_value
        )}"
    )

    print(
        f"Actual portfolio compounded return: "
        f"{format_percent(
            actual_total_return
        )}"
    )

    print()

    print(
        f"Market Intel vs actual "
        f"return difference: "
        f"{format_percent(
            return_difference
        )}"
    )

    print(
        f"Market Intel vs actual "
        f"dollar difference on $10,000: "
        f"{format_money(
            dollar_difference
        )}"
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

    print()
    print(
        "HISTORICAL PORTFOLIO "
        "FULL-UNIVERSE MARKET INTEL "
        "SIMULATION"
    )

    print("=" * 120)

    print(
        f"Candidate universe: "
        f"{CANDIDATE_UNIVERSE}"
    )

    print(
        "Strategy: Equal weight all "
        "Priority 3+ candidates"
    )

    print(
        f"Starting comparison value: "
        f"{format_money(
            STARTING_VALUE
        )}"
    )

    periods = []

    for index in range(
        len(snapshot_months) - 1
    ):
        period = build_period(
            events,
            snapshot_months[index],
            snapshot_months[
                index + 1
            ],
        )

        periods.append(
            period
        )

        print_period(
            period
        )

    print_compounded_summary(
        periods
    )


if __name__ == "__main__":
    main()