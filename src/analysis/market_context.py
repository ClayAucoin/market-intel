from decimal import Decimal
from math import sqrt

from src.database import (
    get_connection,
)


BENCHMARK = "SPY"


def calculate_return(
    start_price,
    end_price,
):
    if (
        start_price is None
        or end_price is None
        or start_price == 0
    ):
        return None

    return round(
        (
            (
                end_price
                - start_price
            )
            / start_price
        )
        * Decimal("100"),
        2,
    )


def get_prior_prices(
    symbol,
    entry_date,
    limit=61,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    trade_date,
                    adjusted_close

                FROM daily_prices

                WHERE UPPER(symbol) =
                      UPPER(%s)

                  AND trade_date < %s

                  AND adjusted_close
                      IS NOT NULL

                ORDER BY
                    trade_date DESC

                LIMIT %s;
                """,
                (
                    symbol,
                    entry_date,
                    limit,
                ),
            )

            rows = cursor.fetchall()

    prices = [
        {
            "trade_date": row[0],
            "close": Decimal(
                row[1]
            ),
        }
        for row in rows
    ]

    #
    # Database query returns newest first.
    #
    prices.reverse()

    return prices


def get_entry_price_record(
    symbol,
    entry_date,
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

                WHERE UPPER(symbol) =
                      UPPER(%s)

                  AND trade_date = %s

                LIMIT 1;
                """,
                (
                    symbol,
                    entry_date,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "trade_date": row[0],

        "open": (
            Decimal(row[1])
            if row[1] is not None
            else None
        ),

        "close": (
            Decimal(row[2])
            if row[2] is not None
            else None
        ),
    }


def get_trailing_return(
    prices,
    sessions,
):
    #
    # A 20-session return requires
    # 21 closing prices:
    #
    # close[-21] -> close[-1]
    #
    required = sessions + 1

    if len(prices) < required:
        return None

    start_price = prices[
        -required
    ]["close"]

    end_price = prices[
        -1
    ]["close"]

    return calculate_return(
        start_price,
        end_price,
    )


def calculate_daily_returns(
    prices,
):
    returns = []

    for index in range(
        1,
        len(prices),
    ):
        previous = prices[
            index - 1
        ]["close"]

        current = prices[
            index
        ]["close"]

        if previous == 0:
            continue

        daily_return = (
            current - previous
        ) / previous

        returns.append(
            daily_return
        )

    return returns


def calculate_stddev(
    values,
):
    if len(values) < 2:
        return None

    average = (
        sum(values)
        / Decimal(len(values))
    )

    variance = (
        sum(
            (
                value - average
            ) ** 2
            for value in values
        )
        / Decimal(
            len(values) - 1
        )
    )

    return Decimal(
        str(
            sqrt(
                float(variance)
            )
        )
    )


def get_20d_volatility(
    prices,
):
    #
    # Need 21 closes to calculate
    # 20 daily returns.
    #
    if len(prices) < 21:
        return None

    window = prices[
        -21:
    ]

    daily_returns = (
        calculate_daily_returns(
            window
        )
    )

    stddev = calculate_stddev(
        daily_returns
    )

    if stddev is None:
        return None

    #
    # Annualized realized volatility.
    #
    annualized = (
        stddev
        * Decimal(
            str(
                sqrt(252)
            )
        )
        * Decimal("100")
    )

    return round(
        annualized,
        2,
    )


def get_opening_gap(
    symbol,
    entry_date,
):
    prior_prices = get_prior_prices(
        symbol,
        entry_date,
        limit=1,
    )

    if not prior_prices:
        return {
            "previous_close": None,
            "entry_open": None,
            "gap_percent": None,
        }

    entry = get_entry_price_record(
        symbol,
        entry_date,
    )

    if (
        entry is None
        or entry["open"] is None
    ):
        return {
            "previous_close": None,
            "entry_open": None,
            "gap_percent": None,
        }

    previous_close = (
        prior_prices[-1]["close"]
    )

    gap = calculate_return(
        previous_close,
        entry["open"],
    )

    return {
        "previous_close":
            previous_close,

        "entry_open":
            entry["open"],

        "gap_percent":
            gap,
    }


def calculate_market_context(
    symbol,
    entry_date,
    benchmark=BENCHMARK,
):
    stock_prices = get_prior_prices(
        symbol,
        entry_date,
        limit=61,
    )

    benchmark_prices = (
        get_prior_prices(
            benchmark,
            entry_date,
            limit=61,
        )
    )

    stock_20d = get_trailing_return(
        stock_prices,
        20,
    )

    stock_60d = get_trailing_return(
        stock_prices,
        60,
    )

    benchmark_20d = (
        get_trailing_return(
            benchmark_prices,
            20,
        )
    )

    benchmark_60d = (
        get_trailing_return(
            benchmark_prices,
            60,
        )
    )

    excess_20d = None

    if (
        stock_20d is not None
        and benchmark_20d is not None
    ):
        excess_20d = round(
            stock_20d
            - benchmark_20d,
            2,
        )

    excess_60d = None

    if (
        stock_60d is not None
        and benchmark_60d is not None
    ):
        excess_60d = round(
            stock_60d
            - benchmark_60d,
            2,
        )

    volatility_20d = (
        get_20d_volatility(
            stock_prices
        )
    )

    stock_gap = get_opening_gap(
        symbol,
        entry_date,
    )

    benchmark_gap = (
        get_opening_gap(
            benchmark,
            entry_date,
        )
    )

    gap_excess = None

    if (
        stock_gap["gap_percent"]
        is not None
        and benchmark_gap[
            "gap_percent"
        ] is not None
    ):
        gap_excess = round(
            stock_gap[
                "gap_percent"
            ]
            - benchmark_gap[
                "gap_percent"
            ],
            2,
        )

    return {
        "pre_return_20d":
            stock_20d,

        "pre_return_60d":
            stock_60d,

        "pre_excess_20d":
            excess_20d,

        "pre_excess_60d":
            excess_60d,

        "pre_volatility_20d":
            volatility_20d,

        "previous_close":
            stock_gap[
                "previous_close"
            ],

        "entry_open":
            stock_gap[
                "entry_open"
            ],

        "opening_gap_pct":
            stock_gap[
                "gap_percent"
            ],

        "spy_opening_gap_pct":
            benchmark_gap[
                "gap_percent"
            ],

        "opening_gap_excess":
            gap_excess,
    }