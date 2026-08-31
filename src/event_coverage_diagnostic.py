import sys

from src.database import get_connection
from src.time_split_statistics import DEFAULT_UNIVERSE



def get_coverage(
    universe_name=DEFAULT_UNIVERSE,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.ticker,
                    aum.sector,

                    COUNT(be.id) AS event_count,

                    MIN(be.entry_date) AS first_event,
                    MAX(be.entry_date) AS latest_event,

                    COUNT(
                        CASE
                            WHEN be.revenue_yoy
                                IS NOT NULL
                            THEN 1
                        END
                    ) AS revenue_count,

                    COUNT(
                        CASE
                            WHEN be.revenue_acceleration
                                IS NOT NULL
                            THEN 1
                        END
                    ) AS acceleration_count,

                    COUNT(
                        CASE
                            WHEN be.eps_yoy
                                IS NOT NULL
                            THEN 1
                        END
                    ) AS eps_count

                FROM analysis_universe_members aum

                JOIN analysis_universes au
                    ON au.id = aum.universe_id

                JOIN securities s
                    ON s.id = aum.security_id

                LEFT JOIN backtest_events be
                    ON be.security_id = s.id

                WHERE au.name = %s

                GROUP BY
                    s.ticker,
                    aum.sector

                ORDER BY
                    latest_event NULLS FIRST,
                    s.ticker;
                """,
                (
                    universe_name,
                ),
            )

            rows = cursor.fetchall()

    return rows


def print_report(
    rows,
    universe_name=DEFAULT_UNIVERSE,
):
    print()
    print(
        "BACKTEST EVENT COVERAGE DIAGNOSTIC"
    )

    print(
        f"Universe: {universe_name}"
    )

    print("=" * 125)

    print(
        f"{'Ticker':<8}"
        f"{'Sector':<27}"
        f"{'Events':>9}"
        f"{'First Event':>14}"
        f"{'Latest Event':>14}"
        f"{'Revenue':>11}"
        f"{'Accel':>10}"
        f"{'EPS':>10}"
    )

    print("-" * 125)

    missing = []
    stale = []

    for row in rows:
        (
            ticker,
            sector,
            event_count,
            first_event,
            latest_event,
            revenue_count,
            acceleration_count,
            eps_count,
        ) = row

        sector = sector or "UNKNOWN"

        print(
            f"{ticker:<8}"
            f"{sector:<27}"
            f"{event_count:>9}"
            f"{str(first_event or '-'):>14}"
            f"{str(latest_event or '-'):>14}"
            f"{revenue_count:>11}"
            f"{acceleration_count:>10}"
            f"{eps_count:>10}"
        )

        if event_count == 0:
            missing.append(
                ticker
            )

        elif latest_event is not None:
            if latest_event.year < 2026:
                stale.append(
                    (
                        ticker,
                        latest_event,
                    )
                )

    print()
    print("SUMMARY")
    print("=" * 70)

    print(
        f"Universe companies: {len(rows)}"
    )

    print(
        f"Companies with events: "
        f"{len(rows) - len(missing)}"
    )

    print(
        f"Companies with no events: "
        f"{len(missing)}"
    )

    print()

    if missing:
        print(
            "NO BACKTEST EVENTS:"
        )

        for ticker in missing:
            print(
                f"  {ticker}"
            )

    if stale:
        print()
        print(
            "LATEST EVENT BEFORE 2026:"
        )

        for ticker, latest_event in stale:
            print(
                f"  {ticker:<8}"
                f"{latest_event}"
            )


def main():
    universe_name = (
        sys.argv[1]
        if len(sys.argv) >= 2
        else DEFAULT_UNIVERSE
    )

    rows = get_coverage(
        universe_name
    )

    print_report(
        rows,
        universe_name,
    )


if __name__ == "__main__":
    main()