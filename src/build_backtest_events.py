from decimal import Decimal

from src.backtester import (
    backtest_from_entry_date,
)

from src.company_universe import (
    get_tickers,
)

from src.database import (
    get_connection,
)

from src.event_timing import (
    get_event_entry_date,
)

from src.market_context import (
    calculate_market_context,
)


BENCHMARK = "SPY"

MAX_REPORTING_LAG_DAYS = 120

HORIZONS = [
    "30d",
    "90d",
    "180d",
]


def clear_backtest_events():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE TABLE
                    backtest_events
                RESTART IDENTITY;
                """
            )

    print(
        "Cleared existing "
        "backtest_events."
    )


def get_security(ticker):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    ticker

                FROM securities

                WHERE UPPER(ticker) =
                      UPPER(%s)

                ORDER BY
                    is_primary DESC,
                    id

                LIMIT 1;
                """,
                (
                    ticker,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"Security not found: {ticker}"
        )

    return {
        "security_id": row[0],
        "ticker": row[1],
    }


def get_metric_history(
    security_id,
    metric,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    period_start,
                    period_end,
                    fiscal_year,
                    fiscal_period,
                    value,
                    filed_date,
                    accession_number,
                    is_derived,
                    concept,
                    company_id

                FROM financial_facts

                WHERE security_id = %s
                  AND metric = %s

                ORDER BY period_end;
                """,
                (
                    security_id,
                    metric,
                ),
            )

            rows = cursor.fetchall()

    return [
        {
            "period_start": row[0],
            "period_end": row[1],
            "fiscal_year": row[2],
            "fiscal_period": row[3],
            "value": Decimal(row[4]),
            "filed_date": row[5],
            "accession_number": row[6],
            "is_derived": row[7],
            "concept": row[8],
            "company_id": row[9],
        }
        for row in rows
    ]


def is_current_reporting_event(
    financial_fact,
):
    period_end = financial_fact.get(
        "period_end"
    )

    filed_date = financial_fact.get(
        "filed_date"
    )

    if (
        period_end is None
        or filed_date is None
    ):
        return False

    reporting_lag = (
        filed_date
        - period_end
    ).days

    if reporting_lag < 0:
        return False

    if (
        reporting_lag
        > MAX_REPORTING_LAG_DAYS
    ):
        return False

    return True


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
        key=lambda item:
            item[0]
    )

    return candidates[0][1]


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
        (
            current
            - previous
        )
        / abs(previous)
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

    return round(
        (
            numerator
            / revenue
        )
        * Decimal("100"),
        2,
    )


def get_margin_change(
    numerator_history,
    revenue_history,
    period_end,
):
    numerator_current = (
        get_period_record(
            numerator_history,
            period_end,
        )
    )

    revenue_current = (
        get_period_record(
            revenue_history,
            period_end,
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


def get_filing(
    accession_number,
):
    if not accession_number:
        return None

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    filing_date,
                    acceptance_datetime,
                    form

                FROM filings

                WHERE accession_number = %s

                LIMIT 1;
                """,
                (
                    accession_number,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "filing_date": row[0],

        "acceptance_datetime":
            row[1],

        "form": row[2],
    }


def get_entry_date(
    ticker,
    financial_fact,
):
    filing = get_filing(
        financial_fact[
            "accession_number"
        ]
    )

    if filing is None:
        return None

    event = {
        "filed_date":
            filing["filing_date"],

        "acceptance_datetime":
            filing[
                "acceptance_datetime"
            ],
    }

    return get_event_entry_date(
        ticker,
        event,
    )


def get_horizon_result(
    stock_result,
    benchmark_result,
    horizon,
):
    stock = stock_result[
        "horizons"
    ].get(horizon)

    benchmark = benchmark_result[
        "horizons"
    ].get(horizon)

    if (
        stock is None
        or benchmark is None
    ):
        return {
            "return": None,
            "benchmark_return": None,
            "excess_return": None,
        }

    stock_return = stock[
        "return_percent"
    ]

    benchmark_return = benchmark[
        "return_percent"
    ]

    return {
        "return":
            stock_return,

        "benchmark_return":
            benchmark_return,

        "excess_return":
            round(
                stock_return
                - benchmark_return,
                2,
            ),
    }


def save_backtest_event(
    security_id,
    period_end,
    entry_date,
    entry_price,

    revenue_yoy,
    revenue_acceleration,
    eps_yoy,
    gross_margin_change,
    operating_margin_change,

    market_context,
    horizon_results,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO backtest_events (
                    security_id,
                    period_end,
                    entry_date,
                    entry_price,

                    revenue_yoy,
                    revenue_acceleration,
                    eps_yoy,
                    gross_margin_change,
                    operating_margin_change,

                    pre_return_20d,
                    pre_return_60d,
                    pre_excess_20d,
                    pre_excess_60d,
                    pre_volatility_20d,

                    previous_close,
                    entry_open,
                    opening_gap_pct,
                    spy_opening_gap_pct,
                    opening_gap_excess,

                    return_30d,
                    spy_return_30d,
                    excess_30d,

                    return_90d,
                    spy_return_90d,
                    excess_90d,

                    return_180d,
                    spy_return_180d,
                    excess_180d
                )

                VALUES (
                    %s, %s, %s, %s,

                    %s, %s, %s, %s, %s,

                    %s, %s, %s, %s, %s,

                    %s, %s, %s, %s, %s,

                    %s, %s, %s,

                    %s, %s, %s,

                    %s, %s, %s
                )

                ON CONFLICT (
                    security_id,
                    period_end
                )

                DO UPDATE SET
                    entry_date =
                        EXCLUDED.entry_date,

                    entry_price =
                        EXCLUDED.entry_price,

                    revenue_yoy =
                        EXCLUDED.revenue_yoy,

                    revenue_acceleration =
                        EXCLUDED.revenue_acceleration,

                    eps_yoy =
                        EXCLUDED.eps_yoy,

                    gross_margin_change =
                        EXCLUDED.gross_margin_change,

                    operating_margin_change =
                        EXCLUDED.operating_margin_change,

                    pre_return_20d =
                        EXCLUDED.pre_return_20d,

                    pre_return_60d =
                        EXCLUDED.pre_return_60d,

                    pre_excess_20d =
                        EXCLUDED.pre_excess_20d,

                    pre_excess_60d =
                        EXCLUDED.pre_excess_60d,

                    pre_volatility_20d =
                        EXCLUDED.pre_volatility_20d,

                    previous_close =
                        EXCLUDED.previous_close,

                    entry_open =
                        EXCLUDED.entry_open,

                    opening_gap_pct =
                        EXCLUDED.opening_gap_pct,

                    spy_opening_gap_pct =
                        EXCLUDED.spy_opening_gap_pct,

                    opening_gap_excess =
                        EXCLUDED.opening_gap_excess,

                    return_30d =
                        EXCLUDED.return_30d,

                    spy_return_30d =
                        EXCLUDED.spy_return_30d,

                    excess_30d =
                        EXCLUDED.excess_30d,

                    return_90d =
                        EXCLUDED.return_90d,

                    spy_return_90d =
                        EXCLUDED.spy_return_90d,

                    excess_90d =
                        EXCLUDED.excess_90d,

                    return_180d =
                        EXCLUDED.return_180d,

                    spy_return_180d =
                        EXCLUDED.spy_return_180d,

                    excess_180d =
                        EXCLUDED.excess_180d,

                    updated_at =
                        CURRENT_TIMESTAMP;
                """,
                (
                    security_id,
                    period_end,
                    entry_date,
                    entry_price,

                    revenue_yoy,
                    revenue_acceleration,
                    eps_yoy,
                    gross_margin_change,
                    operating_margin_change,

                    market_context[
                        "pre_return_20d"
                    ],

                    market_context[
                        "pre_return_60d"
                    ],

                    market_context[
                        "pre_excess_20d"
                    ],

                    market_context[
                        "pre_excess_60d"
                    ],

                    market_context[
                        "pre_volatility_20d"
                    ],

                    market_context[
                        "previous_close"
                    ],

                    market_context[
                        "entry_open"
                    ],

                    market_context[
                        "opening_gap_pct"
                    ],

                    market_context[
                        "spy_opening_gap_pct"
                    ],

                    market_context[
                        "opening_gap_excess"
                    ],

                    horizon_results[
                        "30d"
                    ]["return"],

                    horizon_results[
                        "30d"
                    ]["benchmark_return"],

                    horizon_results[
                        "30d"
                    ]["excess_return"],

                    horizon_results[
                        "90d"
                    ]["return"],

                    horizon_results[
                        "90d"
                    ]["benchmark_return"],

                    horizon_results[
                        "90d"
                    ]["excess_return"],

                    horizon_results[
                        "180d"
                    ]["return"],

                    horizon_results[
                        "180d"
                    ]["benchmark_return"],

                    horizon_results[
                        "180d"
                    ]["excess_return"],
                ),
            )


def build_ticker_events(ticker):
    security = get_security(
        ticker
    )

    security_id = (
        security["security_id"]
    )

    revenue_history = (
        get_metric_history(
            security_id,
            "revenue",
        )
    )

    eps_history = (
        get_metric_history(
            security_id,
            "diluted_eps",
        )
    )

    gross_profit_history = (
        get_metric_history(
            security_id,
            "gross_profit",
        )
    )

    operating_income_history = (
        get_metric_history(
            security_id,
            "operating_income",
        )
    )

    saved = 0

    comparative_skipped = 0
    timing_skipped = 0
    price_skipped = 0

    for revenue in revenue_history:
        if not is_current_reporting_event(
            revenue
        ):
            comparative_skipped += 1
            continue

        entry_date = get_entry_date(
            ticker,
            revenue,
        )

        if entry_date is None:
            timing_skipped += 1
            continue

        stock_result = (
            backtest_from_entry_date(
                ticker,
                entry_date,
            )
        )

        benchmark_result = (
            backtest_from_entry_date(
                BENCHMARK,
                entry_date,
            )
        )

        if (
            stock_result is None
            or benchmark_result is None
        ):
            price_skipped += 1
            continue

        market_context = (
            calculate_market_context(
                ticker,
                entry_date,
                benchmark=BENCHMARK,
            )
        )

        eps = get_period_record(
            eps_history,
            revenue["period_end"],
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
                revenue[
                    "period_end"
                ],
            )
        )

        operating_margin_change = (
            get_margin_change(
                operating_income_history,
                revenue_history,
                revenue[
                    "period_end"
                ],
            )
        )

        horizon_results = {}

        for horizon in HORIZONS:
            horizon_results[
                horizon
            ] = get_horizon_result(
                stock_result,
                benchmark_result,
                horizon,
            )

        save_backtest_event(
            security_id=
                security_id,

            period_end=
                revenue["period_end"],

            entry_date=
                entry_date,

            entry_price=
                stock_result[
                    "entry_price"
                ],

            revenue_yoy=
                revenue_yoy,

            revenue_acceleration=
                revenue_acceleration,

            eps_yoy=
                eps_yoy,

            gross_margin_change=
                gross_margin_change,

            operating_margin_change=
                operating_margin_change,

            market_context=
                market_context,

            horizon_results=
                horizon_results,
        )

        saved += 1

    return {
        "ticker":
            ticker,

        "saved":
            saved,

        "comparative_skipped":
            comparative_skipped,

        "timing_skipped":
            timing_skipped,

        "price_skipped":
            price_skipped,
    }


def main():
    tickers = get_tickers()

    results = []

    print()
    print(
        "MARKET INTEL CROSS-COMPANY "
        "BACKTEST BUILD"
    )

    print("=" * 84)

    clear_backtest_events()

    for ticker in tickers:
        print()
        print(
            f"Building {ticker}..."
        )

        try:
            result = (
                build_ticker_events(
                    ticker
                )
            )

        except Exception as error:
            print(
                f"ERROR: {error}"
            )

            result = {
                "ticker":
                    ticker,

                "saved":
                    0,

                "comparative_skipped":
                    0,

                "timing_skipped":
                    0,

                "price_skipped":
                    0,
            }

        results.append(
            result
        )

        print(
            "Saved:",
            result["saved"],
        )

        print(
            "Comparative skipped:",
            result[
                "comparative_skipped"
            ],
        )

        print(
            "Timing skipped:",
            result[
                "timing_skipped"
            ],
        )

        print(
            "Price skipped:",
            result[
                "price_skipped"
            ],
        )

    print()
    print("=" * 84)

    print(
        "BACKTEST BUILD SUMMARY"
    )

    print()

    print(
        f"{'Ticker':<10}"
        f"{'Saved':>9}"
        f"{'Compare':>11}"
        f"{'Timing':>11}"
        f"{'Price':>11}"
    )

    print("-" * 52)

    totals = {
        "saved": 0,
        "comparative_skipped": 0,
        "timing_skipped": 0,
        "price_skipped": 0,
    }

    for result in results:
        print(
            f"{result['ticker']:<10}"

            f"{result['saved']:>9}"

            f"{result[
                'comparative_skipped'
            ]:>11}"

            f"{result[
                'timing_skipped'
            ]:>11}"

            f"{result[
                'price_skipped'
            ]:>11}"
        )

        for field in totals:
            totals[field] += (
                result[field]
            )

    print("-" * 52)

    print(
        f"{'TOTAL':<10}"

        f"{totals['saved']:>9}"

        f"{totals[
            'comparative_skipped'
        ]:>11}"

        f"{totals[
            'timing_skipped'
        ]:>11}"

        f"{totals[
            'price_skipped'
        ]:>11}"
    )


if __name__ == "__main__":
    main()