from decimal import Decimal

from src.analysis.signal_calculator import (
    calculate_acceleration,
    get_metric_history,
)


def percent_change(
    current_value,
    previous_value,
):
    if previous_value == 0:
        return None

    change = (
        (current_value - previous_value)
        / abs(previous_value)
    ) * Decimal("100")

    return round(change, 2)


def find_metric_by_period(
    history,
    period_end,
):
    for item in history:
        if item["period_end"] == period_end:
            return item

    return None


def get_latest_yoy_metric(
    ticker,
    metric,
):
    history = get_metric_history(
        ticker,
        metric,
    )

    if len(history) < 5:
        return None

    latest = history[-1]
    previous_year = history[-5]

    growth = percent_change(
        latest["value"],
        previous_year["value"],
    )

    return {
        "metric": metric,
        "period_end": latest["period_end"],
        "current_value": latest["value"],
        "previous_year_value": previous_year["value"],
        "yoy_growth": growth,
    }


def get_revenue_signal(ticker):
    history = get_metric_history(
        ticker,
        "revenue",
    )

    signals = calculate_acceleration(
        history
    )

    if not signals:
        return None

    latest = signals[-1]

    return {
        "period_end": latest["period_end"],
        "revenue": latest["value"],
        "yoy_growth": latest["yoy_growth"],
        "acceleration": latest[
            "revenue_acceleration"
        ],
    }


def get_margin_signals(ticker):
    revenue_history = get_metric_history(
        ticker,
        "revenue",
    )

    gross_profit_history = get_metric_history(
        ticker,
        "gross_profit",
    )

    operating_income_history = (
        get_metric_history(
            ticker,
            "operating_income",
        )
    )

    if not revenue_history:
        return None

    latest_revenue = revenue_history[-1]

    period_end = latest_revenue[
        "period_end"
    ]

    gross_profit = find_metric_by_period(
        gross_profit_history,
        period_end,
    )

    operating_income = (
        find_metric_by_period(
            operating_income_history,
            period_end,
        )
    )

    if (
        gross_profit is None
        or operating_income is None
    ):
        return None

    revenue = latest_revenue["value"]

    if revenue == 0:
        return None

    gross_margin = (
        gross_profit["value"]
        / revenue
    ) * Decimal("100")

    operating_margin = (
        operating_income["value"]
        / revenue
    ) * Decimal("100")

    #
    # Compare with the same quarter
    # one year earlier.
    #
    if len(revenue_history) < 5:
        return None

    prior_revenue = revenue_history[-5]

    prior_period_end = prior_revenue[
        "period_end"
    ]

    prior_gross_profit = (
        find_metric_by_period(
            gross_profit_history,
            prior_period_end,
        )
    )

    prior_operating_income = (
        find_metric_by_period(
            operating_income_history,
            prior_period_end,
        )
    )

    prior_gross_margin = None
    prior_operating_margin = None

    gross_margin_change = None
    operating_margin_change = None

    if (
        prior_gross_profit is not None
        and prior_revenue["value"] != 0
    ):
        prior_gross_margin = (
            prior_gross_profit["value"]
            / prior_revenue["value"]
        ) * Decimal("100")

        gross_margin_change = (
            gross_margin
            - prior_gross_margin
        )

    if (
        prior_operating_income is not None
        and prior_revenue["value"] != 0
    ):
        prior_operating_margin = (
            prior_operating_income["value"]
            / prior_revenue["value"]
        ) * Decimal("100")

        operating_margin_change = (
            operating_margin
            - prior_operating_margin
        )

    return {
        "period_end": period_end,

        "gross_margin": round(
            gross_margin,
            2,
        ),

        "prior_gross_margin": (
            round(
                prior_gross_margin,
                2,
            )
            if prior_gross_margin
            is not None
            else None
        ),

        "gross_margin_change": (
            round(
                gross_margin_change,
                2,
            )
            if gross_margin_change
            is not None
            else None
        ),

        "operating_margin": round(
            operating_margin,
            2,
        ),

        "prior_operating_margin": (
            round(
                prior_operating_margin,
                2,
            )
            if prior_operating_margin
            is not None
            else None
        ),

        "operating_margin_change": (
            round(
                operating_margin_change,
                2,
            )
            if operating_margin_change
            is not None
            else None
        ),
    }


def get_financial_signals(ticker):
    return {
        "ticker": ticker.upper(),

        "revenue": get_revenue_signal(
            ticker
        ),

        "net_income": get_latest_yoy_metric(
            ticker,
            "net_income",
        ),

        "diluted_eps": get_latest_yoy_metric(
            ticker,
            "diluted_eps",
        ),

        "margins": get_margin_signals(
            ticker
        ),
    }


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def format_points(value):
    if value is None:
        return "-"

    return f"{value:+.2f} pts"


if __name__ == "__main__":
    ticker = "DELL"

    signals = get_financial_signals(
        ticker
    )

    print()
    print(
        f"{ticker} FINANCIAL SIGNALS"
    )
    print("=" * 50)

    revenue = signals["revenue"]

    if revenue:
        print()
        print("REVENUE")
        print(
            "YoY growth:",
            format_percent(
                revenue["yoy_growth"]
            ),
        )

        print(
            "Growth acceleration:",
            format_points(
                revenue["acceleration"]
            ),
        )

    net_income = signals["net_income"]

    if net_income:
        print()
        print("NET INCOME")
        print(
            "YoY growth:",
            format_percent(
                net_income["yoy_growth"]
            ),
        )

    eps = signals["diluted_eps"]

    if eps:
        print()
        print("DILUTED EPS")
        print(
            "YoY growth:",
            format_percent(
                eps["yoy_growth"]
            ),
        )

    margins = signals["margins"]

    if margins:
        print()
        print("MARGINS")

        print(
            "Gross margin:",
            f"{margins['gross_margin']:.2f}%",
        )

        print(
            "Gross margin YoY change:",
            format_points(
                margins[
                    "gross_margin_change"
                ]
            ),
        )

        print(
            "Operating margin:",
            f"{margins['operating_margin']:.2f}%",
        )

        print(
            "Operating margin YoY change:",
            format_points(
                margins[
                    "operating_margin_change"
                ]
            ),
        )

    print()