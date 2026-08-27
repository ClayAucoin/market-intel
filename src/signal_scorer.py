from decimal import Decimal


MAX_SCORE = 6


def to_decimal(value):
    if value is None:
        return None

    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


def classify_score(score):
    if score >= 4:
        return "Strong"

    if score >= 3:
        return "Positive"

    if score >= 2:
        return "Neutral"

    return "Weak"


def score_revenue_acceleration(value):
    value = to_decimal(value)

    if value is None:
        return 0, "Revenue acceleration unavailable"

    if value >= Decimal("20"):
        return (
            2,
            "Revenue acceleration >= 20%",
        )

    return (
        0,
        "Revenue acceleration < 20%",
    )


def score_revenue_growth(value):
    value = to_decimal(value)

    if value is None:
        return 0, "Revenue growth unavailable"

    if value >= Decimal("20"):
        return (
            2,
            "Revenue growth >= 20%",
        )

    if value >= Decimal("10"):
        return (
            1,
            "Revenue growth >= 10%",
        )

    return (
        0,
        "Revenue growth < 10%",
    )


def score_eps_growth(value):
    value = to_decimal(value)

    if value is None:
        return 0, "EPS growth unavailable"

    if value >= Decimal("20"):
        return (
            2,
            "EPS growth >= 20%",
        )

    if value >= Decimal("10"):
        return (
            1,
            "EPS growth >= 10%",
        )

    return (
        0,
        "EPS growth < 10%",
    )


def score_financial_signals(
    revenue_growth=None,
    revenue_acceleration=None,
    eps_growth=None,
):
    components = []

    score, reason = (
        score_revenue_acceleration(
            revenue_acceleration
        )
    )

    components.append(
        {
            "signal": "revenue_acceleration",
            "points": score,
            "reason": reason,
        }
    )

    score, reason = score_revenue_growth(
        revenue_growth
    )

    components.append(
        {
            "signal": "revenue_growth",
            "points": score,
            "reason": reason,
        }
    )

    score, reason = score_eps_growth(
        eps_growth
    )

    components.append(
        {
            "signal": "eps_growth",
            "points": score,
            "reason": reason,
        }
    )

    total_score = sum(
        component["points"]
        for component in components
    )

    return {
        "score": total_score,
        "max_score": MAX_SCORE,
        "classification": classify_score(
            total_score
        ),
        "components": components,
    }


def score_event(row):
    return score_financial_signals(
        revenue_growth=row.get(
            "revenue_yoy"
        ),
        revenue_acceleration=row.get(
            "revenue_acceleration"
        ),
        eps_growth=row.get(
            "eps_yoy"
        ),
    )


def print_score(result):
    print()
    print(
        f"Score: "
        f"{result['score']} / "
        f"{result['max_score']}"
    )

    print(
        f"Classification: "
        f"{result['classification']}"
    )

    print()
    print("Reasons:")

    for component in result[
        "components"
    ]:
        points = component[
            "points"
        ]

        reason = component[
            "reason"
        ]

        print(
            f"  +{points} {reason}"
        )


def main():
    # Simple test case.
    #
    # This should produce:
    #
    # Score: 4 / 6
    # Classification: Strong
    #
    # Revenue acceleration = 15% -> 0
    # Revenue growth = 25%       -> 2
    # EPS growth = 30%           -> 2

    result = score_financial_signals(
        revenue_growth=25,
        revenue_acceleration=15,
        eps_growth=30,
    )

    print_score(
        result
    )


if __name__ == "__main__":
    main()