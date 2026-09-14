from decimal import Decimal

from src.analysis.portfolio_history_stock_performance import (
    build_history,
)
from src.analysis.portfolio_history_stock_performance_summary import (
    get_portfolio_tickers,
)


def percent_change(old_value, new_value):
    if (
        old_value is None
        or new_value is None
        or old_value == 0
    ):
        return None

    return (
        (
            Decimal(str(new_value))
            / Decimal(str(old_value))
        )
        - Decimal("1")
    ) * Decimal("100")


def find_removal(rows):
    """
    Find the first snapshot where a stock is absent
    after previously being held.

    The removal snapshot is only an observation point.
    It is not assumed to be the exact sale date.
    """

    previous_holding = None

    for index, row in enumerate(rows):
        if (
            previous_holding is not None
            and row["held"] is False
        ):
            return index

        previous_holding = (
            row
            if row["held"]
            else None
        )

    return None


def get_removal_row(ticker):
    actual_ticker, rows = build_history(
        ticker
    )

    removal_index = find_removal(
        rows
    )

    if removal_index is None:
        return None

    previous_index = removal_index - 1

    previous_row = rows[
        previous_index
    ]

    removal_row = rows[
        removal_index
    ]

    latest_row = rows[-1]

    previous_value = (
        previous_row["market_value"]
    )

    previous_price = (
        previous_row["adjusted_price"]
    )

    removal_price = (
        removal_row["adjusted_price"]
    )

    latest_price = (
        latest_row["adjusted_price"]
    )

    pre_removal_return = percent_change(
        previous_price,
        removal_price,
    )

    post_removal_return = None

    avoided_gain_loss = None

    if (
        removal_index < len(rows) - 1
        and removal_price is not None
        and latest_price is not None
    ):
        post_removal_return = percent_change(
            removal_price,
            latest_price,
        )

        if (
            previous_value is not None
            and post_removal_return is not None
        ):
            avoided_gain_loss = (
                Decimal(str(previous_value))
                * post_removal_return
                / Decimal("100")
            )

    return {
        "ticker": actual_ticker,
        "last_held": previous_row["month"],
        "first_out": removal_row["month"],
        "last_held_value": previous_value,
        "pre_removal_return": (
            pre_removal_return
        ),
        "post_removal_return": (
            post_removal_return
        ),
        "avoided_gain_loss": (
            avoided_gain_loss
        ),
    }


def format_money(value):
    if value is None:
        return "-"

    return f"${value:,.2f}"


def format_signed_money(value):
    if value is None:
        return "-"

    if value >= 0:
        return f"+${value:,.2f}"

    return f"-${abs(value):,.2f}"


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def get_verdict(post_removal_return):
    if post_removal_return is None:
        return "Too Soon"

    if post_removal_return < 0:
        return "Helped"

    if post_removal_return > 0:
        return "Hurt"

    return "Neutral"


def print_report(rows):
    print()
    print(
        "HISTORICAL PORTFOLIO "
        "REMOVAL DECISION REPORT"
    )
    print("=" * 125)

    print(
        f"{'Ticker':<9}"
        f"{'Last Held':<13}"
        f"{'First Out':<13}"
        f"{'Last Value':>15}"
        f"{'To First Out':>15}"
        f"{'After Removal':>16}"
        f"{'Missed/Avoided $':>19}"
        f"{'Verdict':>14}"
    )

    print("-" * 125)

    for row in rows:
        last_held = (
            row["last_held"]
            .strftime("%Y-%m")
        )

        first_out = (
            row["first_out"]
            .strftime("%Y-%m")
        )

        print(
            f"{row['ticker']:<9}"
            f"{last_held:<13}"
            f"{first_out:<13}"
            f"{format_money(row['last_held_value']):>15}"
            f"{format_percent(row['pre_removal_return']):>15}"
            f"{format_percent(row['post_removal_return']):>16}"
            f"{format_signed_money(row['avoided_gain_loss']):>19}"
            f"{get_verdict(row['post_removal_return']):>14}"
        )

    completed = [
        row
        for row in rows
        if row["post_removal_return"]
        is not None
    ]

    helped = [
        row
        for row in completed
        if row["post_removal_return"] < 0
    ]

    hurt = [
        row
        for row in completed
        if row["post_removal_return"] > 0
    ]

    neutral = [
        row
        for row in completed
        if row["post_removal_return"] == 0
    ]

    print()
    print("SUMMARY")
    print("=" * 60)

    print(
        f"Removal decisions found: "
        f"{len(rows)}"
    )

    print(
        f"With post-removal observation: "
        f"{len(completed)}"
    )

    print(
        f"Helped: "
        f"{len(helped)}"
    )

    print(
        f"Hurt: "
        f"{len(hurt)}"
    )

    print(
        f"Neutral: "
        f"{len(neutral)}"
    )

    if completed:
        average_return = (
            sum(
                row["post_removal_return"]
                for row in completed
            )
            / Decimal(
                len(completed)
            )
        )

        print(
            "Average stock return after removal: "
            f"{average_return:+.2f}%"
        )

        weighted_rows = [
            row
            for row in completed
            if (
                row["last_held_value"]
                is not None
                and row[
                    "avoided_gain_loss"
                ] is not None
            )
        ]

        if weighted_rows:
            total_value = sum(
                Decimal(
                    str(
                        row[
                            "last_held_value"
                        ]
                    )
                )
                for row in weighted_rows
            )

            total_missed_avoided = sum(
                row["avoided_gain_loss"]
                for row in weighted_rows
            )

            weighted_return = (
                total_missed_avoided
                / total_value
                * Decimal("100")
            )

            print(
                "Value-weighted return after removal: "
                f"{weighted_return:+.2f}%"
            )

            print(
                "Estimated missed/avoided change: "
                f"{format_signed_money(total_missed_avoided)}"
            )

            if total_missed_avoided > 0:
                print(
                    "Overall observed result: "
                    "REMOVALS HURT"
                )

            elif total_missed_avoided < 0:
                print(
                    "Overall observed result: "
                    "REMOVALS HELPED"
                )

            else:
                print(
                    "Overall observed result: "
                    "NEUTRAL"
                )

    print()
    print(
        "Interpretation: a negative After Removal "
        "return means selling avoided a later decline "
        "and is labeled Helped."
    )

    print(
        "A positive After Removal return means the "
        "stock subsequently rose and is labeled Hurt."
    )

    print(
        "Missed/Avoided $ estimates what the last known "
        "position value would have gained or lost if it "
        "had remained invested through the latest snapshot."
    )

    print(
        "Positive dollars represent missed gains; "
        "negative dollars represent losses that were avoided."
    )

    print(
        "Snapshot dates are observation dates, not "
        "exact transaction dates."
    )


def main():
    tickers = get_portfolio_tickers()

    rows = []

    for ticker in tickers:
        try:
            row = get_removal_row(
                ticker
            )

            if row is not None:
                rows.append(
                    row
                )

        except Exception as exc:
            print(
                f"WARNING: {ticker}: {exc}"
            )

    rows.sort(
        key=lambda row: (
            row["first_out"],
            row["ticker"],
        )
    )

    print_report(
        rows
    )


if __name__ == "__main__":
    main()