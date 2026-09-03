import sys
from datetime import timedelta
from decimal import Decimal

from src.analysis.experimental_signal import (
    SIGNAL_DESCRIPTION,
    get_experimental_signal_events,
)
from src.backtesting.backtester import (
    get_price_on_date,
    get_price_on_or_after,
)
from src.backtesting.time_split_statistics import (
    TRAIN_END,
    TEST_START,
    get_events,
    split_by_time,
)


DEFAULT_UNIVERSE = "expanded_500"

STARTING_CAPITAL = Decimal("10000")
HOLDING_DAYS = 45

POSITION_SIZES = [
    Decimal("500"),
    Decimal("750"),
    Decimal("1000"),
]

STRESS_LOSSES = [
    Decimal("-20"),
    Decimal("-30"),
    Decimal("-40"),
    Decimal("-50"),
    Decimal("-75"),
    Decimal("-100"),
]


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


def format_money(value):
    return f"${value:,.2f}"


def format_percent(value):
    if value is None:
        return "N/A"

    return f"{value:+.2f}%"


def extract_price(result):
    if result is None:
        return None

    if isinstance(
        result,
        Decimal,
    ):
        return result

    if isinstance(
        result,
        (int, float, str),
    ):
        return Decimal(
            str(result)
        )

    if isinstance(
        result,
        dict,
    ):
        for key in (
            "adjusted_open",
            "adjusted_close",
            "open",
            "close",
            "price",
        ):
            value = result.get(
                key
            )

            if value is not None:
                return Decimal(
                    str(value)
                )

        return None

    if isinstance(
        result,
        (tuple, list),
    ):
        for value in reversed(
            result
        ):
            try:
                return Decimal(
                    str(value)
                )
            except Exception:
                continue

        return None

    return None


def get_45_day_return(row):
    ticker = row["ticker"]
    entry_date = row["entry_date"]

    entry_result = get_price_on_date(
        ticker,
        entry_date,
    )

    entry_price = extract_price(
        entry_result
    )

    if entry_price is None:
        return None

    target_exit_date = (
        entry_date
        + timedelta(
            days=HOLDING_DAYS
        )
    )

    exit_result = get_price_on_or_after(
        ticker,
        target_exit_date,
    )

    exit_price = extract_price(
        exit_result
    )

    if exit_price is None:
        return None

    if entry_price <= 0:
        return None

    return (
        (
            exit_price
            - entry_price
        )
        / entry_price
        * Decimal("100")
    )


def calculate_position_loss(
    position_size,
    loss_percent,
):
    return (
        position_size
        * loss_percent
        / Decimal("100")
    )


def calculate_account_impact(
    position_size,
    loss_percent,
):
    position_loss = (
        calculate_position_loss(
            position_size,
            loss_percent,
        )
    )

    account_impact = (
        position_loss
        / STARTING_CAPITAL
        * Decimal("100")
    )

    return (
        position_loss,
        account_impact,
    )


def get_signal_return_stats(
    rows,
):
    matches = (
        get_experimental_signal_events(
            rows
        )
    )

    returns = []
    missing = 0

    for row in matches:
        result = get_45_day_return(
            row
        )

        if result is None:
            missing += 1
            continue

        returns.append(
            result
        )

    if not returns:
        return {
            "signals":
                len(matches),

            "completed":
                0,

            "missing":
                missing,

            "worst_45d":
                None,

            "loss_20":
                0,

            "loss_30":
                0,

            "loss_40":
                0,

            "loss_50":
                0,
        }

    return {
        "signals":
            len(matches),

        "completed":
            len(returns),

        "missing":
            missing,

        "worst_45d":
            min(returns),

        "loss_20":
            sum(
                1
                for value in returns
                if value <= Decimal("-20")
            ),

        "loss_30":
            sum(
                1
                for value in returns
                if value <= Decimal("-30")
            ),

        "loss_40":
            sum(
                1
                for value in returns
                if value <= Decimal("-40")
            ),

        "loss_50":
            sum(
                1
                for value in returns
                if value <= Decimal("-50")
            ),
    }


def print_historical_context(
    title,
    rows,
):
    stats = get_signal_return_stats(
        rows
    )

    print()
    print(title)
    print("=" * 90)

    print(
        "Signal matches:",
        stats["signals"],
    )

    print(
        "Completed 45-day outcomes:",
        stats["completed"],
    )

    print(
        "Missing/incomplete:",
        stats["missing"],
    )

    print(
        "Worst 45-day stock return:",
        format_percent(
            stats["worst_45d"]
        ),
    )

    print(
        "Outcomes <= -20%:",
        stats["loss_20"],
    )

    print(
        "Outcomes <= -30%:",
        stats["loss_30"],
    )

    print(
        "Outcomes <= -40%:",
        stats["loss_40"],
    )

    print(
        "Outcomes <= -50%:",
        stats["loss_50"],
    )


def print_stress_table():
    print()
    print(
        "SINGLE-POSITION LOSS STRESS"
    )
    print("=" * 105)

    print(
        f"{'Position':>12}"
        f"{'Position %':>14}"
        f"{'Stock Loss':>14}"
        f"{'Dollar Loss':>16}"
        f"{'Account Impact':>18}"
    )

    print("-" * 105)

    for position_size in POSITION_SIZES:
        position_percent = (
            position_size
            / STARTING_CAPITAL
            * Decimal("100")
        )

        for loss_percent in STRESS_LOSSES:
            (
                dollar_loss,
                account_impact,
            ) = calculate_account_impact(
                position_size,
                loss_percent,
            )

            print(
                f"{format_money(position_size):>12}"
                f"{format_percent(position_percent):>14}"
                f"{format_percent(loss_percent):>14}"
                f"{format_money(dollar_loss):>16}"
                f"{format_percent(account_impact):>18}"
            )

        print()


def print_multi_position_stress():
    print()
    print(
        "$1,000 POSITION CLUSTER STRESS"
    )
    print("=" * 105)

    print(
        f"{'Positions':>12}"
        f"{'Loss Each':>14}"
        f"{'Capital Exposed':>18}"
        f"{'Dollar Loss':>16}"
        f"{'Account Impact':>18}"
    )

    print("-" * 105)

    position_size = Decimal("1000")

    scenarios = [
        (2, Decimal("-20")),
        (3, Decimal("-20")),
        (5, Decimal("-20")),
        (2, Decimal("-30")),
        (3, Decimal("-30")),
        (5, Decimal("-30")),
        (2, Decimal("-40")),
        (3, Decimal("-40")),
        (5, Decimal("-40")),
        (2, Decimal("-50")),
        (3, Decimal("-50")),
        (5, Decimal("-50")),
    ]

    for (
        count,
        loss_percent,
    ) in scenarios:
        capital_exposed = (
            position_size
            * Decimal(count)
        )

        dollar_loss = (
            capital_exposed
            * loss_percent
            / Decimal("100")
        )

        account_impact = (
            dollar_loss
            / STARTING_CAPITAL
            * Decimal("100")
        )

        print(
            f"{count:>12}"
            f"{format_percent(loss_percent):>14}"
            f"{format_money(capital_exposed):>18}"
            f"{format_money(dollar_loss):>16}"
            f"{format_percent(account_impact):>18}"
        )


def main():
    universe_name = (
        get_universe_name()
    )

    rows = get_events(
        universe_name
    )

    training, testing = (
        split_by_time(
            rows
        )
    )

    print()
    print(
        "EXPERIMENTAL SIGNAL "
        "POSITION LOSS STRESS TEST"
    )

    print("=" * 100)

    print(
        "Universe:",
        universe_name,
    )

    print(
        "Signal:",
        SIGNAL_DESCRIPTION,
    )

    print(
        "Starting capital:",
        format_money(
            STARTING_CAPITAL
        ),
    )

    print(
        "Holding period:",
        f"{HOLDING_DAYS} calendar days",
    )

    print(
        "Training through:",
        TRAIN_END,
    )

    print(
        "Out-of-sample from:",
        TEST_START,
    )

    print_historical_context(
        "TRAINING — HISTORICAL 45-DAY LOSS CONTEXT",
        training,
    )

    print_historical_context(
        "OUT-OF-SAMPLE — HISTORICAL 45-DAY LOSS CONTEXT",
        testing,
    )

    print_stress_table()

    print_multi_position_stress()


if __name__ == "__main__":
    main()