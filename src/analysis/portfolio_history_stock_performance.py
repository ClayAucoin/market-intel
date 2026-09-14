from argparse import ArgumentParser
from decimal import Decimal

from src.database import get_connection


PORTFOLIO_NAME = "Historical Portfolio"


def get_daily_price_columns(cursor):
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'daily_prices';
        """
    )

    columns = {
        row[0]
        for row in cursor.fetchall()
    }

    date_candidates = [
        "date",
        "price_date",
        "trade_date",
    ]

    price_candidates = [
        "adjusted_close",
        "adj_close",
        "close",
    ]

    date_column = next(
        (
            column
            for column in date_candidates
            if column in columns
        ),
        None,
    )

    price_column = next(
        (
            column
            for column in price_candidates
            if column in columns
        ),
        None,
    )

    if date_column is None:
        raise RuntimeError(
            "Could not determine the date column "
            "in daily_prices."
        )

    if price_column is None:
        raise RuntimeError(
            "Could not determine the adjusted-price "
            "column in daily_prices."
        )

    return date_column, price_column


def get_snapshots(cursor):
    cursor.execute(
        """
        SELECT
            id,
            snapshot_month,
            source_filename
        FROM portfolio_snapshots
        WHERE portfolio_name = %s
        ORDER BY snapshot_month;
        """,
        (
            PORTFOLIO_NAME,
        ),
    )

    return [
        {
            "id": row[0],
            "month": row[1],
            "source_filename": row[2],
        }
        for row in cursor.fetchall()
    ]


def get_security(cursor, ticker):
    cursor.execute(
        """
        SELECT
            id,
            ticker
        FROM securities
        WHERE UPPER(ticker) = UPPER(%s)
        LIMIT 1;
        """,
        (
            ticker,
        ),
    )

    row = cursor.fetchone()

    if row is None:
        raise RuntimeError(
            f"Security not found: {ticker}"
        )

    return {
        "security_id": row[0],
        "ticker": row[1],
    }


def get_snapshot_holding(
    cursor,
    snapshot_id,
    security_id,
):
    cursor.execute(
        """
        SELECT
            ticker,
            description,
            price,
            shares,
            market_value,
            cost_basis,
            gain_loss
        FROM portfolio_snapshot_holdings
        WHERE snapshot_id = %s
          AND security_id = %s;
        """,
        (
            snapshot_id,
            security_id,
        ),
    )

    row = cursor.fetchone()

    if row is None:
        return None

    return {
        "ticker": row[0],
        "description": row[1],
        "price": row[2],
        "shares": row[3],
        "market_value": row[4],
        "cost_basis": row[5],
        "gain_loss": row[6],
    }


def get_adjusted_price(
    cursor,
    ticker,
    target_date,
    date_column,
    price_column,
):
    allowed_date_columns = {
        "date",
        "price_date",
        "trade_date",
    }

    allowed_price_columns = {
        "adjusted_close",
        "adj_close",
        "close",
    }

    if date_column not in allowed_date_columns:
        raise RuntimeError(
            f"Unexpected date column: {date_column}"
        )

    if price_column not in allowed_price_columns:
        raise RuntimeError(
            f"Unexpected price column: {price_column}"
        )

    query = f"""
        SELECT
            {date_column},
            {price_column}
        FROM daily_prices
        WHERE symbol = %s
          AND {date_column} >= %s
          AND {date_column} <= %s + INTERVAL '7 days'
          AND {price_column} IS NOT NULL
        ORDER BY {date_column}
        LIMIT 1;
    """

    cursor.execute(
        query,
        (
            ticker,
            target_date,
            target_date,
        ),
    )

    row = cursor.fetchone()

    if row is not None:
        return {
            "date": row[0],
            "price": Decimal(str(row[1])),
        }

    query = f"""
        SELECT
            {date_column},
            {price_column}
        FROM daily_prices
        WHERE symbol = %s
          AND {date_column} <= %s
          AND {price_column} IS NOT NULL
        ORDER BY {date_column} DESC
        LIMIT 1;
    """

    cursor.execute(
        query,
        (
            ticker,
            target_date,
        ),
    )

    row = cursor.fetchone()

    if row is None:
        return None

    return {
        "date": row[0],
        "price": Decimal(str(row[1])),
    }


def percent_change(old_value, new_value):
    if (
        old_value is None
        or new_value is None
        or old_value == 0
    ):
        return None

    return (
        (new_value / old_value)
        - Decimal("1")
    ) * Decimal("100")


def determine_action(
    holding,
    previous_holding,
    ever_held_before,
):
    if previous_holding is None:
        if holding is None:
            return "Out"

        if ever_held_before:
            return "Re-added"

        return "Added"

    if holding is None:
        return "Removed"

    old_shares = Decimal(
        str(previous_holding["shares"])
    )

    new_shares = Decimal(
        str(holding["shares"])
    )

    difference = new_shares - old_shares

    tolerance = Decimal("0.000001")

    if difference > tolerance:
        return "Increased"

    if difference < -tolerance:
        return "Reduced"

    return "Held"


def format_money(value):
    if value is None:
        return "-"

    return f"${value:,.2f}"


def format_shares(value):
    if value is None:
        return "-"

    return f"{value:,.4f}"


def format_percent(value):
    if value is None:
        return "-"

    return f"{value:+.2f}%"


def build_history(ticker):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            date_column, price_column = (
                get_daily_price_columns(cursor)
            )

            security = get_security(
                cursor,
                ticker,
            )

            snapshots = get_snapshots(
                cursor
            )

            if not snapshots:
                raise RuntimeError(
                    "No Historical Portfolio "
                    "snapshots were found."
                )

            rows = []

            previous_holding = None
            previous_market_price = None
            ever_held = False

            for snapshot in snapshots:
                holding = get_snapshot_holding(
                    cursor,
                    snapshot["id"],
                    security["security_id"],
                )

                market_price = get_adjusted_price(
                    cursor,
                    security["ticker"],
                    snapshot["month"],
                    date_column,
                    price_column,
                )

                current_price = (
                    market_price["price"]
                    if market_price
                    else None
                )

                period_return = percent_change(
                    previous_market_price,
                    current_price,
                )

                action = determine_action(
                    holding,
                    previous_holding,
                    ever_held,
                )

                if holding is not None:
                    ever_held = True

                rows.append(
                    {
                        "month": snapshot["month"],
                        "held": holding is not None,
                        "shares": (
                            holding["shares"]
                            if holding
                            else None
                        ),
                        "snapshot_price": (
                            holding["price"]
                            if holding
                            else None
                        ),
                        "market_value": (
                            holding["market_value"]
                            if holding
                            else None
                        ),
                        "adjusted_price": current_price,
                        "price_date": (
                            market_price["date"]
                            if market_price
                            else None
                        ),
                        "period_return": period_return,
                        "action": action,
                    }
                )

                previous_holding = holding
                previous_market_price = current_price

    return (
        security["ticker"],
        rows,
    )


def print_report(ticker, rows):
    print()
    print(
        f"HISTORICAL PORTFOLIO STOCK PERFORMANCE: "
        f"{ticker}"
    )
    print("=" * 138)

    print(
        f"{'Month':<12}"
        f"{'Held':<8}"
        f"{'Shares':>13}"
        f"{'Snapshot Px':>15}"
        f"{'Position Value':>18}"
        f"{'Adj Price':>14}"
        f"{'Price Date':>13}"
        f"{'Period Return':>16}"
        f"{'Action':>16}"
    )

    print("-" * 138)

    for row in rows:
        month_label = row["month"].strftime("%Y-%m")

        print(
            f"{month_label:<12}"
            f"{'Yes' if row['held'] else 'No':<8}"
            f"{format_shares(row['shares']):>13}"
            f"{format_money(row['snapshot_price']):>15}"
            f"{format_money(row['market_value']):>18}"
            f"{format_money(row['adjusted_price']):>14}"
            f"{str(row['price_date'] or '-'):>13}"
            f"{format_percent(row['period_return']):>16}"
            f"{row['action']:>16}"
        )

    print()
    print(
        "Period Return uses adjusted market prices "
        "between consecutive available portfolio snapshots."
    )

    print(
        "It continues measuring the stock even during "
        "months when the portfolio does not own it."
    )

    print(
        "If a monthly snapshot is missing, the return spans "
        "the gap between the available snapshots."
    )

    print(
        "Snapshot Px and Position Value come from the "
        "portfolio source document when the stock was held."
    )


def main():
    parser = ArgumentParser(
        description=(
            "Show a stock's performance across "
            "Historical Portfolio snapshots."
        )
    )

    parser.add_argument(
        "ticker",
        help="Ticker symbol, for example AAPL.",
    )

    args = parser.parse_args()

    ticker, rows = build_history(
        args.ticker.strip().upper()
    )

    print_report(
        ticker,
        rows,
    )


if __name__ == "__main__":
    main()