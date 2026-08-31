from datetime import timedelta
from decimal import Decimal

from src.database import get_connection
from src.analysis.event_timing import (
    get_event_entry_date,
    get_financial_events,
)


BACKTEST_HORIZONS = {
    "30d": 30,
    "90d": 90,
    "180d": 180,
}


def get_price_on_date(
    symbol,
    trade_date,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    trade_date,
                    adjusted_open,
                    adjusted_close
                FROM daily_prices
                WHERE symbol = %s
                  AND trade_date = %s
                LIMIT 1;
                """,
                (
                    symbol.upper(),
                    trade_date,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "trade_date": row[0],
        "adjusted_open": (
            Decimal(row[1])
            if row[1] is not None
            else None
        ),
        "adjusted_close": (
            Decimal(row[2])
            if row[2] is not None
            else None
        ),
    }


def get_price_on_or_after(
    symbol,
    target_date,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    trade_date,
                    adjusted_close
                FROM daily_prices
                WHERE symbol = %s
                  AND trade_date >= %s
                ORDER BY trade_date
                LIMIT 1;
                """,
                (
                    symbol.upper(),
                    target_date,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "trade_date": row[0],
        "price": Decimal(row[1]),
    }


def calculate_return(
    entry_price,
    exit_price,
):
    if entry_price == 0:
        return None

    result = (
        (exit_price - entry_price)
        / entry_price
    ) * Decimal("100")

    return round(result, 2)


def backtest_from_entry_date(
    symbol,
    entry_date,
):
    entry_record = get_price_on_date(
        symbol,
        entry_date,
    )

    if entry_record is None:
        return None

    entry_price = entry_record[
        "adjusted_open"
    ]

    if entry_price is None:
        return None

    horizons = {}

    for name, days in BACKTEST_HORIZONS.items():
        target_date = (
            entry_date
            + timedelta(days=days)
        )

        exit_record = get_price_on_or_after(
            symbol,
            target_date,
        )

        if exit_record is None:
            horizons[name] = None
            continue

        horizons[name] = {
            "target_date": target_date,
            "exit_date": exit_record[
                "trade_date"
            ],
            "exit_price": exit_record[
                "price"
            ],
            "return_percent": (
                calculate_return(
                    entry_price,
                    exit_record["price"],
                )
            ),
        }

    return {
        "symbol": symbol.upper(),
        "entry_date": entry_date,
        "entry_price": entry_price,
        "horizons": horizons,
    }


def compare_to_benchmark(
    symbol,
    benchmark,
    entry_date,
):
    stock = backtest_from_entry_date(
        symbol,
        entry_date,
    )

    market = backtest_from_entry_date(
        benchmark,
        entry_date,
    )

    if stock is None or market is None:
        return None

    comparisons = {}

    for horizon in BACKTEST_HORIZONS:
        stock_result = stock[
            "horizons"
        ].get(horizon)

        market_result = market[
            "horizons"
        ].get(horizon)

        if (
            stock_result is None
            or market_result is None
        ):
            comparisons[horizon] = None
            continue

        excess_return = (
            stock_result[
                "return_percent"
            ]
            - market_result[
                "return_percent"
            ]
        )

        comparisons[horizon] = {
            "stock_return": (
                stock_result[
                    "return_percent"
                ]
            ),
            "benchmark_return": (
                market_result[
                    "return_percent"
                ]
            ),
            "excess_return": round(
                excess_return,
                2,
            ),
            "stock_exit_date": (
                stock_result[
                    "exit_date"
                ]
            ),
            "benchmark_exit_date": (
                market_result[
                    "exit_date"
                ]
            ),
        }

    return {
        "symbol": symbol.upper(),
        "benchmark": benchmark.upper(),
        "entry_date": stock[
            "entry_date"
        ],
        "entry_price": stock[
            "entry_price"
        ],
        "comparisons": comparisons,
    }


def backtest_financial_event(
    ticker,
    benchmark,
    event,
):
    entry_date = get_event_entry_date(
        ticker,
        event,
    )

    if entry_date is None:
        return None

    result = compare_to_benchmark(
        ticker,
        benchmark,
        entry_date,
    )

    if result is None:
        return None

    result["period_end"] = event[
        "period_end"
    ]

    result["fiscal_year"] = event[
        "fiscal_year"
    ]

    result["fiscal_period"] = event[
        "fiscal_period"
    ]

    result["filed_date"] = event[
        "filed_date"
    ]

    result["acceptance_datetime"] = event[
        "acceptance_datetime"
    ]

    return result


if __name__ == "__main__":
    ticker = "DELL"
    benchmark = "SPY"

    events = get_financial_events(
        ticker,
        "revenue",
    )

    latest_event = events[-1]

    result = backtest_financial_event(
        ticker,
        benchmark,
        latest_event,
    )

    print()
    print(
        f"{ticker} BACKTEST"
    )
    print("=" * 60)

    print(
        "Period end:",
        result["period_end"],
    )

    print(
        "Filed date:",
        result["filed_date"],
    )

    print(
        "Entry date:",
        result["entry_date"],
    )

    print(
        "Entry price:",
        f"${result['entry_price']:.2f}",
    )

    print()

    for horizon, data in (
        result["comparisons"].items()
    ):
        print(horizon)

        if data is None:
            print(
                "  Not enough future "
                "price data."
            )
            print()
            continue

        print(
            f"  {ticker} return:",
            f"{data['stock_return']:+.2f}%",
        )

        print(
            f"  {benchmark} return:",
            f"{data['benchmark_return']:+.2f}%",
        )

        print(
            "  Excess return:",
            f"{data['excess_return']:+.2f}%",
        )

        print(
            f"  {ticker} exit date:",
            data["stock_exit_date"],
        )

        print()