from datetime import timedelta
from decimal import Decimal

from src.database import get_connection


BACKTEST_HORIZONS = {
    "30d": 30,
    "90d": 90,
    "180d": 180,
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


def backtest_symbol(
    symbol,
    signal_date,
):
    entry = get_price_on_or_after(
        symbol,
        signal_date,
    )

    if entry is None:
        return None

    horizons = {}

    for name, days in BACKTEST_HORIZONS.items():
        target_date = (
            entry["trade_date"]
            + timedelta(days=days)
        )

        exit_price = get_price_on_or_after(
            symbol,
            target_date,
        )

        if exit_price is None:
            horizons[name] = None
            continue

        horizons[name] = {
            "target_date": target_date,
            "exit_date": exit_price[
                "trade_date"
            ],
            "exit_price": exit_price[
                "price"
            ],
            "return_percent": (
                calculate_return(
                    entry["price"],
                    exit_price["price"],
                )
            ),
        }

    return {
        "symbol": symbol.upper(),
        "signal_date": signal_date,
        "entry_date": entry[
            "trade_date"
        ],
        "entry_price": entry[
            "price"
        ],
        "horizons": horizons,
    }


def compare_to_benchmark(
    symbol,
    benchmark,
    signal_date,
):
    stock = backtest_symbol(
        symbol,
        signal_date,
    )

    market = backtest_symbol(
        benchmark,
        signal_date,
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
            comparisons[
                horizon
            ] = None

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
        "signal_date": signal_date,
        "entry_date": stock[
            "entry_date"
        ],
        "entry_price": stock[
            "entry_price"
        ],
        "comparisons": comparisons,
    }


if __name__ == "__main__":
    #
    # Dell's FY2027 Q1 10-Q filing date.
    #
    signal_date = "2026-06-09"

    result = compare_to_benchmark(
        "DELL",
        "SPY",
        signal_date,
    )

    print()
    print(
        "DELL BACKTEST"
    )
    print("=" * 60)

    print(
        "Signal date:",
        result["signal_date"],
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
            continue

        print(
            "  DELL return:",
            f"{data['stock_return']:+.2f}%",
        )

        print(
            "  SPY return:",
            f"{data['benchmark_return']:+.2f}%",
        )

        print(
            "  Excess return:",
            f"{data['excess_return']:+.2f}%",
        )

        print(
            "  DELL exit date:",
            data["stock_exit_date"],
        )

        print()