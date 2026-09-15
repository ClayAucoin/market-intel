import sys

from collections import Counter
from datetime import date

from src.analysis.experimental_signal import (
    HORIZON,
    qualifies_experimental_signal,
)
from src.analysis.latest_signal_report import (
    add_scores,
    get_latest_events,
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


def get_requested_snapshot_month():
    if len(sys.argv) < 2:
        raise RuntimeError(
            "Snapshot month required. "
            "Example: 2026-05"
        )

    value = sys.argv[1].strip()

    try:
        if len(value) == 7:
            return date.fromisoformat(
                f"{value}-01"
            )

        parsed = date.fromisoformat(
            value
        )

        return parsed.replace(
            day=1
        )

    except ValueError as exc:
        raise RuntimeError(
            "Snapshot month must be "
            "YYYY-MM or YYYY-MM-DD."
        ) from exc


def get_universe_name(snapshot_month):
    return (
        "portfolio_history_"
        f"{snapshot_month:%Y_%m}"
    )


def get_snapshot(snapshot_month):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ps.id,
                    ps.portfolio_name,
                    ps.snapshot_month,
                    ps.valuation_date,
                    ps.cash,
                    ps.total_portfolio_value,
                    ps.total_cost_basis,
                    ps.source_filename

                FROM portfolio_snapshots ps

                WHERE
                    ps.portfolio_name = %s
                    AND ps.snapshot_month = %s
                """,
                (
                    PORTFOLIO_NAME,
                    snapshot_month,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        raise RuntimeError(
            "Historical Portfolio snapshot "
            f"not found for {snapshot_month:%Y-%m}."
        )

    valuation_date = row[3]

    if valuation_date is not None:
        as_of_date = valuation_date
        as_of_source = (
            "Verified valuation date"
        )
    else:
        as_of_date = row[2]
        as_of_source = (
            "Snapshot month date "
            "(exact valuation date not reported)"
        )

    return {
        "id": row[0],
        "portfolio_name": row[1],
        "snapshot_month": row[2],
        "valuation_date": valuation_date,
        "as_of_date": as_of_date,
        "as_of_source": as_of_source,
        "cash": row[4],
        "total_portfolio_value": row[5],
        "total_cost_basis": row[6],
        "source_filename": row[7],
    }


def get_holdings(snapshot_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    psh.ticker,
                    psh.description,
                    psh.price,
                    psh.shares,
                    psh.market_value,
                    psh.cost_basis,
                    psh.gain_loss

                FROM portfolio_snapshot_holdings psh

                WHERE psh.snapshot_id = %s

                ORDER BY
                    psh.ticker
                """,
                (
                    snapshot_id,
                ),
            )

            rows = cursor.fetchall()

    return [
        {
            "ticker": row[0],
            "description": row[1],
            "price": row[2],
            "shares": row[3],
            "market_value": row[4],
            "cost_basis": row[5],
            "gain_loss": row[6],
        }
        for row in rows
    ]


def filter_events_as_of(
    events,
    as_of_date,
):
    return [
        row
        for row in events
        if (
            row.get("entry_date")
            is not None
            and row["entry_date"]
            <= as_of_date
        )
    ]


def filter_completed_horizon_as_of(
    rows,
    as_of_date,
):
    exit_date_key = (
        f"exit_date_{HORIZON}"
    )

    return [
        row
        for row in rows
        if (
            row.get(exit_date_key)
            is not None
            and row[exit_date_key]
            <= as_of_date
        )
    ]


def build_analysis(snapshot_month):
    snapshot = get_snapshot(
        snapshot_month
    )

    holdings = get_holdings(
        snapshot["id"]
    )

    universe_name = get_universe_name(
        snapshot_month
    )

    # Portfolio-universe events are used to score
    # only the securities held in this snapshot.
    events = get_events(
        universe_name
    )

    as_of_events = filter_events_as_of(
        events,
        snapshot["as_of_date"],
    )

    # Sector confidence comes from the broader
    # historical S&P 500 research population.
    confidence_universe = "historical_sp500"

    confidence_events = get_events(
        confidence_universe
    )

    confidence_as_of_events = (
        filter_events_as_of(
            confidence_events,
            snapshot["as_of_date"],
        )
    )

    confidence_training, confidence_testing = (
        split_by_time(
            confidence_as_of_events
        )
    )

    confidence_training = (
        filter_completed_horizon_as_of(
            confidence_training,
            snapshot["as_of_date"],
        )
    )

    confidence_testing = (
        filter_completed_horizon_as_of(
            confidence_testing,
            snapshot["as_of_date"],
        )
    )

    confidence_map = (
        build_sector_confidence_map(
            confidence_training,
            confidence_testing,
        )
    )

    latest_events = get_latest_events(
        as_of_events
    )

    scored_events = add_scores(
        latest_events,
        confidence_map,
    )

    scored_by_ticker = {
        item["row"]["ticker"]: item
        for item in scored_events
    }

    results = []

    for holding in holdings:
        ticker = holding["ticker"]

        score_item = scored_by_ticker.get(
            ticker
        )

        if score_item is None:
            results.append(
                {
                    **holding,
                    "status":
                        "Insufficient Data",
                    "score": None,
                    "priority": None,
                    "sector_confidence":
                        None,
                    "entry_date": None,
                    "experimental_match":
                        False,
                }
            )

            continue

        row = score_item["row"]

        results.append(
            {
                **holding,
                "status":
                    score_item[
                        "recommendation"
                    ],
                "score":
                    score_item["score"],
                "priority":
                    score_item["priority"],
                "sector_confidence":
                    score_item[
                        "sector_confidence"
                    ],
                "entry_date":
                    row["entry_date"],
                "experimental_match":
                    qualifies_experimental_signal(
                        row
                    ),
            }
        )

    diagnostics = {
        "universe_name":
            universe_name,

        "confidence_universe":
            confidence_universe,

        "total_events":
            len(events),

        "as_of_events":
            len(as_of_events),

        "confidence_training":
            len(confidence_training),

        "confidence_testing":
            len(confidence_testing),
    }

    return (
        snapshot,
        results,
        diagnostics,
    )


def format_money(value):
    if value is None:
        return "-"

    return f"${value:,.2f}"


def print_header(
    snapshot,
    diagnostics,
):
    print()
    print(
        "HISTORICAL PORTFOLIO "
        "POINT-IN-TIME ANALYSIS"
    )
    print("=" * 140)

    print(
        f"Portfolio: "
        f"{snapshot['portfolio_name']}"
    )

    print(
        f"Snapshot month: "
        f"{snapshot['snapshot_month']}"
    )

    print(
        f"Valuation date: "
        f"{snapshot['valuation_date'] or '-'}"
    )

    print(
        f"Analysis as-of date: "
        f"{snapshot['as_of_date']}"
    )

    print(
        f"As-of source: "
        f"{snapshot['as_of_source']}"
    )

    print(
        f"Universe: "
        f"{diagnostics['universe_name']}"
    )

    print(
        f"Source: "
        f"{snapshot['source_filename']}"
    )

    print(
        f"Cash: "
        f"{format_money(snapshot['cash'])}"
    )

    print(
        f"Total portfolio value: "
        f"{format_money(
            snapshot['total_portfolio_value']
        )}"
    )

    print(
        f"Total cost basis: "
        f"{format_money(
            snapshot['total_cost_basis']
        )}"
    )

    print()
    print(
        "POINT-IN-TIME FILTER"
    )
    print("-" * 140)

    print(
        f"Universe events in database: "
        f"{diagnostics['total_events']}"
    )

    print(
        f"Events known by as-of date: "
        f"{diagnostics['as_of_events']}"
    )

    print(
        f"Sector confidence universe: "
        f"{diagnostics['confidence_universe']}"
    )

    print(
        f"Completed {HORIZON} training "
        f"outcomes known by as-of date: "
        f"{diagnostics['confidence_training']}"
    )

    print(
        f"Completed {HORIZON} testing "
        f"outcomes known by as-of date: "
        f"{diagnostics['confidence_testing']}"
    )


def print_holdings(results):
    print()
    print(
        "HOLDING ANALYSIS"
    )
    print("=" * 180)

    print(
        f"{'Ticker':<8}"
        f"{'Market Value':>14}"
        f"{'Gain/Loss':>14}"
        f"{'Score':>8}"
        f"{'Priority':>10}"
        f"{'Entry Date':>14}"
        f"{'Experimental':>14}"
        f"{'Sector Conf':>18}"
        f"  {'Status':<34}"
    )

    print("-" * 180)

    ordered = sorted(
        results,
        key=lambda item: (
            item["priority"]
            if item["priority"] is not None
            else -1,

            item["score"]
            if item["score"] is not None
            else -1,

            item["market_value"],
        ),
        reverse=True,
    )

    for item in ordered:
        score_text = (
            str(item["score"])
            if item["score"] is not None
            else "-"
        )

        priority_text = (
            str(item["priority"])
            if item["priority"] is not None
            else "-"
        )

        entry_text = (
            str(item["entry_date"])
            if item["entry_date"] is not None
            else "-"
        )

        experimental_text = (
            "YES"
            if item[
                "experimental_match"
            ]
            else "-"
        )

        confidence_text = (
            item["sector_confidence"]
            if item[
                "sector_confidence"
            ]
            is not None
            else "-"
        )

        gain_loss_text = (
            format_money(
                item["gain_loss"]
            )
        )

        print(
            f"{item['ticker']:<8}"
            f"${item['market_value']:>13,.2f}"
            f"{gain_loss_text:>14}"
            f"{score_text:>8}"
            f"{priority_text:>10}"
            f"{entry_text:>14}"
            f"{experimental_text:>14}"
            f"{confidence_text:>18}"
            f"  {item['status']:<34}"
        )


def print_summary(results):
    print()
    print(
        "SUMMARY"
    )
    print("=" * 100)

    print(
        f"Total holdings: "
        f"{len(results)}"
    )

    analyzable = [
        item
        for item in results
        if item["score"] is not None
    ]

    insufficient = [
        item
        for item in results
        if item["score"] is None
    ]

    experimental = [
        item
        for item in results
        if item[
            "experimental_match"
        ]
    ]

    strong = [
        item
        for item in analyzable
        if (
            item["priority"] is not None
            and item["priority"] >= 3
        )
    ]

    print(
        f"Analyzable holdings: "
        f"{len(analyzable)}"
    )

    print(
        f"Insufficient data: "
        f"{len(insufficient)}"
    )

    print(
        f"Priority 3 or higher: "
        f"{len(strong)}"
    )

    print(
        f"Experimental strategy matches: "
        f"{len(experimental)}"
    )

    print()
    print(
        "STATUS COUNTS"
    )
    print("-" * 100)

    status_counts = Counter(
        item["status"]
        for item in results
    )

    for status, count in sorted(
        status_counts.items(),
        key=lambda item: (
            item[1],
            item[0],
        ),
        reverse=True,
    ):
        print(
            f"{status:<40}"
            f"{count:>5}"
        )

    if insufficient:
        print()
        print(
            "INSUFFICIENT DATA"
        )
        print("-" * 100)

        print(
            ", ".join(
                item["ticker"]
                for item in sorted(
                    insufficient,
                    key=lambda item:
                        item["ticker"],
                )
            )
        )


def main():
    snapshot_month = (
        get_requested_snapshot_month()
    )

    (
        snapshot,
        results,
        diagnostics,
    ) = build_analysis(
        snapshot_month
    )

    print_header(
        snapshot,
        diagnostics,
    )

    print_holdings(
        results
    )

    print_summary(
        results
    )


if __name__ == "__main__":
    main()