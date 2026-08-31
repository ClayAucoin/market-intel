import sys

from src.recommendation_engine import (
    get_recommendation,
)
from src.sector_confidence import (
    build_sector_confidence_map,
)
from src.signal_scorer import (
    score_event,
)
from src.time_split_statistics import (
    DEFAULT_UNIVERSE,
    format_percent,
    get_events,
    split_by_time,
)


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


def get_latest_events(rows):
    latest = {}

    for row in rows:
        ticker = row.get("ticker")
        entry_date = row.get("entry_date")

        if (
            not ticker
            or entry_date is None
        ):
            continue

        current = latest.get(
            ticker
        )

        if (
            current is None
            or entry_date
            > current["entry_date"]
        ):
            latest[ticker] = row

    return list(
        latest.values()
    )


def add_scores(
    rows,
    confidence_map,
):
    results = []

    for row in rows:
        score_result = score_event(
            row
        )

        sector = (
            row.get("sector")
            or "UNKNOWN"
        )

        confidence = (
            confidence_map.get(
                sector,
                {
                    "label":
                        "No Evidence",
                },
            )
        )

        sector_confidence = (
            confidence["label"]
        )

        recommendation = (
            get_recommendation(
                score_result["score"],
                sector_confidence,
            )
        )

        results.append(
            {
                "row": row,

                "score":
                    score_result[
                        "score"
                    ],

                "classification":
                    score_result[
                        "classification"
                    ],

                "components":
                    score_result[
                        "components"
                    ],

                "sector_confidence":
                    sector_confidence,

                "recommendation":
                    recommendation[
                        "label"
                    ],

                "priority":
                    recommendation[
                        "priority"
                    ],

                "recommendation_reason":
                    recommendation[
                        "reason"
                    ],
            }
        )

    return results


def print_results(results):
    print()
    print(
        "LATEST FINANCIAL SIGNAL REPORT"
    )

    print("=" * 190)

    print(
        f"{'Ticker':<8}"
        f"{'Sector':<25}"
        f"{'Entry Date':>12}"
        f"{'Score':>8}"
        f"{'Class':>12}"
        f"{'Sector Conf':>16}"
        f"{'Priority':>10}"
        f"  {'Recommendation':<32}"
        f"{'Rev Growth':>14}"
        f"{'Rev Accel':>14}"
        f"{'EPS Growth':>14}"
    )

    print("-" * 190)

    for item in results:
        row = item["row"]

        print(
            f"{row['ticker']:<8}"
            f"{(row.get('sector') or 'UNKNOWN'):<25}"
            f"{str(row['entry_date']):>12}"
            f"{item['score']:>8}"
            f"{item['classification']:>12}"
            f"{item['sector_confidence']:>16}"
            f"{item['priority']:>10}"
            f"  {item['recommendation']:<32}"
            f"{format_percent(row.get('revenue_yoy')):>14}"
            f"{format_percent(row.get('revenue_acceleration')):>14}"
            f"{format_percent(row.get('eps_yoy')):>14}"
        )


def print_priority_summary(results):
    print()
    print(
        "RECOMMENDATION SUMMARY"
    )

    print("=" * 100)

    ordered = sorted(
        results,
        key=lambda item: (
            item["priority"],
            item["score"],
            item["row"]["entry_date"],
        ),
        reverse=True,
    )

    for priority in range(
        5,
        -1,
        -1,
    ):
        matching = [
            item
            for item in ordered
            if item["priority"] == priority
        ]

        if not matching:
            continue

        print()
        print(
            f"Priority {priority}: "
            f"{len(matching)} companies"
        )

        print("-" * 100)

        for item in matching:
            row = item["row"]

            print(
                f"{row['ticker']:<8}"
                f"{item['score']}/6  "
                f"{item['sector_confidence']:<16}"
                f"{item['recommendation']}"
            )


def print_strong_details(results):
    strong = [
        item
        for item in results
        if item["score"] >= 4
    ]

    strong.sort(
        key=lambda item: (
            item["priority"],
            item["score"],
            item["row"]["entry_date"],
        ),
        reverse=True,
    )

    print()
    print(
        "STRONG SIGNAL DETAILS"
    )

    print("=" * 110)

    print(
        "Companies with score 4 or higher:",
        len(strong),
    )

    for item in strong:
        row = item["row"]

        print()
        print(
            f"{row['ticker']} "
            f"| Score "
            f"{item['score']} / 6 "
            f"| {item['classification']}"
        )

        print(
            f"Recommendation: "
            f"{item['recommendation']}"
        )

        print(
            f"Priority: "
            f"{item['priority']}"
        )

        print(
            f"Sector confidence: "
            f"{item['sector_confidence']}"
        )

        print(
            f"Entry date: "
            f"{row['entry_date']}"
        )

        print(
            f"Sector: "
            f"{row.get('sector') or 'UNKNOWN'}"
        )

        print(
            f"Reason: "
            f"{item['recommendation_reason']}"
        )

        print(
            "Financial signal:"
        )

        for component in item[
            "components"
        ]:
            print(
                f"  +{component['points']} "
                f"{component['reason']}"
            )


def main():
    universe_name = get_universe_name()

    rows = get_events(
        universe_name
    )

    training, testing = split_by_time(
        rows
    )

    confidence_map = (
        build_sector_confidence_map(
            training,
            testing,
        )
    )

    latest = get_latest_events(
        rows
    )

    scored = add_scores(
        latest,
        confidence_map,
    )

    scored.sort(
        key=lambda item: (
            item["priority"],
            item["score"],
            item["row"]["entry_date"],
        ),
        reverse=True,
    )

    print()
    print(
        "Universe:",
        universe_name,
    )

    print_results(
        scored
    )

    print_priority_summary(
        scored
    )

    print_strong_details(
        scored
    )


if __name__ == "__main__":
    main()