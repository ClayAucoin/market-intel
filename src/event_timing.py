from datetime import time, timedelta
from zoneinfo import ZoneInfo

from src.database import get_connection


EASTERN = ZoneInfo(
    "America/New_York"
)

MARKET_OPEN = time(
    hour=9,
    minute=30,
)

MARKET_CLOSE = time(
    hour=16,
    minute=0,
)

MAX_ENTRY_DELAY_DAYS = 7


def get_financial_events(
    ticker,
    metric="revenue",
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ff.period_end,
                    ff.fiscal_year,
                    ff.fiscal_period,
                    ff.value,
                    ff.filed_date,
                    ff.accession_number,
                    ff.is_derived,
                    f.acceptance_datetime

                FROM financial_facts ff

                JOIN companies c
                    ON c.id =
                       ff.company_id

                LEFT JOIN filings f
                    ON f.accession_number =
                       ff.accession_number

                WHERE UPPER(c.ticker) =
                      UPPER(%s)

                  AND ff.metric = %s

                ORDER BY
                    ff.period_end;
                """,
                (
                    ticker,
                    metric,
                ),
            )

            rows = cursor.fetchall()

    return [
        {
            "period_end": row[0],
            "fiscal_year": row[1],
            "fiscal_period": row[2],
            "value": row[3],
            "filed_date": row[4],
            "accession_number": row[5],
            "is_derived": row[6],
            "acceptance_datetime": row[7],
        }
        for row in rows
    ]


def normalize_acceptance_datetime(
    acceptance_datetime,
):
    if acceptance_datetime is None:
        return None

    if acceptance_datetime.tzinfo is None:
        return acceptance_datetime.replace(
            tzinfo=EASTERN
        )

    return acceptance_datetime.astimezone(
        EASTERN
    )


def classify_timing(event):
    acceptance = (
        normalize_acceptance_datetime(
            event[
                "acceptance_datetime"
            ]
        )
    )

    if acceptance is None:
        return "timestamp unavailable"

    acceptance_time = acceptance.time()

    if acceptance_time < MARKET_OPEN:
        return "pre-market"

    if acceptance_time < MARKET_CLOSE:
        return "market hours"

    return "after market close"


def get_candidate_entry_date(event):
    acceptance = (
        normalize_acceptance_datetime(
            event[
                "acceptance_datetime"
            ]
        )
    )

    #
    # Without a timestamp, be conservative
    # and use the following day.
    #
    if acceptance is None:
        return (
            event["filed_date"]
            + timedelta(days=1)
        )

    acceptance_date = acceptance.date()
    acceptance_time = acceptance.time()

    #
    # Pre-market:
    # same-day open is usable.
    #
    if acceptance_time < MARKET_OPEN:
        return acceptance_date

    #
    # Market-hours or after-hours:
    # use the following trading session.
    #
    return (
        acceptance_date
        + timedelta(days=1)
    )


def get_next_trading_date(
    symbol,
    candidate_date,
):
    latest_allowed_date = (
        candidate_date
        + timedelta(
            days=MAX_ENTRY_DELAY_DAYS
        )
    )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    trade_date

                FROM daily_prices

                WHERE symbol = %s
                  AND trade_date >= %s
                  AND trade_date <= %s

                ORDER BY trade_date

                LIMIT 1;
                """,
                (
                    symbol.upper(),
                    candidate_date,
                    latest_allowed_date,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return row[0]


def get_event_entry_date(
    ticker,
    event,
):
    candidate_date = (
        get_candidate_entry_date(
            event
        )
    )

    return get_next_trading_date(
        ticker,
        candidate_date,
    )


if __name__ == "__main__":
    ticker = "DELL"

    events = get_financial_events(
        ticker,
        "revenue",
    )

    print()
    print(
        f"{ticker} FINANCIAL EVENT TIMING"
    )

    print("=" * 104)

    print(
        f"{'Period':<12}"
        f"{'FY':>6}"
        f"{'FP':>6}"
        f"{'Filed':>12}"
        f"{'Accepted ET':>24}"
        f"{'Timing':>22}"
        f"{'Entry':>12}"
    )

    print("-" * 104)

    for event in events[-12:]:
        acceptance = (
            normalize_acceptance_datetime(
                event[
                    "acceptance_datetime"
                ]
            )
        )

        acceptance_text = (
            acceptance.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if acceptance
            else "-"
        )

        entry_date = (
            get_event_entry_date(
                ticker,
                event,
            )
        )

        print(
            f"{str(event['period_end']):<12}"
            f"{str(event['fiscal_year']):>6}"
            f"{str(event['fiscal_period']):>6}"
            f"{str(event['filed_date']):>12}"
            f"{acceptance_text:>24}"
            f"{classify_timing(event):>22}"
            f"{str(entry_date):>12}"
        )