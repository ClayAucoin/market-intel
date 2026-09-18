from src.analysis.latest_signal_report import (
    add_scores,
    get_latest_events,
)
from src.analysis.portfolio_history_snapshot_report import (
    filter_completed_horizon_as_of,
    filter_events_as_of,
    get_snapshot,
)
from src.analysis.sector_confidence import (
    build_sector_confidence_map,
)
from src.backtesting.time_split_statistics import (
    get_events,
    split_by_time,
)
from src.database import get_connection


PORTFOLIO_NAME = "Historical Portfolio"
CANDIDATE_UNIVERSE = "historical_sp500"
INDEX_NAME = "S&P 500"


def get_snapshot_months():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT snapshot_month

                FROM portfolio_snapshots

                WHERE portfolio_name = %s

                ORDER BY snapshot_month;
                """,
                (
                    PORTFOLIO_NAME,
                ),
            )

            rows = cursor.fetchall()

    return [
        row[0]
        for row in rows
    ]


def get_member_tickers(
    as_of_date,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    COALESCE(
                        sth.ticker,
                        s.ticker
                    )

                FROM index_membership_history imh

                JOIN securities s
                    ON s.id = imh.security_id

                LEFT JOIN security_ticker_history sth
                    ON sth.security_id = s.id

                    AND sth.effective_from <= %s

                    AND (
                        sth.effective_to IS NULL
                        OR sth.effective_to >= %s
                    )

                WHERE
                    imh.index_name = %s

                    AND imh.effective_from <= %s

                    AND (
                        imh.effective_to IS NULL
                        OR imh.effective_to >= %s
                    );
                """,
                (
                    as_of_date,
                    as_of_date,
                    INDEX_NAME,
                    as_of_date,
                    as_of_date,
                ),
            )

            rows = cursor.fetchall()

    return {
        row[0]
        for row in rows
        if row[0]
    }


def build_confidence_map(
    events,
    as_of_date,
):
    as_of_events = filter_events_as_of(
        events,
        as_of_date,
    )

    training, testing = split_by_time(
        as_of_events
    )

    training = (
        filter_completed_horizon_as_of(
            training,
            as_of_date,
        )
    )

    testing = (
        filter_completed_horizon_as_of(
            testing,
            as_of_date,
        )
    )

    return build_sector_confidence_map(
        training,
        testing,
    )


def get_candidates(
    events,
    as_of_date,
):
    as_of_events = filter_events_as_of(
        events,
        as_of_date,
    )

    latest_events = get_latest_events(
        as_of_events
    )

    confidence_map = build_confidence_map(
        events,
        as_of_date,
    )

    scored_events = add_scores(
        latest_events,
        confidence_map,
    )

    member_tickers = get_member_tickers(
        as_of_date
    )

    candidates = []

    for item in scored_events:
        row = item["row"]

        ticker = row.get(
            "ticker"
        )

        if not ticker:
            continue

        if ticker not in member_tickers:
            continue

        if item["priority"] < 3:
            continue

        candidates.append(
            {
                "ticker":
                    ticker,
                "sector":
                    row.get("sector")
                    or "UNKNOWN",
                "entry_date":
                    row["entry_date"],
                "score":
                    item["score"],
                "priority":
                    item["priority"],
                "sector_confidence":
                    item[
                        "sector_confidence"
                    ],
                "recommendation":
                    item[
                        "recommendation"
                    ],
                "experimental_match":
                    item[
                        "experimental_match"
                    ],
            }
        )

    candidates.sort(
        key=lambda item: (
            item["priority"],
            item["score"],
            item["entry_date"],
            item["ticker"],
        ),
        reverse=True,
    )

    return (
        candidates,
        len(member_tickers),
        len(latest_events),
    )


def print_snapshot_candidates(
    snapshot_month,
    snapshot,
    candidates,
    member_count,
    latest_event_count,
):
    print()
    print("=" * 150)

    print(
        f"Snapshot: "
        f"{snapshot_month:%Y-%m}"
    )

    print(
        f"Analysis date: "
        f"{snapshot['as_of_date']}"
    )

    print(
        f"As-of source: "
        f"{snapshot['as_of_source']}"
    )

    print(
        f"S&P 500 members on date: "
        f"{member_count}"
    )

    print(
        f"Companies with latest event: "
        f"{latest_event_count}"
    )

    print(
        f"Priority 3+ S&P 500 candidates: "
        f"{len(candidates)}"
    )

    print("-" * 150)

    print(
        f"{'Ticker':<8}"
        f"{'Sector':<28}"
        f"{'Event Date':>14}"
        f"{'Score':>8}"
        f"{'Priority':>10}"
        f"{'Sector Conf':>18}"
        f"{'Experimental':>14}"
        f"  {'Recommendation'}"
    )

    print("-" * 150)

    for item in candidates:
        experimental = (
            "YES"
            if item[
                "experimental_match"
            ]
            else "-"
        )

        print(
            f"{item['ticker']:<8}"
            f"{item['sector']:<28}"
            f"{str(item['entry_date']):>14}"
            f"{item['score']:>8}"
            f"{item['priority']:>10}"
            f"{item['sector_confidence']:>18}"
            f"{experimental:>14}"
            f"  {item['recommendation']}"
        )


def main():
    snapshot_months = (
        get_snapshot_months()
    )

    if not snapshot_months:
        raise RuntimeError(
            "No Historical Portfolio "
            "snapshots found."
        )

    events = get_events(
        CANDIDATE_UNIVERSE
    )

    print()
    print(
        "HISTORICAL PORTFOLIO "
        "MARKET INTEL CANDIDATES"
    )

    print("=" * 150)

    print(
        f"Candidate universe: "
        f"{CANDIDATE_UNIVERSE}"
    )

    print(
        f"Historical events: "
        f"{len(events)}"
    )

    for snapshot_month in snapshot_months:
        snapshot = get_snapshot(
            snapshot_month
        )

        (
            candidates,
            member_count,
            latest_event_count,
        ) = get_candidates(
            events,
            snapshot["as_of_date"],
        )

        print_snapshot_candidates(
            snapshot_month,
            snapshot,
            candidates,
            member_count,
            latest_event_count,
        )


if __name__ == "__main__":
    main()