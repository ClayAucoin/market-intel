from decimal import Decimal


REVENUE_ACCELERATION_MIN = Decimal("20")
HORIZON = "30d"

SIGNAL_DESCRIPTION = (
    "Revenue acceleration >= 20% + "
    "operating margin improving + "
    "20-day excess return vs. SPY > 0"
)


def to_decimal(value):
    if value is None:
        return None

    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


def qualifies_experimental_signal(row):
    revenue_acceleration = to_decimal(
        row.get(
            "revenue_acceleration"
        )
    )

    operating_margin_change = to_decimal(
        row.get(
            "operating_margin_change"
        )
    )

    pre_excess_20d = to_decimal(
        row.get(
            "pre_excess_20d"
        )
    )

    if (
        revenue_acceleration is None
        or operating_margin_change is None
        or pre_excess_20d is None
    ):
        return False

    return (
        revenue_acceleration
        >= REVENUE_ACCELERATION_MIN
        and operating_margin_change > 0
        and pre_excess_20d > 0
    )


def get_experimental_signal_events(
    rows,
):
    return [
        row
        for row in rows
        if qualifies_experimental_signal(
            row
        )
    ]