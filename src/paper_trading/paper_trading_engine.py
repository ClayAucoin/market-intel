from datetime import date
from decimal import Decimal

from src.database import get_connection
from src.analysis.experimental_signal import (
    SIGNAL_DESCRIPTION,
    qualifies_experimental_signal,
)
from src.analysis.latest_signal_report import (
    add_scores,
)
from src.notifications.notifier import (
    send_notification,
)
from src.analysis.sector_confidence import (
    build_sector_confidence_map,
)
from src.backtesting.time_split_statistics import (
    get_events,
    split_by_time,
)


ACCOUNT_NAME = "Primary Paper Account"


def format_money(value):
    return f"${value:,.2f}"


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
        "starting_cash":
            Decimal(str(row[2])),
        "cash":
            Decimal(str(row[3])),
        "trade_size":
            Decimal(str(row[4])),
        "ticker_cap_percent":
            Decimal(str(row[5])),
        "minimum_priority":
            int(row[6]),
        "holding_days":
            int(row[7]),
        "created_at":
            row[8],
    }


def get_event_ids(
    ticker,
    period_end,
    entry_date,
):
    query = """
        SELECT
            s.id,
            be.id
        FROM backtest_events be
        JOIN securities s
          ON s.id = be.security_id
        WHERE UPPER(s.ticker) = UPPER(%s)
          AND be.period_end = %s
          AND be.entry_date = %s
        ORDER BY
            s.is_primary DESC,
            be.id DESC
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    ticker,
                    period_end,
                    entry_date,
                ),
            )

            row = cur.fetchone()

    if row is None:
        return None

    return {
        "security_id": row[0],
        "backtest_event_id": row[1],
    }


def get_entry_price(
    ticker,
    entry_date,
):
    query = """
        SELECT adjusted_open
        FROM daily_prices
        WHERE UPPER(symbol) = UPPER(%s)
          AND trade_date = %s
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    ticker,
                    entry_date,
                ),
            )

            row = cur.fetchone()

    if (
        row is None
        or row[0] is None
    ):
        return None

    return Decimal(
        str(row[0])
    )


def get_existing_signal(
    account_id,
    security_id,
    signal_date,
):
    query = """
        SELECT
            id,
            action,
            action_reason
        FROM paper_signals
        WHERE account_id = %s
          AND security_id = %s
          AND signal_date = %s
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    account_id,
                    security_id,
                    signal_date,
                ),
            )

            row = cur.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "action": row[1],
        "action_reason": row[2],
    }


def get_open_positions(
    account_id,
):
    query = """
        SELECT
            id,
            ticker,
            invested_amount
        FROM paper_positions
        WHERE account_id = %s
          AND status = 'OPEN'
        ORDER BY entry_date, id
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
            "invested_amount":
                Decimal(str(row[2])),
        }
        for row in rows
    ]


def get_ticker_exposure(
    positions,
    ticker,
):
    return sum(
        (
            position[
                "invested_amount"
            ]
            for position in positions
            if (
                position["ticker"].upper()
                == ticker.upper()
            )
        ),
        Decimal("0"),
    )


def get_total_invested(
    positions,
):
    return sum(
        (
            position[
                "invested_amount"
            ]
            for position in positions
        ),
        Decimal("0"),
    )


def determine_action(
    account,
    item,
    entry_price,
):
    ticker = item["row"]["ticker"]

    if entry_price is None:
        return {
            "action": "WAIT",
            "reason":
                "Entry-day market price is "
                "not available yet.",
        }

    positions = get_open_positions(
        account["id"]
    )

    if (
        account["cash"]
        < account["trade_size"]
    ):
        return {
            "action": "SKIP_CASH",
            "reason":
                "Available paper cash is below "
                "the required trade size.",
        }

    ticker_exposure = (
        get_ticker_exposure(
            positions,
            ticker,
        )
    )

    proposed_exposure = (
        ticker_exposure
        + account["trade_size"]
    )

    portfolio_value_for_cap = (
        account["cash"]
        + get_total_invested(
            positions
        )
    )

    maximum_allowed = (
        portfolio_value_for_cap
        * account[
            "ticker_cap_percent"
        ]
        / Decimal("100")
    )

    if (
        proposed_exposure
        > maximum_allowed
    ):
        return {
            "action": "SKIP_CAP",
            "reason":
                (
                    f"Proposed {ticker} "
                    f"exposure would be "
                    f"{format_money(proposed_exposure)}, "
                    f"above the "
                    f"{account['ticker_cap_percent']}% "
                    f"portfolio cap of "
                    f"{format_money(maximum_allowed)}."
                ),
        }

    return {
        "action": "BUY",
        "reason":
            "Experimental signal passed: "
            f"{SIGNAL_DESCRIPTION}. "
            "Cash and per-ticker risk cap "
            "also passed.",
    }


def insert_or_update_signal(
    cur,
    account,
    item,
    ids,
    action,
    existing,
):
    row = item["row"]

    if existing is not None:
        query = """
            UPDATE paper_signals
            SET
                action = %s,
                action_reason = %s
            WHERE id = %s
            RETURNING id
        """

        cur.execute(
            query,
            (
                action["action"],
                action["reason"],
                existing["id"],
            ),
        )

        return cur.fetchone()[0]

    query = """
        INSERT INTO paper_signals (
            account_id,
            security_id,
            backtest_event_id,
            ticker,
            sector,
            signal_date,
            period_end,
            score,
            classification,
            sector_confidence,
            recommendation,
            priority,
            recommendation_reason,
            revenue_yoy,
            revenue_acceleration,
            eps_yoy,
            operating_margin_change,
            pre_excess_20d,
            action,
            action_reason
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s
        )
        RETURNING id
    """

    cur.execute(
        query,
        (
            account["id"],
            ids["security_id"],
            ids["backtest_event_id"],
            row["ticker"],
            row.get("sector"),
            row["entry_date"],
            row.get("period_end"),
            item["score"],
            item["classification"],
            item["sector_confidence"],
            item["recommendation"],
            item["priority"],
            item[
                "recommendation_reason"
            ],
            row.get("revenue_yoy"),
            row.get(
                "revenue_acceleration"
            ),
            row.get("eps_yoy"),
            row.get(
                "operating_margin_change"
            ),
            row.get(
                "pre_excess_20d"
            ),
            action["action"],
            action["reason"],
        ),
    )

    return cur.fetchone()[0]


def open_position_in_transaction(
    cur,
    account,
    signal_id,
    item,
    ids,
    entry_price,
):
    row = item["row"]

    shares = (
        account["trade_size"]
        / entry_price
    )

    insert_position = """
        INSERT INTO paper_positions (
            account_id,
            signal_id,
            security_id,
            ticker,
            status,
            entry_date,
            entry_price,
            shares,
            invested_amount,
            planned_exit_date
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            'OPEN',
            %s,
            %s,
            %s,
            %s,
            %s + (%s * INTERVAL '1 day')
        )
    """

    cur.execute(
        insert_position,
        (
            account["id"],
            signal_id,
            ids["security_id"],
            row["ticker"],
            row["entry_date"],
            entry_price,
            shares,
            account["trade_size"],
            row["entry_date"],
            account["holding_days"],
        ),
    )

    update_account = """
        UPDATE paper_accounts
        SET
            cash = cash - %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """

    cur.execute(
        update_account,
        (
            account["trade_size"],
            account["id"],
        ),
    )


def save_action(
    account,
    item,
    ids,
    action,
    existing,
    entry_price,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            signal_id = (
                insert_or_update_signal(
                    cur,
                    account,
                    item,
                    ids,
                    action,
                    existing,
                )
            )

            if (
                action["action"]
                == "BUY"
            ):
                open_position_in_transaction(
                    cur,
                    account,
                    signal_id,
                    item,
                    ids,
                    entry_price,
                )

        conn.commit()

    if (
        action["action"]
        == "BUY"
    ):
        account["cash"] -= (
            account["trade_size"]
        )

    return signal_id


def get_current_recommendations(
    account_start_date,
    universe_name,
):
    rows = get_events(
        universe_name
    )

    training, testing = split_by_time(
        rows
    )

    confidence_map = (
        build_sector_confidence_map(
            training,
            testing,
        )
    )

    prospective_rows = [
        row
        for row in rows
        if (
            row.get("entry_date")
            is not None
            and row["entry_date"]
            > account_start_date
        )
    ]

    return add_scores(
        prospective_rows,
        confidence_map,
    )


def process_recommendation(
    account,
    item,
):
    row = item["row"]

    ticker = row["ticker"]
    signal_date = row["entry_date"]

    if not qualifies_experimental_signal(
        row
    ):
        return {
            "status":
                "BELOW_EXPERIMENTAL_SIGNAL",
            "ticker": ticker,
        }

    account_start_date = (
        account["created_at"].date()
    )

    if signal_date <= account_start_date:
        return {
            "status": "BEFORE_ACCOUNT",
            "ticker": ticker,
        }

    ids = get_event_ids(
        ticker,
        row["period_end"],
        signal_date,
    )

    if ids is None:
        return {
            "status": "MISSING_EVENT",
            "ticker": ticker,
        }

    existing = get_existing_signal(
        account["id"],
        ids["security_id"],
        signal_date,
    )

    if (
        existing is not None
        and existing["action"] != "WAIT"
    ):
        return {
            "status":
                "ALREADY_RECORDED",
            "ticker": ticker,
            "action":
                existing["action"],
        }

    entry_price = get_entry_price(
        ticker,
        signal_date,
    )

    action = determine_action(
        account,
        item,
        entry_price,
    )

    save_action(
        account,
        item,
        ids,
        action,
        existing,
        entry_price,
    )

    return {
        "status": action["action"],
        "ticker": ticker,
        "signal_date": signal_date,
        "priority": item["priority"],
        "score": item["score"],
        "recommendation":
            item["recommendation"],
        "reason":
            action["reason"],
        "entry_price":
            entry_price,
        "revenue_acceleration":
            row.get(
                "revenue_acceleration"
            ),
        "operating_margin_change":
            row.get(
                "operating_margin_change"
            ),
        "pre_excess_20d":
            row.get(
                "pre_excess_20d"
            ),
    }


def send_buy_notification(
    result,
):
    entry_price = (
        result["entry_price"]
    )

    if entry_price is None:
        price_text = (
            "Not available"
        )
    else:
        price_text = format_money(
            entry_price
        )

    subject = (
        f"PAPER BUY SIGNAL: "
        f"{result['ticker']}"
    )

    message = (
        f"Ticker: {result['ticker']}\n"
        f"Action: BUY\n"
        f"Signal date: "
        f"{result['signal_date']}\n"
        f"Entry price: {price_text}\n"
        f"Priority: "
        f"{result['priority']}\n"
        f"Score: "
        f"{result['score']}\n"
        f"Recommendation: "
        f"{result['recommendation']}\n\n"
        f"Experimental qualification:\n"
        f"Revenue acceleration: "
        f"{format_percent(
            result['revenue_acceleration']
        )}\n"
        f"Operating margin change: "
        f"{format_percent(
            result['operating_margin_change']
        )}\n"
        f"20-day excess return vs. SPY: "
        f"{format_percent(
            result['pre_excess_20d']
        )}\n\n"
        f"Required thresholds:\n"
        f"Revenue acceleration >= 20%\n"
        f"Operating margin change > 0%\n"
        f"20-day excess return vs. SPY "
        f"> 0%\n\n"
        f"Reason:\n"
        f"{result['reason']}\n\n"
        f"This is a paper-trading signal, "
        f"not a live trade recommendation."
    )

    send_notification(
        subject=subject,
        message=message,
    )


def print_account(account):
    positions = get_open_positions(
        account["id"]
    )

    invested = get_total_invested(
        positions
    )

    print()
    print("PAPER ACCOUNT")
    print("=" * 70)

    print(
        f"Name:            "
        f"{account['name']}"
    )

    print(
        f"Created:         "
        f"{account['created_at']}"
    )

    print(
        f"Available cash:  "
        f"{format_money(account['cash'])}"
    )

    print(
        f"Open invested:   "
        f"{format_money(invested)}"
    )

    print(
        f"Open positions:  "
        f"{len(positions)}"
    )

    print(
        f"Minimum priority:"
        f" {account['minimum_priority']} "
        f"(reporting only)"
    )

    print(
        f"Trade size:      "
        f"{format_money(account['trade_size'])}"
    )

    print(
        f"Ticker cap:      "
        f"{account['ticker_cap_percent']}%"
    )

    print(
        f"Holding period:  "
        f"{account['holding_days']} days"
    )

    print(
        "Paper strategy:  "
        "Accel >=20% + Op Margin + Momentum"
    )


def main(universe_name):
    account = get_account()

    print()
    print("PAPER TRADING ENGINE")
    print("=" * 70)

    print(
        f"Run date: {date.today()}"
    )

    print(
        "Mode: Prospective only"
    )

    print(
        f"Qualification: "
        f"{SIGNAL_DESCRIPTION}"
    )

    recommendations = (
        get_current_recommendations(
            account[
                "created_at"
            ].date(),
            universe_name,
        )
    )

    results = []

    for item in sorted(
        recommendations,
        key=lambda value: (
            value["row"]["entry_date"],
            value["priority"],
            value["score"],
            value["row"]["ticker"],
        ),
    ):
        result = process_recommendation(
            account,
            item,
        )

        results.append(
            result
        )

        if result["status"] == "BUY":
            send_buy_notification(
                result
            )

    actionable = [
        result
        for result in results
        if result["status"] in (
            "BUY",
            "WAIT",
            "SKIP_CASH",
            "SKIP_CAP",
        )
    ]

    print()
    print("NEW PAPER SIGNALS")
    print("=" * 100)

    if not actionable:
        print(
            "No new experimental signals "
            "since the paper account "
            "was created."
        )

    else:
        for result in actionable:
            print()

            print(
                f"{result['ticker']} "
                f"| {result['status']} "
                f"| Priority "
                f"{result['priority']} "
                f"| Score "
                f"{result['score']}"
            )

            print(
                f"  Signal date: "
                f"{result['signal_date']}"
            )

            print(
                f"  Recommendation: "
                f"{result['recommendation']}"
            )

            print(
                f"  Revenue acceleration: "
                f"{format_percent(
                    result['revenue_acceleration']
                )}"
            )

            print(
                f"  Operating margin change: "
                f"{format_percent(
                    result['operating_margin_change']
                )}"
            )

            print(
                f"  20d excess vs. SPY: "
                f"{format_percent(
                    result['pre_excess_20d']
                )}"
            )

            if (
                result["entry_price"]
                is not None
            ):
                print(
                    f"  Entry price: "
                    f"${result['entry_price']}"
                )

            print(
                f"  Reason: "
                f"{result['reason']}"
            )

    account = get_account()

    print_account(
        account
    )


if __name__ == "__main__":
    main()