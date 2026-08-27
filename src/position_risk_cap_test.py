from datetime import timedelta
from decimal import Decimal

from src.capital_constrained_backtest import (
    STARTING_CASH,
    TRADE_SIZE,
    build_candidate_trades,
)
from src.recommendation_backtest import (
    get_backtest_events,
)
from src.time_split_statistics import (
    split_by_time,
)


HOLDING_DAYS = 180


def format_money(value):
    return f"${value:,.2f}"


def format_percent(value):
    return f"{value:+.2f}%"


def get_candidates():
    rows = get_backtest_events()

    training, testing = split_by_time(
        rows
    )

    return build_candidate_trades(
        testing,
        rows,
    )


def close_due_positions(
    positions,
    cash,
    current_date,
):
    still_open = []
    closed = []

    for position in positions:
        if position["exit_date"] <= current_date:
            cash += position["exit_value"]
            closed.append(position)
        else:
            still_open.append(position)

    return (
        still_open,
        cash,
        closed,
    )


def get_ticker_exposure(
    positions,
    ticker,
):
    return sum(
        (
            position["investment"]
            for position in positions
            if position["ticker"] == ticker
        ),
        Decimal("0"),
    )


def get_total_invested(
    positions,
):
    return sum(
        (
            position["investment"]
            for position in positions
        ),
        Decimal("0"),
    )


def get_portfolio_value_for_cap(
    cash,
    positions,
):
    return (
        cash
        + get_total_invested(
            positions
        )
    )


def build_position(
    row,
):
    stock_return = row[
        "return_180d"
    ]

    profit = (
        TRADE_SIZE
        * stock_return
        / Decimal("100")
    )

    return {
        "ticker":
            row["ticker"],

        "entry_date":
            row["entry_date"],

        "exit_date":
            (
                row["entry_date"]
                + timedelta(
                    days=HOLDING_DAYS
                )
            ),

        "investment":
            TRADE_SIZE,

        "return":
            stock_return,

        "profit":
            profit,

        "exit_value":
            TRADE_SIZE + profit,
    }


def simulate_with_cap(
    candidates,
    dollar_cap=None,
    percent_cap=None,
):
    cash = STARTING_CASH

    open_positions = []
    completed = []

    skipped_cash = 0
    skipped_cap = 0

    max_ticker_exposure = Decimal("0")

    for row in candidates:
        entry_date = row[
            "entry_date"
        ]

        (
            open_positions,
            cash,
            closed,
        ) = close_due_positions(
            open_positions,
            cash,
            entry_date,
        )

        completed.extend(
            closed
        )

        if cash < TRADE_SIZE:
            skipped_cash += 1
            continue

        ticker = row[
            "ticker"
        ]

        current_exposure = (
            get_ticker_exposure(
                open_positions,
                ticker,
            )
        )

        proposed_exposure = (
            current_exposure
            + TRADE_SIZE
        )

        if dollar_cap is not None:
            if (
                proposed_exposure
                > dollar_cap
            ):
                skipped_cap += 1
                continue

        if percent_cap is not None:
            portfolio_value = (
                get_portfolio_value_for_cap(
                    cash,
                    open_positions,
                )
            )

            maximum_allowed = (
                portfolio_value
                * percent_cap
                / Decimal("100")
            )

            if (
                proposed_exposure
                > maximum_allowed
            ):
                skipped_cap += 1
                continue

        position = build_position(
            row
        )

        open_positions.append(
            position
        )

        cash -= TRADE_SIZE

        exposure_after_buy = (
            get_ticker_exposure(
                open_positions,
                ticker,
            )
        )

        if (
            exposure_after_buy
            > max_ticker_exposure
        ):
            max_ticker_exposure = (
                exposure_after_buy
            )

    for position in open_positions:
        cash += position[
            "exit_value"
        ]

        completed.append(
            position
        )

    return {
        "cash":
            cash,

        "completed":
            completed,

        "skipped_cash":
            skipped_cash,

        "skipped_cap":
            skipped_cap,

        "max_ticker_exposure":
            max_ticker_exposure,
    }


def calculate_stats(
    result,
):
    completed = result[
        "completed"
    ]

    final_value = result[
        "cash"
    ]

    profit = (
        final_value
        - STARTING_CASH
    )

    total_return = (
        profit
        / STARTING_CASH
        * Decimal("100")
    )

    winners = sum(
        1
        for trade in completed
        if trade["profit"] > 0
    )

    win_rate = (
        Decimal(winners)
        / Decimal(len(completed))
        * Decimal("100")
        if completed
        else Decimal("0")
    )

    return {
        "trades":
            len(completed),

        "win_rate":
            win_rate,

        "profit":
            profit,

        "final_value":
            final_value,

        "return":
            total_return,

        "skipped_cash":
            result[
                "skipped_cash"
            ],

        "skipped_cap":
            result[
                "skipped_cap"
            ],

        "max_ticker_exposure":
            result[
                "max_ticker_exposure"
            ],
    }


def print_results(
    candidates,
):
    tests = [
        (
            "Unlimited",
            {
                "dollar_cap": None,
                "percent_cap": None,
            },
        ),

        (
            "$2,000/ticker",
            {
                "dollar_cap":
                    Decimal("2000"),

                "percent_cap":
                    None,
            },
        ),

        (
            "$3,000/ticker",
            {
                "dollar_cap":
                    Decimal("3000"),

                "percent_cap":
                    None,
            },
        ),

        (
            "20% portfolio/ticker",
            {
                "dollar_cap":
                    None,

                "percent_cap":
                    Decimal("20"),
            },
        ),

        (
            "30% portfolio/ticker",
            {
                "dollar_cap":
                    None,

                "percent_cap":
                    Decimal("30"),
            },
        ),
    ]

    print()
    print(
        "POSITION RISK CAP TEST"
    )

    print("=" * 145)

    print(
        f"{'Policy':<26}"
        f"{'Trades':>9}"
        f"{'Win Rate':>12}"
        f"{'Cash Skip':>11}"
        f"{'Cap Skip':>10}"
        f"{'Max Ticker $':>15}"
        f"{'Profit':>16}"
        f"{'Final Value':>18}"
        f"{'Return':>13}"
    )

    print("-" * 145)

    for name, settings in tests:
        result = simulate_with_cap(
            candidates,
            dollar_cap=settings[
                "dollar_cap"
            ],
            percent_cap=settings[
                "percent_cap"
            ],
        )

        stats = calculate_stats(
            result
        )

        print(
            f"{name:<26}"
            f"{stats['trades']:>9}"
            f"{format_percent(stats['win_rate']):>12}"
            f"{stats['skipped_cash']:>11}"
            f"{stats['skipped_cap']:>10}"
            f"{format_money(stats['max_ticker_exposure']):>15}"
            f"{format_money(stats['profit']):>16}"
            f"{format_money(stats['final_value']):>18}"
            f"{format_percent(stats['return']):>13}"
        )


def print_cap_skips(
    candidates,
    dollar_cap,
    title,
):
    cash = STARTING_CASH
    open_positions = []

    print()
    print(title)
    print("=" * 100)

    found = False

    for row in candidates:
        entry_date = row[
            "entry_date"
        ]

        (
            open_positions,
            cash,
            closed,
        ) = close_due_positions(
            open_positions,
            cash,
            entry_date,
        )

        if cash < TRADE_SIZE:
            continue

        ticker = row[
            "ticker"
        ]

        current_exposure = (
            get_ticker_exposure(
                open_positions,
                ticker,
            )
        )

        proposed_exposure = (
            current_exposure
            + TRADE_SIZE
        )

        if (
            proposed_exposure
            > dollar_cap
        ):
            found = True

            print(
                f"{entry_date}  "
                f"{ticker:<6}  "
                f"Current: "
                f"{format_money(current_exposure):>10}  "
                f"Proposed: "
                f"{format_money(proposed_exposure):>10}  "
                f"SKIPPED"
            )

            continue

        position = build_position(
            row
        )

        open_positions.append(
            position
        )

        cash -= TRADE_SIZE

    if not found:
        print(
            "No signals skipped by this cap."
        )


def main():
    candidates = get_candidates()

    print_results(
        candidates
    )

    print_cap_skips(
        candidates,
        Decimal("2000"),
        "$2,000 PER-TICKER CAP SKIPS",
    )


if __name__ == "__main__":
    main()