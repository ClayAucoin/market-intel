from decimal import Decimal

from src.backtesting.backtester import (
    backtest_financial_event,
)

from src.database import get_connection

from src.analysis.event_timing import (
    get_financial_events,
)


TICKER = "DELL"
BENCHMARK = "SPY"

MAX_REPORTING_LAG_DAYS = 120


def get_company_id(ticker):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id

                FROM companies

                WHERE UPPER(ticker) =
                      UPPER(%s)

                LIMIT 1;
                """,
                (ticker,),
            )

            row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"Company not found: {ticker}"
        )

    return row[0]


def get_metric_history(
    company_id,
    metric,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    period_end,
                    fiscal_year,
                    fiscal_period,
                    value,
                    filed_date,
                    accession_number,
                    is_derived

                FROM financial_facts

                WHERE company_id = %s
                  AND metric = %s

                ORDER BY period_end;
                """,
                (
                    company_id,
                    metric,
                ),
            )

            rows = cursor.fetchall()

    return [
        {
            "period_end": row[0],
            "fiscal_year": row[1],
            "fiscal_period": row[2],
            "value": Decimal(row[3]),
            "filed_date": row[4],
            "accession_number": row[5],
            "is_derived": row[6],
        }
        for row in rows
    ]


def get_period_record(
    history,
    period_end,
):
    for item in history:
        if (
            item["period_end"]
            == period_end
        ):
            return item

    return None


def find_same_period_last_year(
    history,
    current,
):
    candidates = []

    for item in history:
        if (
            item["period_end"]
            >= current["period_end"]
        ):
            continue

        difference = (
            current["period_end"]
            - item["period_end"]
        ).days

        if 330 <= difference <= 400:
            candidates.append(
                (
                    abs(
                        difference - 365
                    ),
                    item,
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[0][1]


def calculate_percent_change(
    current,
    previous,
):
    if (
        current is None
        or previous is None
        or previous == 0
    ):
        return None

    result = (
        (current - previous)
        / abs(previous)
    ) * Decimal("100")

    return round(
        result,
        2,
    )


def calculate_margin(
    numerator,
    revenue,
):
    if (
        numerator is None
        or revenue is None
        or revenue == 0
    ):
        return None

    result = (
        numerator
        / revenue
    ) * Decimal("100")

    return round(
        result,
        2,
    )


def get_yoy_growth(
    history,
    current,
):
    previous = (
        find_same_period_last_year(
            history,
            current,
        )
    )

    if previous is None:
        return None

    return calculate_percent_change(
        current["value"],
        previous["value"],
    )


def get_previous_quarter(
    history,
    current,
):
    previous = [
        item
        for item in history
        if (
            item["period_end"]
            < current["period_end"]
        )
    ]

    if not previous:
        return None

    return previous[-1]


def get_growth_acceleration(
    history,
    current,
):
    current_growth = get_yoy_growth(
        history,
        current,
    )

    previous_quarter = (
        get_previous_quarter(
            history,
            current,
        )
    )

    if previous_quarter is None:
        return None

    previous_growth = get_yoy_growth(
        history,
        previous_quarter,
    )

    if (
        current_growth is None
        or previous_growth is None
    ):
        return None

    return round(
        current_growth
        - previous_growth,
        2,
    )


def get_margin_change(
    numerator_history,
    revenue_history,
    current_period_end,
):
    numerator_current = (
        get_period_record(
            numerator_history,
            current_period_end,
        )
    )

    revenue_current = (
        get_period_record(
            revenue_history,
            current_period_end,
        )
    )

    if (
        numerator_current is None
        or revenue_current is None
    ):
        return None

    numerator_previous = (
        find_same_period_last_year(
            numerator_history,
            numerator_current,
        )
    )

    revenue_previous = (
        find_same_period_last_year(
            revenue_history,
            revenue_current,
        )
    )

    if (
        numerator_previous is None
        or revenue_previous is None
    ):
        return None

    current_margin = calculate_margin(
        numerator_current["value"],
        revenue_current["value"],
    )

    previous_margin = calculate_margin(
        numerator_previous["value"],
        revenue_previous["value"],
    )

    if (
        current_margin is None
        or previous_margin is None
    ):
        return None

    return round(
        current_margin
        - previous_margin,
        2,
    )


def get_excess_return(
    backtest,
    horizon,
):
    if backtest is None:
        return None

    comparison = (
        backtest[
            "comparisons"
        ].get(horizon)
    )

    if comparison is None:
        return None

    return comparison[
        "excess_return"
    ]


def is_current_reporting_event(event):
    if (
        event["period_end"] is None
        or event["filed_date"] is None
    ):
        return False

    reporting_lag = (
        event["filed_date"]
        - event["period_end"]
    ).days

    if reporting_lag < 0:
        return False

    if (
        reporting_lag
        > MAX_REPORTING_LAG_DAYS
    ):
        return False

    return True


def build_historical_backtest(
    ticker,
    benchmark,
):
    company_id = get_company_id(
        ticker
    )

    revenue_history = (
        get_metric_history(
            company_id,
            "revenue",
        )
    )

    eps_history = (
        get_metric_history(
            company_id,
            "diluted_eps",
        )
    )

    gross_profit_history = (
        get_metric_history(
            company_id,
            "gross_profit",
        )
    )

    operating_income_history = (
        get_metric_history(
            company_id,
            "operating_income",
        )
    )

    revenue_events = (
        get_financial_events(
            ticker,
            "revenue",
        )
    )

    results = []

    for event in revenue_events:
        #
        # Ignore historical comparative facts
        # that first appeared long after the
        # financial period actually ended.
        #
        if not is_current_reporting_event(
            event
        ):
            continue

        revenue = get_period_record(
            revenue_history,
            event["period_end"],
        )

        if revenue is None:
            continue

        eps = get_period_record(
            eps_history,
            event["period_end"],
        )

        revenue_yoy = get_yoy_growth(
            revenue_history,
            revenue,
        )

        revenue_acceleration = (
            get_growth_acceleration(
                revenue_history,
                revenue,
            )
        )

        eps_yoy = None

        if eps is not None:
            eps_yoy = get_yoy_growth(
                eps_history,
                eps,
            )

        gross_margin_change = (
            get_margin_change(
                gross_profit_history,
                revenue_history,
                event["period_end"],
            )
        )

        operating_margin_change = (
            get_margin_change(
                operating_income_history,
                revenue_history,
                event["period_end"],
            )
        )

        backtest = (
            backtest_financial_event(
                ticker,
                benchmark,
                event,
            )
        )

        if backtest is None:
            continue

        reporting_lag = (
            event["filed_date"]
            - event["period_end"]
        ).days

        results.append(
            {
                "period_end":
                    event["period_end"],

                "entry_date":
                    backtest[
                        "entry_date"
                    ],

                "reporting_lag":
                    reporting_lag,

                "revenue_yoy":
                    revenue_yoy,

                "revenue_acceleration":
                    revenue_acceleration,

                "eps_yoy":
                    eps_yoy,

                "gross_margin_change":
                    gross_margin_change,

                "operating_margin_change":
                    operating_margin_change,

                "excess_30d":
                    get_excess_return(
                        backtest,
                        "30d",
                    ),

                "excess_90d":
                    get_excess_return(
                        backtest,
                        "90d",
                    ),

                "excess_180d":
                    get_excess_return(
                        backtest,
                        "180d",
                    ),
            }
        )

    #
    # Present events in actual trading order.
    #
    return sorted(
        results,
        key=lambda item:
            item["entry_date"],
    )


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_results(results):
    print()

    print(
        f"{TICKER} HISTORICAL "
        f"FINANCIAL BACKTEST"
    )

    print("=" * 137)

    print(
        f"{'Period End':<12}"
        f"{'Entry':<12}"
        f"{'Lag':>6}"
        f"{'Rev YoY':>11}"
        f"{'Rev Accel':>12}"
        f"{'EPS YoY':>11}"
        f"{'Gross Δ':>11}"
        f"{'Op Δ':>11}"
        f"{'30d Excess':>14}"
        f"{'90d Excess':>14}"
        f"{'180d Excess':>15}"
    )

    print("-" * 137)

    for row in results:
        print(
            f"{str(row['period_end']):<12}"

            f"{str(row['entry_date']):<12}"

            f"{row['reporting_lag']:>5}d"

            f"{format_percent(
                row['revenue_yoy']
            ):>11}"

            f"{format_percent(
                row[
                    'revenue_acceleration'
                ]
            ):>12}"

            f"{format_percent(
                row['eps_yoy']
            ):>11}"

            f"{format_percent(
                row[
                    'gross_margin_change'
                ]
            ):>11}"

            f"{format_percent(
                row[
                    'operating_margin_change'
                ]
            ):>11}"

            f"{format_percent(
                row['excess_30d']
            ):>14}"

            f"{format_percent(
                row['excess_90d']
            ):>14}"

            f"{format_percent(
                row['excess_180d']
            ):>15}"
        )


if __name__ == "__main__":
    results = (
        build_historical_backtest(
            TICKER,
            BENCHMARK,
        )
    )

    print_results(
        results
    )