from datetime import datetime

from src.database import get_connection


def parse_trade_date(value):
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).date()


def save_daily_prices(
    symbol,
    prices,
):
    rows = []

    for price in prices:
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
        return

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
                    adjusted_close,
                    volume,
                    dividend_cash,
                    split_factor
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
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