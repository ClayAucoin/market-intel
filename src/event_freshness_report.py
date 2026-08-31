from datetime import date
import sys

from src.time_split_statistics import (
    DEFAULT_UNIVERSE,
    get_events,
)


STALE_DAYS = 180


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

        current = latest.get(ticker)

        if (
            current is None
            or entry_date > current["entry_date"]
        ):
            latest[ticker] = row

    return latest


def get_age_days(entry_date):
    return (
        date.today() - entry_date
    ).days


def get_status(age_days):
    if age_days <= STALE_DAYS:
        return "Current"

    return "STALE"


def print_report(latest):
    results = []

    for ticker, row in latest.items():
        entry_date = row["entry_date"]

        age_days = get_age_days(
            entry_date
        )

        results.append(
            {
                "ticker": ticker,
                "sector": (
                    row.get("sector")
                    or "UNKNOWN"
                ),
                "period_end": row.get(
                    "period_end"
                ),
                "entry_date": entry_date,
                "age_days": age_days,
                "status": get_status(
                    age_days
                ),
            }
        )

    results.sort(
        key=lambda item: (
            -item["age_days"],
            item["ticker"],
        )
    )

    print()
    print(
        "FINANCIAL EVENT FRESHNESS REPORT"
    )

    print(
        f"Stale threshold: "
        f"more than {STALE_DAYS} days"
    )

    print("=" * 112)

    print(
        f"{'Ticker':<8}"
        f"{'Sector':<27}"
        f"{'Period End':>13}"
        f"{'Entry Date':>13}"
        f"{'Age Days':>12}"
        f"{'Status':>12}"
    )

    print("-" * 112)

    for item in results:
        print(
            f"{item['ticker']:<8}"
            f"{item['sector']:<27}"
            f"{str(item['period_end']):>13}"
            f"{str(item['entry_date']):>13}"
            f"{item['age_days']:>12}"
            f"{item['status']:>12}"
        )

    stale = [
        item
        for item in results
        if item["status"] == "STALE"
    ]

    current = [
        item
        for item in results
        if item["status"] == "Current"
    ]

    print()
    print(
        "SUMMARY"
    )

    print("=" * 60)

    print(
        f"Companies found: "
        f"{len(results)}"
    )

    print(
        f"Current: "
        f"{len(current)}"
    )

    print(
        f"Stale: "
        f"{len(stale)}"
    )

    if stale:
        print()
        print(
            "STALE COMPANIES"
        )

        print("-" * 60)

        for item in stale:
            print(
                f"{item['ticker']:<8}"
                f"Latest event: "
                f"{item['entry_date']} "
                f"({item['age_days']} days old)"
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

    latest = get_latest_events(
        rows
    )

    print_report(
        latest
    )


if __name__ == "__main__":
    main()