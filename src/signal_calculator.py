from decimal import Decimal

from src.database import get_connection


def get_metric_history(ticker, metric):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ff.fiscal_year,
                    ff.fiscal_period,
                    ff.period_end,
                    ff.value,
                    ff.is_derived
                FROM financial_facts ff

                JOIN companies c
                    ON c.id = ff.company_id

                WHERE UPPER(c.ticker) = UPPER(%s)
                  AND ff.metric = %s

                ORDER BY ff.period_end;
                """,
                (
                    ticker,
                    metric,
                ),
            )

            rows = cursor.fetchall()

    return [
        {
            "fiscal_year": row[0],
            "fiscal_period": row[1],
            "period_end": row[2],
            "value": Decimal(row[3]),
            "is_derived": row[4],
        }
        for row in rows
    ]


def calculate_growth(
    current_value,
    previous_value,
):
    if previous_value == 0:
        return None

    growth = (
        (current_value - previous_value)
        / previous_value
    ) * Decimal("100")

    return round(growth, 2)


def calculate_yoy_growth(history):
    results = []

    for index, quarter in enumerate(history):
        result = {
            **quarter,
            "yoy_growth": None,
            "revenue_acceleration": None,
        }

        # Four quarters earlier is the comparable
        # quarter from the previous fiscal year.
        if index >= 4:
            previous_year_quarter = history[
                index - 4
            ]

            result["yoy_growth"] = calculate_growth(
                quarter["value"],
                previous_year_quarter["value"],
            )

        results.append(result)

    return results


def calculate_acceleration(history):
    results = calculate_yoy_growth(history)

    previous_growth = None

    for item in results:
        current_growth = item["yoy_growth"]

        if (
            current_growth is not None
            and previous_growth is not None
        ):
            item["revenue_acceleration"] = round(
                current_growth - previous_growth,
                2,
            )

        if current_growth is not None:
            previous_growth = current_growth

    return results


def get_revenue_signals(ticker):
    history = get_metric_history(
        ticker,
        "revenue",
    )

    return calculate_acceleration(history)


if __name__ == "__main__":
    ticker = "DELL"

    signals = get_revenue_signals(
        ticker
    )

    print(
        f"{ticker} revenue growth analysis"
    )

    print()

    print(
        f"{'Period':<12}"
        f"{'Revenue':>14}"
        f"{'YoY Growth':>14}"
        f"{'Acceleration':>16}"
    )

    print("-" * 56)

    for item in signals[-12:]:
        revenue_billions = (
            item["value"]
            / Decimal("1000000000")
        )

        yoy = item["yoy_growth"]

        acceleration = item[
            "revenue_acceleration"
        ]

        yoy_text = (
            f"{yoy:.2f}%"
            if yoy is not None
            else "-"
        )

        acceleration_text = (
            f"{acceleration:+.2f} pts"
            if acceleration is not None
            else "-"
        )

        print(
            f"{str(item['period_end']):<12}"
            f"${revenue_billions:>11.3f}B"
            f"{yoy_text:>14}"
            f"{acceleration_text:>16}"
        )