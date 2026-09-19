from decimal import Decimal

from src.database import get_connection
from psycopg.rows import dict_row
from src.paper_trading.paper_execution import completed_through, eastern_now, positive_price

from src.notifications.notifier import send_notification


ACCOUNT_NAME = "Primary Paper Account"


def format_money(value):
    return f"${value:,.2f}"


def format_percent(value):
    return f"{value:+.2f}%"


def get_account():
    query = """
        SELECT
            id,
            name,
            cash
        FROM paper_accounts
        WHERE name = %s
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (ACCOUNT_NAME,),
            )

            row = cur.fetchone()

    if row is None:
        raise ValueError(
            f"Paper account not found: "
            f"{ACCOUNT_NAME}"
        )

    return {
        "id": row[0],
        "name": row[1],
        "cash": Decimal(
            str(row[2])
        ),
    }


def get_open_positions(
    account_id,
):
    query = """
        SELECT
            id,
            ticker,
            shares,
            invested_amount,
            entry_date,
            entry_price,
            planned_exit_date
        FROM paper_positions
        WHERE account_id = %s
          AND status = 'OPEN'
        ORDER BY
            planned_exit_date,
            ticker,
            id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (account_id,),
            )

            rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "ticker": row[1],
            "shares": Decimal(
                str(row[2])
            ),
            "invested_amount": Decimal(
                str(row[3])
            ),
            "entry_date": row[4],
            "entry_price": Decimal(
                str(row[5])
            ),
            "planned_exit_date": row[6],
        }
        for row in rows
    ]


def get_exit_price(
    ticker,
    planned_exit_date,
):
    query = """
        SELECT
            trade_date,
            adjusted_close
        FROM daily_prices
        WHERE UPPER(symbol) = UPPER(%s)
          AND trade_date >= %s
          AND adjusted_close IS NOT NULL
          AND adjusted_close > 0
          AND adjusted_close < 'Infinity'::numeric
          AND trade_date <= %s
        ORDER BY trade_date
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    ticker,
                    planned_exit_date,
                    completed_through(eastern_now()),
                ),
            )

            row = cur.fetchone()

    if row is None:
        return None

    return {
        "exit_date": row[0],
        "exit_price": Decimal(
            str(row[1])
        ),
    }


def close_position(account, position, exit_data):
    # Same lock order as commitments/fills. Re-read the position after locking;
    # another run may have closed it since the initial list was fetched.
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT cash FROM paper_accounts WHERE id = %s FOR UPDATE",
                        (account["id"],))
            if cur.fetchone() is None:
                raise ValueError("Paper account disappeared during close.")
            cur.execute("""
                SELECT * FROM paper_positions
                WHERE id = %s AND account_id = %s FOR UPDATE
            """, (position["id"], account["id"]))
            current = cur.fetchone()
            if current is None or current["status"] != "OPEN":
                return None
            if (exit_data["exit_date"] < current["planned_exit_date"]
                    or exit_data["exit_date"] > completed_through(eastern_now())
                    or not positive_price(exit_data["exit_price"])):
                raise ValueError("Invalid paper exit date or price.")
            exit_value = current["shares"] * exit_data["exit_price"]
            profit = exit_value - current["invested_amount"]
            return_percent = profit / current["invested_amount"] * Decimal("100")
            cur.execute("""
                UPDATE paper_positions
                SET status = 'CLOSED', exit_date = %s, exit_price = %s,
                    exit_value = %s, profit = %s, return_percent = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND account_id = %s AND status = 'OPEN'
                RETURNING id
            """, (exit_data["exit_date"], exit_data["exit_price"], exit_value,
                  profit, return_percent, current["id"], account["id"]))
            if cur.fetchone() is None:
                return None
            cur.execute("""
                UPDATE paper_accounts
                SET cash = cash + %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s RETURNING cash
            """, (exit_value, account["id"]))
            cash = cur.fetchone()["cash"]
    account["cash"] = cash
    return {
        "ticker": current["ticker"], "entry_date": current["entry_date"],
        "entry_price": current["entry_price"], "exit_date": exit_data["exit_date"],
        "exit_price": exit_data["exit_price"], "invested_amount": current["invested_amount"],
        "exit_value": exit_value, "profit": profit, "return_percent": return_percent,
    }


def send_close_notification(
    result,
):
    subject = (
        f"PAPER POSITION CLOSED: "
        f"{result['ticker']}"
    )

    message = (
        f"Ticker: {result['ticker']}\n"
        f"Entry date: "
        f"{result['entry_date']}\n"
        f"Exit date: "
        f"{result['exit_date']}\n"
        f"Entry price: "
        f"{format_money(result['entry_price'])}\n"
        f"Exit price: "
        f"{format_money(result['exit_price'])}\n"
        f"Invested amount: "
        f"{format_money(result['invested_amount'])}\n"
        f"Exit value: "
        f"{format_money(result['exit_value'])}\n"
        f"Profit/Loss: "
        f"{format_money(result['profit'])}\n"
        f"Return: "
        f"{format_percent(result['return_percent'])}\n\n"
        f"This is a paper-trading result, "
        f"not a live trade."
    )

    send_notification(
        subject=subject,
        message=message,
    )
    
    
def main():
    account = get_account()

    positions = get_open_positions(
        account["id"]
    )

    print()
    print(
        "PAPER POSITION MANAGER"
    )

    print("=" * 80)

    if not positions:
        print(
            "No open paper positions."
        )

        print()

        print(
            f"Available cash: "
            f"{format_money(account['cash'])}"
        )

        return

    closed = []
    waiting = []

    for position in positions:
        exit_data = get_exit_price(
            position["ticker"],
            position[
                "planned_exit_date"
            ],
        )

        if exit_data is None:
            waiting.append(
                position
            )

            continue

        result = close_position(
            account,
            position,
            exit_data,
        )

        if result is None:
            continue

        closed.append(
            result
        )

        send_close_notification(
            result
        )

    print()
    print(
        "CLOSED POSITIONS"
    )

    print("-" * 80)

    if not closed:
        print(
            "No positions are ready "
            "to close."
        )

    else:
        for item in closed:
            print()

            print(
                f"{item['ticker']} "
                f"| "
                f"{item['entry_date']} "
                f"-> "
                f"{item['exit_date']}"
            )

            print(
                f"  Entry:  "
                f"${item['entry_price']}"
            )

            print(
                f"  Exit:   "
                f"${item['exit_price']}"
            )

            print(
                f"  Profit: "
                f"{format_money(item['profit'])}"
            )

            print(
                f"  Return: "
                f"{format_percent(item['return_percent'])}"
            )

    print()
    print(
        "WAITING POSITIONS"
    )

    print("-" * 80)

    if not waiting:
        print(
            "None"
        )

    else:
        for position in waiting:
            print(
                f"{position['ticker']} "
                f"| planned exit "
                f"{position['planned_exit_date']}"
            )

    print()

    print(
        f"Available cash: "
        f"{format_money(account['cash'])}"
    )


if __name__ == "__main__":
    main()
