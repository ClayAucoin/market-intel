import sys
from datetime import date, timedelta

from src.database import get_connection


DEFAULT_UNIVERSE = "expanded_200"

PRICE_STALE_DAYS = 7
FINANCIAL_STALE_DAYS = 550
EVENT_STALE_DAYS = 550

CORE_METRICS = [
    "revenue",
    "net_income",
]

PREFERRED_METRICS = [
    "diluted_eps",
]

OPTIONAL_METRICS = [
    "operating_income",
    "operating_cash_flow",
    "gross_profit",
]


def get_universe_members(
    universe_name,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.ticker,
                    aum.sector

                FROM analysis_universe_members aum

                JOIN analysis_universes au
                    ON au.id = aum.universe_id

                JOIN securities s
                    ON s.id = aum.security_id

                WHERE au.name = %s

                ORDER BY s.ticker;
                """,
                (universe_name,),
            )

            return cursor.fetchall()


def get_price_health(
    ticker,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    MIN(trade_date),
                    MAX(trade_date),
                    COUNT(
                        CASE
                            WHEN adjusted_close IS NULL
                            THEN 1
                        END
                    ),
                    COUNT(
                        CASE
                            WHEN adjusted_open IS NULL
                            THEN 1
                        END
                    )

                FROM daily_prices

                WHERE symbol = %s;
                """,
                (ticker,),
            )

            row = cursor.fetchone()

    return {
        "count": row[0],
        "first_date": row[1],
        "latest_date": row[2],
        "missing_adjusted_close": row[3],
        "missing_adjusted_open": row[4],
    }


def get_financial_health(
    security_id,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    metric,
                    COUNT(*),
                    MIN(period_end),
                    MAX(period_end)

                FROM financial_facts

                WHERE security_id = %s

                GROUP BY metric;
                """,
                (security_id,),
            )

            rows = cursor.fetchall()

    metrics = {}

    for (
        metric,
        count,
        first_date,
        latest_date,
    ) in rows:
        metrics[metric] = {
            "count": count,
            "first_date": first_date,
            "latest_date": latest_date,
        }

    return metrics


def get_event_health(
    security_id,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    MIN(entry_date),
                    MAX(entry_date),
                    COUNT(
                        CASE
                            WHEN revenue_yoy IS NOT NULL
                            THEN 1
                        END
                    ),
                    COUNT(
                        CASE
                            WHEN revenue_acceleration
                                IS NOT NULL
                            THEN 1
                        END
                    ),
                    COUNT(
                        CASE
                            WHEN eps_yoy IS NOT NULL
                            THEN 1
                        END
                    ),
                    COUNT(
                        CASE
                            WHEN operating_margin_change
                                IS NOT NULL
                            THEN 1
                        END
                    ),
                    COUNT(
                        CASE
                            WHEN pre_excess_20d
                                IS NOT NULL
                            THEN 1
                        END
                    )

                FROM backtest_events

                WHERE security_id = %s;
                """,
                (security_id,),
            )

            row = cursor.fetchone()

    return {
        "count": row[0],
        "first_date": row[1],
        "latest_date": row[2],
        "revenue_count": row[3],
        "acceleration_count": row[4],
        "eps_count": row[5],
        "operating_margin_count": row[6],
        "pre_excess_count": row[7],
    }


def get_metric_names_by_level(
    metrics,
    names,
):
    return [
        name
        for name in names
        if (
            name not in metrics
            or metrics[name]["count"] == 0
        )
    ]


def is_stale(
    latest_date,
    days,
):
    if latest_date is None:
        return True

    cutoff = (
        date.today()
        - timedelta(days=days)
    )

    return latest_date < cutoff


def audit_company(
    security_id,
    ticker,
    sector,
):
    price = get_price_health(
        ticker
    )

    financials = get_financial_health(
        security_id
    )

    events = get_event_health(
        security_id
    )

    critical = []
    warnings = []
    notes = []

    if price["count"] == 0:
        critical.append(
            "no price history"
        )

    elif is_stale(
        price["latest_date"],
        PRICE_STALE_DAYS,
    ):
        critical.append(
            "stale price history"
        )

    if (
        price["missing_adjusted_close"] > 0
    ):
        warnings.append(
            "missing adjusted close"
        )

    if (
        price["missing_adjusted_open"] > 0
    ):
        warnings.append(
            "missing adjusted open"
        )

    missing_core = (
        get_metric_names_by_level(
            financials,
            CORE_METRICS,
        )
    )

    missing_preferred = (
        get_metric_names_by_level(
            financials,
            PREFERRED_METRICS,
        )
    )

    missing_optional = (
        get_metric_names_by_level(
            financials,
            OPTIONAL_METRICS,
        )
    )

    if missing_core:
        critical.append(
            "missing core: "
            + ", ".join(
                missing_core
            )
        )

    latest_financial_date = None

    for metric_data in (
        financials.values()
    ):
        metric_latest = (
            metric_data[
                "latest_date"
            ]
        )

        if metric_latest is None:
            continue

        if (
            latest_financial_date
            is None
            or metric_latest
            > latest_financial_date
        ):
            latest_financial_date = (
                metric_latest
            )

    if (
        financials
        and is_stale(
            latest_financial_date,
            FINANCIAL_STALE_DAYS,
        )
    ):
        warnings.append(
            "stale financial data"
        )

    if missing_preferred:
        warnings.append(
            "missing preferred: "
            + ", ".join(
                missing_preferred
            )
        )

    if missing_optional:
        notes.append(
            "missing optional: "
            + ", ".join(
                missing_optional
            )
        )

    if events["count"] == 0:
        warnings.append(
            "no backtest events"
        )

    elif is_stale(
        events["latest_date"],
        EVENT_STALE_DAYS,
    ):
        warnings.append(
            "stale backtest events"
        )

    if events["count"] > 0:
        if (
            events[
                "acceleration_count"
            ] == 0
        ):
            notes.append(
                "no revenue acceleration events"
            )

        if (
            events[
                "operating_margin_count"
            ] == 0
        ):
            notes.append(
                "no operating margin events"
            )

        if (
            events[
                "pre_excess_count"
            ] == 0
        ):
            notes.append(
                "no pre-event excess data"
            )

    if critical:
        status = "CRITICAL"

    elif warnings:
        status = "WARNING"

    else:
        status = "HEALTHY"

    return {
        "ticker": ticker,
        "sector": (
            sector
            or "UNKNOWN"
        ),
        "status": status,
        "critical": critical,
        "warnings": warnings,
        "notes": notes,
        "price": price,
        "financials": financials,
        "latest_financial_date":
            latest_financial_date,
        "events": events,
    }


def print_company_line(
    result,
):
    price_date = (
        result["price"][
            "latest_date"
        ]
        or "-"
    )

    financial_date = (
        result[
            "latest_financial_date"
        ]
        or "-"
    )

    event_date = (
        result["events"][
            "latest_date"
        ]
        or "-"
    )

    print(
        f"{result['ticker']:<8}"
        f"{result['status']:<11}"
        f"{str(price_date):>12}"
        f"{str(financial_date):>14}"
        f"{result['events']['count']:>9}"
        f"{str(event_date):>14}"
    )


def print_detail_section(
    title,
    results,
):
    print()
    print(title)
    print("=" * 90)

    if not results:
        print("None")
        return

    for result in results:
        print()
        print(
            f"{result['ticker']} "
            f"({result['sector']})"
        )

        for item in result[
            "critical"
        ]:
            print(
                f"  CRITICAL: {item}"
            )

        for item in result[
            "warnings"
        ]:
            print(
                f"  WARNING:  {item}"
            )

        for item in result[
            "notes"
        ]:
            print(
                f"  NOTE:     {item}"
            )


def print_summary(
    results,
    universe_name,
):
    healthy = [
        result
        for result in results
        if result["status"]
        == "HEALTHY"
    ]

    warnings = [
        result
        for result in results
        if result["status"]
        == "WARNING"
    ]

    critical = [
        result
        for result in results
        if result["status"]
        == "CRITICAL"
    ]

    no_events = [
        result
        for result in results
        if result["events"]["count"]
        == 0
    ]

    print()
    print(
        "SYSTEM & DATA HEALTH AUDIT"
    )

    print(
        f"Universe: {universe_name}"
    )

    print("=" * 90)

    print(
        f"{'Ticker':<8}"
        f"{'Status':<11}"
        f"{'Price':>12}"
        f"{'Financial':>14}"
        f"{'Events':>9}"
        f"{'Latest Event':>14}"
    )

    print("-" * 90)

    for result in results:
        print_company_line(
            result
        )

    print()
    print("SUMMARY")
    print("=" * 90)

    print(
        "Universe securities:",
        len(results),
    )

    print(
        "Healthy:",
        len(healthy),
    )

    print(
        "Warnings:",
        len(warnings),
    )

    print(
        "Critical:",
        len(critical),
    )

    print(
        "No backtest events:",
        len(no_events),
    )

    print_detail_section(
        "CRITICAL ISSUES",
        critical,
    )

    print_detail_section(
        "WARNINGS",
        warnings,
    )


def main():
    universe_name = (
        sys.argv[1]
        if len(sys.argv) >= 2
        else DEFAULT_UNIVERSE
    )

    members = get_universe_members(
        universe_name
    )

    if not members:
        raise ValueError(
            f"No members found for "
            f"universe: {universe_name}"
        )

    results = []

    for (
        security_id,
        ticker,
        sector,
    ) in members:
        results.append(
            audit_company(
                security_id,
                ticker,
                sector,
            )
        )

    print_summary(
        results,
        universe_name,
    )


if __name__ == "__main__":
    main()