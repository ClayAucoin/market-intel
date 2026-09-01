import sys

from src.analysis.experimental_signal import (
    SIGNAL_DESCRIPTION,
    qualifies_experimental_signal,
)
from src.analysis.recommendation_engine import (
    get_recommendation,
)
from src.analysis.sector_confidence import (
    build_sector_confidence_map,
)
from src.analysis.signal_scorer import (
    score_event,
)
from src.backtesting.time_split_statistics import (
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

        experimental_match = (
            qualifies_experimental_signal(
                row
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

                "experimental_match":
                    experimental_match,
            }
        )

    return results


def print_results(results):
    print()
    print(
        "LATEST FINANCIAL SIGNAL REPORT"
    )

    print("=" * 204)

    print(
        f"{'Ticker':<8}"
        f"{'Sector':<25}"
        f"{'Entry Date':>12}"
        f"{'Score':>8}"
        f"{'Class':>12}"
        f"{'Sector Conf':>16}"
        f"{'Priority':>10}"
        f"{'Experimental':>14}"
        f"  {'Recommendation':<32}"
        f"{'Rev Growth':>14}"
        f"{'Rev Accel':>14}"
        f"{'EPS Growth':>14}"
    )

    print("-" * 204)

    for item in results:
        row = item["row"]

        experimental_text = (
            "YES"
            if item[
                "experimental_match"
            ]
            else "-"
        )

        print(
            f"{row['ticker']:<8}"
            f"{(row.get('sector') or 'UNKNOWN'):<25}"
            f"{str(row['entry_date']):>12}"
            f"{item['score']:>8}"
            f"{item['classification']:>12}"
            f"{item['sector_confidence']:>16}"
            f"{item['priority']:>10}"
            f"{experimental_text:>14}"
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

            experimental_text = (
                " | EXPERIMENTAL MATCH"
                if item[
                    "experimental_match"
                ]
                else ""
            )

            print(
                f"{row['ticker']:<8}"
                f"{item['score']}/6  "
                f"{item['sector_confidence']:<16}"
                f"{item['recommendation']}"
                f"{experimental_text}"
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
            f"Experimental strategy match: "
            f"{'YES' if item['experimental_match'] else 'NO'}"
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


def print_experimental_matches(
    results,
):
    matches = [
        item
        for item in results
        if item[
            "experimental_match"
        ]
    ]

    matches.sort(
        key=lambda item: (
            item["row"]["entry_date"],
            item["priority"],
            item["score"],
        ),
        reverse=True,
    )

    print()
    print(
        "EXPERIMENTAL STRATEGY MATCHES"
    )

    print("=" * 110)

    print(
        f"Qualification: "
        f"{SIGNAL_DESCRIPTION}"
    )

    print(
        f"Current latest-event matches: "
        f"{len(matches)}"
    )

    if not matches:
        print(
            "No current latest events "
            "match the experimental strategy."
        )
        return

    for item in matches:
        row = item["row"]

        print()
        print(
            f"{row['ticker']} "
            f"| {row['entry_date']} "
            f"| Score {item['score']}/6 "
            f"| Priority {item['priority']}"
        )

        print(
            f"  Sector: "
            f"{row.get('sector') or 'UNKNOWN'}"
        )

        print(
            f"  Sector confidence: "
            f"{item['sector_confidence']}"
        )

        print(
            f"  Recommendation: "
            f"{item['recommendation']}"
        )

        print(
            f"  Revenue acceleration: "
            f"{format_percent(
                row.get(
                    'revenue_acceleration'
                )
            )}"
        )

        print(
            f"  Operating margin change: "
            f"{format_percent(
                row.get(
                    'operating_margin_change'
                )
            )}"
        )

        print(
            f"  20d excess vs. SPY: "
            f"{format_percent(
                row.get(
                    'pre_excess_20d'
                )
            )}"
        )


def main():
    universe_name = (
        get_universe_name()
    )

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

    print_experimental_matches(
        scored
    )


if __name__ == "__main__":
    main()