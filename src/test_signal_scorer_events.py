import sys

from src.signal_scorer import (
    print_score,
    score_event,
)
from src.time_split_statistics import (
    DEFAULT_UNIVERSE,
    get_events,
)


def format_value(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def print_event(row):
    result = score_event(row)

    print()
    print("=" * 80)

    print(
        f"{row.get('ticker', '-')}"
        f" | Period End: {row.get('period_end', '-')}"
        f" | Entry Date: {row.get('entry_date', '-')}"
    )

    print("-" * 80)

    print(
        "Revenue Growth:       "
        f"{format_value(row.get('revenue_yoy'))}"
    )

    print(
        "Revenue Acceleration: "
        f"{format_value(row.get('revenue_acceleration'))}"
    )

    print(
        "EPS Growth:           "
        f"{format_value(row.get('eps_yoy'))}"
    )

    print_score(result)

    print()
    print("Future excess returns:")

    print(
        "  30d:  "
        f"{format_value(row.get('excess_30d'))}"
    )

    print(
        "  90d:  "
        f"{format_value(row.get('excess_90d'))}"
    )

    print(
        "  180d: "
        f"{format_value(row.get('excess_180d'))}"
    )


def main():
    universe_name = (
        sys.argv[1]
        if len(sys.argv) >= 2
        else DEFAULT_UNIVERSE
    )

    rows = get_events(
        universe_name
    )

    scored_rows = []

    for row in rows:
        result = score_event(row)

        scored_rows.append(
            (
                result["score"],
                row,
            )
        )

    scored_rows.sort(
        key=lambda item: (
            item[0],
            item[1].get("entry_date"),
        ),
        reverse=True,
    )

    print()
    print("REAL HISTORICAL EVENT SCORER TEST")

    print(
        f"Events loaded: {len(scored_rows)}"
    )

    print()
    print(
        "Showing the first 10 highest-scoring "
        "historical events."
    )

    for score, row in scored_rows[:10]:
        print_event(row)


if __name__ == "__main__":
    main()