from collections import Counter

from src.analysis.experimental_signal import (
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


PORTFOLIO_NAME = "Rum Runners"
SNAPSHOT_MONTH = "2026-09-01"
UNIVERSE_NAME = "rum_runner_2026_09"


def get_snapshot():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ps.id,
                    ps.portfolio_name,
                    ps.snapshot_month,
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
                    SNAPSHOT_MONTH,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        raise RuntimeError(
            "Rum Runners September 2026 snapshot not found."
        )

    return {
        "id": row[0],
        "portfolio_name": row[1],
        "snapshot_month": row[2],
        "cash": row[3],
        "total_portfolio_value": row[4],
        "total_cost_basis": row[5],
        "source_filename": row[6],
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
                ORDER BY psh.ticker
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


def build_analysis():
    snapshot = get_snapshot()
    holdings = get_holdings(
        snapshot["id"]
    )

    events = get_events(
        UNIVERSE_NAME
    )

    training, testing = split_by_time(
        events
    )

    confidence_map = (
        build_sector_confidence_map(
            training,
            testing,
        )
    )

    latest_events = get_latest_events(
        events
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
                    "sector_confidence": None,
                    "entry_date": None,
                    "experimental_match": False,
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

    return snapshot, results


def print_header(snapshot):
    print()
    print(
        "RUM RUNNERS SNAPSHOT ANALYSIS"
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
        f"Source: "
        f"{snapshot['source_filename']}"
    )

    print(
        f"Cash: "
        f"${snapshot['cash']:,.2f}"
    )

    print(
        f"Total portfolio value: "
        f"${snapshot['total_portfolio_value']:,.2f}"
    )

    print(
        f"Total cost basis: "
        f"${snapshot['total_cost_basis']:,.2f}"
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

        print(
            f"{item['ticker']:<8}"
            f"${item['market_value']:>13,.2f}"
            f"${item['gain_loss']:>13,.2f}"
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
    snapshot, results = (
        build_analysis()
    )

    print_header(
        snapshot
    )

    print_holdings(
        results
    )

    print_summary(
        results
    )


if __name__ == "__main__":
    main()