from datetime import timedelta
from decimal import Decimal

from src.database import (
    get_connection,
)
from src.recommendation_engine import (
    get_recommendation,
)
from src.sector_confidence import (
    classify_sector,
    get_strong_sector_stats,
)
from src.signal_scorer import (
    score_event,
)
from src.time_split_statistics import (
    split_by_time,
)


INVESTMENT_PER_TRADE = Decimal("1000")

HORIZONS = [
    "30d",
    "90d",
    "180d",
]


def get_backtest_events():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.ticker,
                    aum.sector,

                    be.period_end,
                    be.entry_date,
                    be.entry_price,

                    be.revenue_yoy,
                    be.revenue_acceleration,
                    be.eps_yoy,
                    be.gross_margin_change,
                    be.operating_margin_change,

                    be.return_30d,
                    be.return_90d,
                    be.return_180d,

                    be.spy_return_30d,
                    be.spy_return_90d,
                    be.spy_return_180d,

                    be.excess_30d,
                    be.excess_90d,
                    be.excess_180d

                FROM backtest_events be

                JOIN securities s
                    ON s.id = be.security_id

                JOIN analysis_universe_members aum
                    ON aum.security_id = s.id

                JOIN analysis_universes au
                    ON au.id = aum.universe_id
                   AND au.name = 'expanded_50'

                ORDER BY
                    be.entry_date,
                    s.ticker;
                """
            )

            rows = cursor.fetchall()

    return [
        {
            "ticker": row[0],
            "sector": row[1],

            "period_end": row[2],
            "entry_date": row[3],
            "entry_price": row[4],

            "revenue_yoy": row[5],
            "revenue_acceleration": row[6],
            "eps_yoy": row[7],
            "gross_margin_change": row[8],
            "operating_margin_change": row[9],

            "return_30d": row[10],
            "return_90d": row[11],
            "return_180d": row[12],

            "spy_return_30d": row[13],
            "spy_return_90d": row[14],
            "spy_return_180d": row[15],

            "excess_30d": row[16],
            "excess_90d": row[17],
            "excess_180d": row[18],
        }
        for row in rows
    ]


def get_known_180d_rows(
    all_rows,
    as_of_date,
):
    known = []

    for row in all_rows:
        entry_date = row.get(
            "entry_date"
        )

        if entry_date is None:
            continue

        if row.get(
            "excess_180d"
        ) is None:
            continue

        result_available_date = (
            entry_date
            + timedelta(
                days=180
            )
        )

        if (
            result_available_date
            <= as_of_date
        ):
            known.append(
                row
            )

    return known


def get_historical_sector_confidence(
    all_rows,
    current_row,
):
    sector = (
        current_row.get("sector")
        or "UNKNOWN"
    )

    as_of_date = current_row[
        "entry_date"
    ]

    known_rows = (
        get_known_180d_rows(
            all_rows,
            as_of_date,
        )
    )

    known_training, known_testing = (
        split_by_time(
            known_rows
        )
    )

    training_stats = (
        get_strong_sector_stats(
            known_training,
            sector,
        )
    )

    testing_stats = (
        get_strong_sector_stats(
            known_testing,
            sector,
        )
    )

    label = classify_sector(
        training_stats,
        testing_stats,
    )

    return {
        "label": label,

        "training_n":
            training_stats["n"],

        "testing_n":
            testing_stats["n"],
    }


def add_historical_recommendations(
    rows,
    all_rows,
):
    results = []

    ordered_rows = sorted(
        rows,
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        ),
    )

    for row in ordered_rows:
        score_result = score_event(
            row
        )

        confidence = (
            get_historical_sector_confidence(
                all_rows,
                row,
            )
        )

        sector_confidence = (
            confidence["label"]
        )

        recommendation = (
            get_recommendation(
                score_result["score"],
                sector_confidence,
            )
        )

        results.append(
            {
                **row,

                "score":
                    score_result[
                        "score"
                    ],

                "sector_confidence":
                    sector_confidence,

                "sector_training_n":
                    confidence[
                        "training_n"
                    ],

                "sector_testing_n":
                    confidence[
                        "testing_n"
                    ],

                "recommendation":
                    recommendation[
                        "label"
                    ],

                "priority":
                    recommendation[
                        "priority"
                    ],
            }
        )

    return results


def get_completed_trades(
    rows,
    horizon,
    minimum_priority,
):
    return [
        row
        for row in rows
        if (
            row["priority"]
            >= minimum_priority
            and row.get(
                f"return_{horizon}"
            )
            is not None
        )
    ]


def calculate_trade_profit(
    return_percent,
):
    if return_percent is None:
        return None

    return (
        INVESTMENT_PER_TRADE
        * return_percent
        / Decimal("100")
    )


def calculate_strategy_stats(
    rows,
    horizon,
    minimum_priority,
):
    trades = get_completed_trades(
        rows,
        horizon,
        minimum_priority,
    )

    if not trades:
        return {
            "trades": 0,
            "invested": Decimal("0"),
            "profit": Decimal("0"),
            "ending_value": Decimal("0"),
            "average_return": None,
            "win_rate": None,
            "spy_profit": Decimal("0"),
            "excess_profit": Decimal("0"),
        }

    profits = []
    returns = []
    spy_profits = []
    excess_profits = []

    for row in trades:
        stock_return = row[
            f"return_{horizon}"
        ]

        spy_return = row[
            f"spy_return_{horizon}"
        ]

        excess_return = row[
            f"excess_{horizon}"
        ]

        returns.append(
            stock_return
        )

        profits.append(
            calculate_trade_profit(
                stock_return
            )
        )

        if spy_return is not None:
            spy_profits.append(
                calculate_trade_profit(
                    spy_return
                )
            )

        if excess_return is not None:
            excess_profits.append(
                calculate_trade_profit(
                    excess_return
                )
            )

    invested = (
        INVESTMENT_PER_TRADE
        * len(trades)
    )

    profit = sum(
        profits,
        Decimal("0"),
    )

    average_return = (
        sum(
            returns,
            Decimal("0"),
        )
        / len(returns)
    )

    winners = sum(
        1
        for value in returns
        if value > 0
    )

    win_rate = (
        Decimal(winners)
        / Decimal(len(returns))
        * Decimal("100")
    )

    spy_profit = sum(
        spy_profits,
        Decimal("0"),
    )

    excess_profit = sum(
        excess_profits,
        Decimal("0"),
    )

    return {
        "trades":
            len(trades),

        "invested":
            invested,

        "profit":
            profit,

        "ending_value":
            invested + profit,

        "average_return":
            average_return,

        "win_rate":
            win_rate,

        "spy_profit":
            spy_profit,

        "excess_profit":
            excess_profit,
    }


def format_money(value):
    if value is None:
        return "-"

    return (
        f"${value:,.2f}"
    )


def format_percent(value):
    if value is None:
        return "-"

    return (
        f"{value:+.2f}%"
    )


def print_period(
    title,
    rows,
):
    print()
    print(title)
    print("=" * 132)

    print(
        f"{'Rule':<22}"
        f"{'Horizon':>10}"
        f"{'Trades':>10}"
        f"{'Invested':>15}"
        f"{'Profit':>15}"
        f"{'End Value':>15}"
        f"{'Avg Return':>14}"
        f"{'Win Rate':>12}"
        f"{'SPY Profit':>15}"
        f"{'Excess $':>14}"
    )

    print("-" * 132)

    for minimum_priority in [
        4,
        3,
        2,
    ]:
        rule = (
            f"Priority {minimum_priority}+"
        )

        for horizon in HORIZONS:
            stats = (
                calculate_strategy_stats(
                    rows,
                    horizon,
                    minimum_priority,
                )
            )

            print(
                f"{rule:<22}"
                f"{horizon:>10}"
                f"{stats['trades']:>10}"
                f"{format_money(stats['invested']):>15}"
                f"{format_money(stats['profit']):>15}"
                f"{format_money(stats['ending_value']):>15}"
                f"{format_percent(stats['average_return']):>14}"
                f"{format_percent(stats['win_rate']):>12}"
                f"{format_money(stats['spy_profit']):>15}"
                f"{format_money(stats['excess_profit']):>14}"
            )

            rule = ""


def print_trade_details(
    title,
    rows,
    horizon="180d",
    minimum_priority=3,
):
    trades = get_completed_trades(
        rows,
        horizon,
        minimum_priority,
    )

    trades.sort(
        key=lambda row: (
            row["entry_date"],
            row["ticker"],
        )
    )

    print()
    print(title)
    print("=" * 175)

    print(
        f"Rule: Priority {minimum_priority}+"
    )

    print(
        f"Investment per trade: "
        f"{format_money(INVESTMENT_PER_TRADE)}"
    )

    print(
        f"Horizon: {horizon}"
    )

    print()

    print(
        f"{'Ticker':<8}"
        f"{'Entry Date':>12}"
        f"{'Priority':>10}"
        f"{'Score':>8}"
        f"{'Sector Conf':<16}"
        f"{'Train N':>9}"
        f"{'Test N':>8}"
        f"{'Return':>12}"
        f"{'Profit':>14}"
        f"{'SPY':>12}"
        f"{'Excess':>12}"
    )

    print("-" * 175)

    for row in trades:
        stock_return = row[
            f"return_{horizon}"
        ]

        spy_return = row[
            f"spy_return_{horizon}"
        ]

        excess_return = row[
            f"excess_{horizon}"
        ]

        profit = calculate_trade_profit(
            stock_return
        )

        print(
            f"{row['ticker']:<8}"
            f"{str(row['entry_date']):>12}"
            f"{row['priority']:>10}"
            f"{row['score']:>8}"
            f"{row['sector_confidence']:<16}"
            f"{row['sector_training_n']:>9}"
            f"{row['sector_testing_n']:>8}"
            f"{format_percent(stock_return):>12}"
            f"{format_money(profit):>14}"
            f"{format_percent(spy_return):>12}"
            f"{format_percent(excess_return):>12}"
        )


def main():
    rows = get_backtest_events()

    training, testing = split_by_time(
        rows
    )

    scored_training = (
        add_historical_recommendations(
            training,
            rows,
        )
    )

    scored_testing = (
        add_historical_recommendations(
            testing,
            rows,
        )
    )

    print()
    print(
        "TIME-AWARE RECOMMENDATION MONEY BACKTEST"
    )

    print(
        "Each historical recommendation "
        f"receives {format_money(INVESTMENT_PER_TRADE)}."
    )

    print(
        "Sector confidence uses only "
        "180-day outcomes available before "
        "each recommendation date."
    )

    print(
        "No later test-period sector results "
        "are allowed to influence earlier trades."
    )

    print()
    print(
        "NOTE: The training period is development/in-sample."
    )

    print(
        "The out-of-sample period is the important "
        "validation result."
    )

    print_period(
        "DEVELOPMENT / TRAINING PERIOD",
        scored_training,
    )

    print_period(
        "OUT-OF-SAMPLE TEST PERIOD",
        scored_testing,
    )

    print_trade_details(
        "OUT-OF-SAMPLE PRIORITY 3+ "
        "COMPLETED 180-DAY TRADES",
        scored_testing,
        horizon="180d",
        minimum_priority=3,
    )


if __name__ == "__main__":
    main()