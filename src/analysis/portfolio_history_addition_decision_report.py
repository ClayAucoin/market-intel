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


def find_addition(rows):
    """
    Find the first snapshot where a stock is held after
    previously being absent.

    Stocks already present in the first available snapshot
    are not treated as additions because their actual
    addition occurred before our available history.
    """

    for index in range(1, len(rows)):
        if (
            not rows[index - 1]["held"]
            and rows[index]["held"]
        ):
            return index

    return None


def get_addition_row(ticker):
    actual_ticker, rows = build_history(
        ticker
    )

    addition_index = find_addition(
        rows
    )

    if addition_index is None:
        return None

    addition_row = rows[
        addition_index
    ]

    latest_row = rows[-1]

    addition_price = (
        addition_row["adjusted_price"]
    )

    latest_price = (
        latest_row["adjusted_price"]
    )

    addition_value = (
        addition_row["market_value"]
    )

    post_addition_return = None
    estimated_gain_loss = None

    if (
        addition_index < len(rows) - 1
        and addition_price is not None
        and latest_price is not None
    ):
        post_addition_return = percent_change(
            addition_price,
            latest_price,
        )

        if (
            addition_value is not None
            and post_addition_return is not None
        ):
            estimated_gain_loss = (
                Decimal(str(addition_value))
                * post_addition_return
                / Decimal("100")
            )

    return {
        "ticker": actual_ticker,
        "first_held": addition_row["month"],
        "addition_value": addition_value,
        "post_addition_return": (
            post_addition_return
        ),
        "estimated_gain_loss": (
            estimated_gain_loss
        ),
        "currently_held": (
            latest_row["held"]
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


def get_verdict(post_addition_return):
    if post_addition_return is None:
        return "Too Soon"

    if post_addition_return > 0:
        return "Helped"

    if post_addition_return < 0:
        return "Hurt"

    return "Neutral"


def print_report(rows):
    print()
    print(
        "HISTORICAL PORTFOLIO "
        "ADDITION DECISION REPORT"
    )
    print("=" * 110)

    print(
        f"{'Ticker':<9}"
        f"{'First Held':<13}"
        f"{'Initial Value':>16}"
        f"{'After Addition':>17}"
        f"{'Estimated $':>17}"
        f"{'Current':>11}"
        f"{'Verdict':>14}"
    )

    print("-" * 110)

    for row in rows:
        first_held = (
            row["first_held"]
            .strftime("%Y-%m")
        )

        print(
            f"{row['ticker']:<9}"
            f"{first_held:<13}"
            f"{format_money(row['addition_value']):>16}"
            f"{format_percent(row['post_addition_return']):>17}"
            f"{format_signed_money(row['estimated_gain_loss']):>17}"
            f"{'Yes' if row['currently_held'] else 'No':>11}"
            f"{get_verdict(row['post_addition_return']):>14}"
        )

    completed = [
        row
        for row in rows
        if row["post_addition_return"]
        is not None
    ]

    helped = [
        row
        for row in completed
        if row["post_addition_return"] > 0
    ]

    hurt = [
        row
        for row in completed
        if row["post_addition_return"] < 0
    ]

    neutral = [
        row
        for row in completed
        if row["post_addition_return"] == 0
    ]

    print()
    print("SUMMARY")
    print("=" * 60)

    print(
        f"Addition decisions found: "
        f"{len(rows)}"
    )

    print(
        f"With post-addition observation: "
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
                row["post_addition_return"]
                for row in completed
            )
            / Decimal(len(completed))
        )

        print(
            "Average stock return after addition: "
            f"{average_return:+.2f}%"
        )

        weighted_rows = [
            row
            for row in completed
            if (
                row["addition_value"] is not None
                and row["estimated_gain_loss"] is not None
            )
        ]

        if weighted_rows:
            total_value = sum(
                Decimal(
                    str(row["addition_value"])
                )
                for row in weighted_rows
            )

            total_gain_loss = sum(
                row["estimated_gain_loss"]
                for row in weighted_rows
            )

            weighted_return = (
                total_gain_loss
                / total_value
                * Decimal("100")
            )

            print(
                "Value-weighted return after addition: "
                f"{weighted_return:+.2f}%"
            )

            print(
                "Estimated gain/loss: "
                f"{format_signed_money(total_gain_loss)}"
            )

            if total_gain_loss > 0:
                print(
                    "Overall observed result: "
                    "ADDITIONS HELPED"
                )

            elif total_gain_loss < 0:
                print(
                    "Overall observed result: "
                    "ADDITIONS HURT"
                )

            else:
                print(
                    "Overall observed result: "
                    "NEUTRAL"
                )

    print()
    print(
        "After Addition measures adjusted-price "
        "performance from the first snapshot where "
        "the stock is known to be held through the "
        "latest available snapshot."
    )

    print(
        "Estimated $ applies that return to the "
        "position's value at the first held snapshot."
    )

    print(
        "Snapshot dates are observation dates, not "
        "exact transaction dates."
    )

    print(
        "Stocks already held in the first available "
        "snapshot are excluded because their actual "
        "addition dates are unknown."
    )


def main():
    tickers = get_portfolio_tickers()

    rows = []

    for ticker in tickers:
        try:
            row = get_addition_row(
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
            row["first_held"],
            row["ticker"],
        )
    )

    print_report(
        rows
    )


if __name__ == "__main__":
    main()