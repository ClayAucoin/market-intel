from decimal import Decimal

from src.database import get_connection


ACCOUNT_NAME = "Primary Paper Account"


def format_money(value):
    if value is None:
        return "$0.00"

    return f"${Decimal(str(value)):,.2f}"


def format_percent(value):
    if value is None:
        return "N/A"

    return f"{Decimal(str(value)):+.2f}%"


def get_account():
    query = """
        SELECT
            id,
            name,
            starting_cash,
            cash,
            trade_size,
            ticker_cap_percent,
            minimum_priority,
            holding_days,
            created_at
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
        "starting_cash": Decimal(
            str(row[2])
        ),
        "cash": Decimal(
            str(row[3])
        ),
        "trade_size": Decimal(
            str(row[4])
        ),
        "ticker_cap_percent": Decimal(
            str(row[5])
        ),
        "minimum_priority": int(
            row[6]
        ),
        "holding_days": int(
            row[7]
        ),
        "created_at": row[8],
    }


def get_open_positions(
    account_id,
):
    query = """
        SELECT
            pp.ticker,
            pp.entry_date,
            pp.entry_price,
            pp.shares,
            pp.invested_amount,
            pp.planned_exit_date,
            ps.score,
            ps.priority,
            ps.recommendation,
            ps.sector_confidence,
            ps.revenue_acceleration,
            ps.operating_margin_change,
            ps.pre_excess_20d
        FROM paper_positions pp
        JOIN paper_signals ps
          ON ps.id = pp.signal_id
        WHERE pp.account_id = %s
          AND pp.status = 'OPEN'
        ORDER BY
            pp.entry_date,
            pp.ticker
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
            "ticker": row[0],
            "entry_date": row[1],
            "entry_price": row[2],
            "shares": row[3],
            "invested_amount": row[4],
            "planned_exit_date": row[5],
            "score": row[6],
            "priority": row[7],
            "recommendation": row[8],
            "sector_confidence": row[9],
            "revenue_acceleration": row[10],
            "operating_margin_change": row[11],
            "pre_excess_20d": row[12],
        }
        for row in rows
    ]


def get_closed_positions(
    account_id,
):
    query = """
        SELECT
            pp.ticker,
            pp.entry_date,
            pp.exit_date,
            pp.invested_amount,
            pp.exit_value,
            pp.profit,
            pp.return_percent,
            ps.score,
            ps.priority,
            ps.recommendation,
            ps.sector_confidence,
            ps.revenue_acceleration,
            ps.operating_margin_change,
            ps.pre_excess_20d
        FROM paper_positions pp
        JOIN paper_signals ps
          ON ps.id = pp.signal_id
        WHERE pp.account_id = %s
          AND pp.status = 'CLOSED'
        ORDER BY
            pp.exit_date,
            pp.ticker
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
            "ticker": row[0],
            "entry_date": row[1],
            "exit_date": row[2],
            "invested_amount": row[3],
            "exit_value": row[4],
            "profit": row[5],
            "return_percent": row[6],
            "score": row[7],
            "priority": row[8],
            "recommendation": row[9],
            "sector_confidence": row[10],
            "revenue_acceleration": row[11],
            "operating_margin_change": row[12],
            "pre_excess_20d": row[13],
        }
        for row in rows
    ]


def get_signal_summary(
    account_id,
):
    query = """
        SELECT
            action,
            COUNT(*)
        FROM paper_signals
        WHERE account_id = %s
        GROUP BY action
        ORDER BY action
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (account_id,),
            )

            rows = cur.fetchall()

    return {
        row[0]: row[1]
        for row in rows
    }


def print_signal_details(position):
    print(
        f"  Revenue acceleration: "
        f"{format_percent(
            position['revenue_acceleration']
        )}"
    )

    print(
        f"  Operating margin change: "
        f"{format_percent(
            position['operating_margin_change']
        )}"
    )

    print(
        f"  20d excess vs. SPY: "
        f"{format_percent(
            position['pre_excess_20d']
        )}"
    )


def main():
    account = get_account()

    open_positions = get_open_positions(
        account["id"]
    )

    closed_positions = get_closed_positions(
        account["id"]
    )

    signal_summary = get_signal_summary(
        account["id"]
    )

    open_invested = sum(
        (
            Decimal(
                str(position[
                    "invested_amount"
                ])
            )
            for position
            in open_positions
        ),
        Decimal("0"),
    )

    realized_profit = sum(
        (
            Decimal(
                str(position["profit"])
            )
            for position
            in closed_positions
            if position["profit"]
            is not None
        ),
        Decimal("0"),
    )

    account_value_cost_basis = (
        account["cash"]
        + open_invested
    )

    total_return = (
        (
            account_value_cost_basis
            - account[
                "starting_cash"
            ]
        )
        / account[
            "starting_cash"
        ]
        * Decimal("100")
    )

    wins = sum(
        1
        for position
        in closed_positions
        if (
            position["profit"]
            is not None
            and Decimal(
                str(position["profit"])
            ) > 0
        )
    )

    losses = sum(
        1
        for position
        in closed_positions
        if (
            position["profit"]
            is not None
            and Decimal(
                str(position["profit"])
            ) < 0
        )
    )

    print()
    print(
        "PAPER TRADING REPORT"
    )

    print("=" * 100)

    print(
        f"Account:              "
        f"{account['name']}"
    )

    print(
        f"Started:              "
        f"{account['created_at']}"
    )

    print(
        f"Starting cash:        "
        f"{format_money(account['starting_cash'])}"
    )

    print(
        f"Available cash:       "
        f"{format_money(account['cash'])}"
    )

    print(
        f"Open invested:        "
        f"{format_money(open_invested)}"
    )

    print(
        f"Account value*:       "
        f"{format_money(account_value_cost_basis)}"
    )

    print(
        f"Realized profit:      "
        f"{format_money(realized_profit)}"
    )

    print(
        f"Return*:              "
        f"{format_percent(total_return)}"
    )

    print()

    print(
        "* Open positions are currently "
        "valued at cost basis."
    )

    print()

    print(
        "STRATEGY"
    )

    print("-" * 100)

    print(
        "Qualification:        "
        "Revenue acceleration >= 20%"
    )

    print(
        "                      "
        "Operating margin improving"
    )

    print(
        "                      "
        "20-day excess return vs. SPY > 0"
    )

    print(
        f"Holding period:       "
        f"{account['holding_days']} days"
    )

    print(
        f"Trade size:           "
        f"{format_money(account['trade_size'])}"
    )

    print(
        f"Ticker cap:           "
        f"{account['ticker_cap_percent']}%"
    )

    print(
        f"Minimum priority:     "
        f"{account['minimum_priority']} "
        f"(reporting only)"
    )

    print()

    print(
        "SIGNALS"
    )

    print("-" * 100)

    if not signal_summary:
        print(
            "No paper signals recorded."
        )

    else:
        for action, count in (
            signal_summary.items()
        ):
            print(
                f"{action:<20}"
                f"{count:>5}"
            )

    print()

    print(
        "OPEN POSITIONS"
    )

    print("-" * 100)

    if not open_positions:
        print(
            "No open positions."
        )

    else:
        for position in open_positions:
            print()

            print(
                f"{position['ticker']} "
                f"| Priority "
                f"{position['priority']} "
                f"| Score "
                f"{position['score']}"
            )

            print(
                f"  Recommendation: "
                f"{position['recommendation']}"
            )

            print(
                f"  Sector confidence: "
                f"{position['sector_confidence']}"
            )

            print_signal_details(
                position
            )

            print(
                f"  Entry date: "
                f"{position['entry_date']}"
            )

            print(
                f"  Entry price: "
                f"{format_money(position['entry_price'])}"
            )

            print(
                f"  Invested: "
                f"{format_money(position['invested_amount'])}"
            )

            print(
                f"  Shares: "
                f"{position['shares']}"
            )

            print(
                f"  Planned exit: "
                f"{position['planned_exit_date']}"
            )

    print()

    print(
        "CLOSED POSITIONS"
    )

    print("-" * 100)

    if not closed_positions:
        print(
            "No closed positions."
        )

    else:
        for position in closed_positions:
            print()

            print(
                f"{position['ticker']} "
                f"| Priority "
                f"{position['priority']} "
                f"| Score "
                f"{position['score']}"
            )

            print(
                f"  Recommendation: "
                f"{position['recommendation']}"
            )

            print(
                f"  Sector confidence: "
                f"{position['sector_confidence']}"
            )

            print_signal_details(
                position
            )

            print(
                f"  "
                f"{position['entry_date']} "
                f"-> "
                f"{position['exit_date']}"
            )

            print(
                f"  Invested: "
                f"{format_money(position['invested_amount'])}"
            )

            print(
                f"  Exit value: "
                f"{format_money(position['exit_value'])}"
            )

            print(
                f"  Profit: "
                f"{format_money(position['profit'])}"
            )

            print(
                f"  Return: "
                f"{format_percent(position['return_percent'])}"
            )

    print()

    print(
        "RESULTS"
    )

    print("-" * 100)

    print(
        f"Open positions:       "
        f"{len(open_positions)}"
    )

    print(
        f"Closed positions:     "
        f"{len(closed_positions)}"
    )

    print(
        f"Winners:              "
        f"{wins}"
    )

    print(
        f"Losers:               "
        f"{losses}"
    )


if __name__ == "__main__":
    main()