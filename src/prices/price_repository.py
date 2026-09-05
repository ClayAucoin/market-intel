from datetime import datetime

from src.database import get_connection


def parse_trade_date(value):
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).date()


def get_latest_price_date(symbol):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT MAX(trade_date)
                FROM daily_prices
                WHERE symbol = %s;
                """,
                (
                    symbol.upper(),
                ),
            )

            row = cursor.fetchone()

    if (
        row is None
        or row[0] is None
    ):
        return None

    return row[0]


def save_daily_prices(
    symbol,
    prices,
):
    rows = []

    for price in prices:
        adjusted_open = price.get(
            "adjOpen"
        )

        if adjusted_open is None:
            adjusted_open = price.get(
                "open"
            )

        rows.append(
            (
                symbol.upper(),

                parse_trade_date(
                    price["date"]
                ),

                price.get("open"),
                price.get("high"),
                price.get("low"),
                price.get("close"),

                adjusted_open,

                price.get("adjClose"),
                price.get("volume"),
                price.get("divCash"),
                price.get("splitFactor"),
            )
        )

    if not rows:
        print(
            f"No price records found "
            f"for {symbol}."
        )

        return 0

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO daily_prices (
                    symbol,
                    trade_date,

                    open,
                    high,
                    low,
                    close,

                    adjusted_open,
                    adjusted_close,

                    volume,
                    dividend_cash,
                    split_factor
                )
                VALUES (
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s
                )

                ON CONFLICT (
                    symbol,
                    trade_date
                )
                DO UPDATE SET
                    open =
                        EXCLUDED.open,

                    high =
                        EXCLUDED.high,

                    low =
                        EXCLUDED.low,

                    close =
                        EXCLUDED.close,

                    adjusted_open =
                        EXCLUDED.adjusted_open,

                    adjusted_close =
                        EXCLUDED.adjusted_close,

                    volume =
                        EXCLUDED.volume,

                    dividend_cash =
                        EXCLUDED.dividend_cash,

                    split_factor =
                        EXCLUDED.split_factor,

                    updated_at =
                        CURRENT_TIMESTAMP;
                """,
                rows,
            )

    print(
        f"Saved {len(rows):,} "
        f"{symbol.upper()} price records."
    )

    return len(rows)