from src.sector_confidence import (
    build_sector_confidence_map,
)
from src.signal_scorer import (
    score_event,
)
from src.time_split_statistics import (
    format_percent,
    get_events,
    split_by_time,
)


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
                    confidence[
                        "label"
                    ],
            }
        )

    return results


def print_results(results):
    print()
    print(
        "LATEST FINANCIAL SIGNAL REPORT"
    )

    print("=" * 150)

    print(
        f"{'Ticker':<8}"
        f"{'Sector':<25}"
        f"{'Entry Date':>12}"
        f"{'Score':>8}"
        f"{'Class':>12}"
        f"{'Sector Conf':>16}"
        f"{'Rev Growth':>14}"
        f"{'Rev Accel':>14}"
        f"{'EPS Growth':>14}"
    )

    print("-" * 150)

    for item in results:
        row = item["row"]

        print(
            f"{row['ticker']:<8}"
            f"{(row.get('sector') or 'UNKNOWN'):<25}"
            f"{str(row['entry_date']):>12}"
            f"{item['score']:>8}"
            f"{item['classification']:>12}"
            f"{item['sector_confidence']:>16}"
            f"{format_percent(row.get('revenue_yoy')):>14}"
            f"{format_percent(row.get('revenue_acceleration')):>14}"
            f"{format_percent(row.get('eps_yoy')):>14}"
        )


def print_strong_details(results):
    strong = [
        item
        for item in results
        if item["score"] >= 4
    ]

    print()
    print(
        "STRONG SIGNAL DETAILS"
    )

    print("=" * 100)

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
            f"| {item['classification']} "
            f"| Sector confidence: "
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

        for component in item[
            "components"
        ]:
            print(
                f"  +{component['points']} "
                f"{component['reason']}"
            )


def main():
    rows = get_events()

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
            item["score"],
            item["row"]["entry_date"],
        ),
        reverse=True,
    )

    print_results(
        scored
    )

    print_strong_details(
        scored
    )


if __name__ == "__main__":
    main()