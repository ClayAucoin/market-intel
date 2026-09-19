"""Prospective paper commitments and fills; historical events are read-only inputs."""

from datetime import timedelta
from decimal import Decimal

from psycopg.rows import dict_row

from src.database import get_connection
from src.analysis.experimental_signal import qualifies_experimental_signal
from src.analysis.latest_signal_report import add_scores
from src.analysis.sector_confidence import build_sector_confidence_map
from src.analysis.event_timing import EASTERN, MAX_ENTRY_DELAY_DAYS, get_candidate_entry_date
from src.backtesting.time_split_statistics import get_events, split_by_time
from src.paper_trading.paper_execution import (
    completed_through, eastern_now, freshness_reason, observed_sessions,
    positive_price, reservation_action,
)

ACCOUNT_NAME = "Primary Paper Account"


def lock_account(cur):
    # All paper writers take this lock before signal/position locks.
    cur.execute("SELECT * FROM paper_accounts WHERE name = %s FOR UPDATE", (ACCOUNT_NAME,))
    account = cur.fetchone()
    if account is None:
        raise ValueError(f"Paper account not found: {ACCOUNT_NAME}")
    return account


def get_candidates(cur, universe_name, today):
    # Keep exact security identity. Confidence still uses the unchanged research
    # reader, split, scoring and sector methodology.
    cur.execute("""
        SELECT be.*, s.ticker,
               COALESCE(a.sector, (SELECT MAX(sector)
                   FROM analysis_universe_members WHERE security_id = s.id), 'UNKNOWN') AS sector
        FROM backtest_events be
        JOIN securities s ON s.id = be.security_id
        JOIN analysis_universe_members a ON a.security_id = s.id
        JOIN analysis_universes u ON u.id = a.universe_id
        WHERE u.name = %s AND be.entry_date = %s
        ORDER BY be.entry_date, s.ticker
    """, (universe_name, today))
    return cur.fetchall()


def get_current_recommendations(universe_name, today):
    rows = get_events(universe_name)
    training, testing = split_by_time(rows)
    confidence = build_sector_confidence_map(training, testing)
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            candidates = get_candidates(cur, universe_name, today)
    return add_scores(candidates, confidence)


def get_provenance(cur, row):
    # Do not choose arbitrarily between multiple issuer/fact rows. Include
    # unmatched filings so incomplete provenance cannot disappear in a join.
    cur.execute("""
        SELECT ff.accession_number, ff.company_id, ff.filed_date,
               f.company_id AS filing_company_id, f.filing_date, f.acceptance_datetime
        FROM financial_facts ff
        LEFT JOIN filings f ON f.accession_number = ff.accession_number
        WHERE ff.security_id = %s AND ff.period_end = %s AND ff.metric = 'revenue'
    """, (row["security_id"], row["period_end"]))
    return cur.fetchall()


def get_reservations(cur, account_id):
    cur.execute("""
        SELECT ticker, invested_amount FROM paper_positions
        WHERE account_id = %s AND status = 'OPEN'
    """, (account_id,))
    positions = cur.fetchall()
    cur.execute("""
        SELECT ticker, committed_amount FROM paper_signals
        WHERE account_id = %s AND action = 'PENDING_BUY'
    """, (account_id,))
    return positions, cur.fetchall()


def commit_recommendation(cur, account, item, now):
    """Caller holds the account lock until this transaction commits."""
    row = item["row"]
    cur.execute("""
        SELECT id, action FROM paper_signals
        WHERE account_id = %s AND security_id = %s AND period_end = %s
        FOR UPDATE
    """, (account["id"], row["security_id"], row["period_end"]))
    if cur.fetchone() is not None:
        return "ALREADY_RECORDED"
    if not qualifies_experimental_signal(row):
        return "BELOW_EXPERIMENTAL_SIGNAL"
    if account["prospective_cutover_at"] is None:
        return "CUTOVER_UNSET"
    if row["entry_date"] != now.astimezone(EASTERN).date():
        return "STALE_EVENT"
    # A rebuild between recommendation and commitment must not change the
    # decision underneath its stored score/qualification snapshot.
    cur.execute("SELECT * FROM backtest_events WHERE id = %s FOR SHARE", (row["id"],))
    current = cur.fetchone()
    fields = ("security_id", "period_end", "entry_date", "revenue_yoy",
              "revenue_acceleration", "eps_yoy", "operating_margin_change", "pre_excess_20d")
    if current is None or any(current[key] != row[key] for key in fields):
        return "EVENT_CHANGED"
    provenance = get_provenance(cur, row)
    sessions = None
    if len(provenance) == 1 and provenance[0]["acceptance_datetime"] is not None:
        candidate = get_candidate_entry_date({
            "acceptance_datetime": provenance[0]["acceptance_datetime"],
            "filed_date": provenance[0]["filing_date"],
        })
        today = now.astimezone(EASTERN).date()
        # Bound the inspection before issuing price queries for stale sources.
        if 0 <= (today - candidate).days <= MAX_ENTRY_DELAY_DAYS:
            sessions = observed_sessions(cur, candidate, today)
    reason = freshness_reason(row, provenance, account["prospective_cutover_at"], now, sessions)
    if reason:
        print(f"{row['ticker']}: no commitment: {reason}")
        return "NOT_FRESH"
    positions, pending = get_reservations(cur, account["id"])
    action, reason = reservation_action(account, positions, pending, row["ticker"])
    # Source/price reads can wait on a concurrent rebuild. Never reuse a prior
    # production day's decision time after such a wait.
    decision_time = eastern_now()
    if decision_time.astimezone(EASTERN).date() != now.astimezone(EASTERN).date():
        return "MISSED_PRODUCTION_DAY"
    if freshness_reason(row, provenance, account["prospective_cutover_at"], decision_time, sessions):
        return "NOT_FRESH"
    is_pending = action == "PENDING_BUY"
    source = provenance[0]
    cur.execute("""
        INSERT INTO paper_signals (
            account_id, security_id, backtest_event_id, ticker, sector,
            signal_date, period_end, score, classification, sector_confidence,
            recommendation, priority, recommendation_reason, revenue_yoy,
            revenue_acceleration, eps_yoy, operating_margin_change, pre_excess_20d,
            action, action_reason, purchase_committed_at, not_before_date,
            committed_amount, source_accession, source_acceptance_at
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
    """, (
        account["id"], row["security_id"], row["id"], row["ticker"], row["sector"],
        row["entry_date"], row["period_end"], item["score"], item["classification"],
        item["sector_confidence"], item["recommendation"], item["priority"],
        item["recommendation_reason"], row["revenue_yoy"], row["revenue_acceleration"],
        row["eps_yoy"], row["operating_margin_change"], row["pre_excess_20d"],
        action, reason, decision_time if is_pending else None,
        decision_time.astimezone(EASTERN).date() + timedelta(days=1) if is_pending else None,
        account["trade_size"] if is_pending else None,
        source["accession_number"] if is_pending else None,
        source["acceptance_datetime"] if is_pending else None,
    ))
    return action


def process_recommendation(item):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            account = lock_account(cur)
            # Timestamp after acquiring the lock, never transaction/run start.
            result = commit_recommendation(cur, account, item, eastern_now())
    return result


def fill_pending_signal(cur, account, signal_id, now):
    """Never re-score a committed purchase or spend more than its reservation."""
    cur.execute("""
        SELECT * FROM paper_signals WHERE id = %s AND account_id = %s FOR UPDATE
    """, (signal_id, account["id"]))
    signal = cur.fetchone()
    if signal is None or signal["action"] != "PENDING_BUY":
        return None
    cur.execute("SELECT id FROM paper_positions WHERE signal_id = %s", (signal_id,))
    if cur.fetchone() is not None:
        raise ValueError("Pending signal already has a position; refusing a second debit.")
    committed = signal["purchase_committed_at"]
    start = signal["not_before_date"]
    amount = signal["committed_amount"]
    if (committed is None or start is None or not positive_price(amount)
            or start != committed.astimezone(EASTERN).date() + timedelta(days=1)):
        raise ValueError("Incomplete pending purchase commitment.")
    sessions = observed_sessions(cur, start, completed_through(now))
    if not sessions:
        return None
    session = sessions[0]
    if session < start or session > completed_through(now):
        return None
    frozen = signal["execution_session_date"]
    if frozen is not None and frozen != session:
        print(f"{signal['ticker']}: pending; stored session coverage changed.")
        return None
    if frozen is None:
        cur.execute("""
            UPDATE paper_signals SET execution_session_date = %s
            WHERE id = %s AND action = 'PENDING_BUY' AND execution_session_date IS NULL
        """, (session, signal_id))
    cur.execute("""
        SELECT adjusted_open FROM daily_prices
        WHERE UPPER(symbol) = UPPER(%s) AND trade_date = %s
    """, (signal["ticker"], session))
    prices = cur.fetchall()
    if len(prices) != 1 or not positive_price(prices[0]["adjusted_open"]):
        return None
    price = prices[0]["adjusted_open"]
    _, reservations = get_reservations(cur, account["id"])
    reserved = sum((r["committed_amount"] for r in reservations), Decimal(0))
    if account["cash"] < reserved:
        raise ValueError("Paper cash no longer covers existing reservations; refusing fill.")
    cur.execute("""
        INSERT INTO paper_positions (
            account_id, signal_id, security_id, ticker, status, entry_date,
            entry_price, shares, invested_amount, planned_exit_date
        ) VALUES (%s,%s,%s,%s,'OPEN',%s,%s,%s,%s,%s)
    """, (
        account["id"], signal_id, signal["security_id"], signal["ticker"], session,
        price, amount / price, amount, session + timedelta(days=account["holding_days"]),
    ))
    cur.execute("""
        UPDATE paper_accounts SET cash = cash - %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (amount, account["id"]))
    fill_reason = "Filled pre-existing commitment at the prospective session open."
    cur.execute("""
        UPDATE paper_signals SET action = 'BUY', action_reason = %s
        WHERE id = %s AND action = 'PENDING_BUY'
    """, (fill_reason, signal_id))
    if cur.rowcount != 1:
        raise ValueError("Pending purchase changed during fill.")
    return {
        **signal, "action": "BUY", "action_reason": fill_reason,
        "execution_session_date": session, "entry_date": session,
        "entry_price": price, "amount": amount, "shares": amount / price,
        "planned_exit_date": session + timedelta(days=account["holding_days"]),
    }


def fill_pending_purchases():
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT ps.id FROM paper_signals ps
                JOIN paper_accounts pa ON pa.id = ps.account_id
                WHERE pa.name = %s AND ps.action = 'PENDING_BUY'
                ORDER BY ps.purchase_committed_at, ps.id
            """, (ACCOUNT_NAME,))
            ids = [row["id"] for row in cur.fetchall()]
    for signal_id in ids:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                account = lock_account(cur)
                result = fill_pending_signal(cur, account, signal_id, eastern_now())
        if result is not None:
            send_buy_notification(result)


def send_buy_notification(result):
    # Called only after the fill transaction commits; never alert on commitment.
    if result["action"] != "BUY":
        return
    # Keep the existing per-channel failure isolation.
    from src.notifications.notifier import send_notification
    send_notification(
        subject=f"PAPER BUY FILLED: {result['ticker']}",
        message=(
            f"Ticker: {result['ticker']}\n"
            f"Historical signal date: {result['signal_date']}\n"
            f"Committed at: {result['purchase_committed_at']}\n"
            f"Actual paper entry date: {result['entry_date']}\n"
            f"Entry price: ${result['entry_price']:,.2f}\n"
            f"Invested: ${result['amount']:,.2f}\n"
            f"Priority: {result['priority']}\nScore: {result['score']}\n"
            f"Recommendation: {result['recommendation']}\n"
            f"Sector confidence: {result['sector_confidence']}\n"
            f"Recommendation reason: {result['recommendation_reason']}\n\n"
            "Experimental qualification (frozen at commitment):\n"
            f"Revenue acceleration: {result['revenue_acceleration']:+.2f}%\n"
            f"Operating margin change: {result['operating_margin_change']:+.2f}%\n"
            f"20-day excess return vs. SPY: {result['pre_excess_20d']:+.2f}%\n\n"
            "Required thresholds:\n"
            "Revenue acceleration >= 20%\n"
            "Operating margin change > 0%\n"
            "20-day excess return vs. SPY > 0%\n\n"
            f"Execution reason: {result['action_reason']}\n\n"
            "This is a paper-trading fill, not a live trade."
        ),
    )


def main(universe_name):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            account = lock_account(cur)
    if account["prospective_cutover_at"] is None:
        print("Prospective cutover is unset; new paper commitments disabled.")
        return
    today = eastern_now().date()
    recommendations = get_current_recommendations(universe_name, today)
    print("PROSPECTIVE PAPER COMMITMENTS")
    for item in sorted(recommendations, key=lambda value: (
        value["row"]["entry_date"], value["priority"], value["score"], value["row"]["ticker"],
    )):
        result = process_recommendation(item)
        print(f"{item['row']['ticker']}: {result}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m src.paper_trading.paper_trading_engine <universe_name>")
    # Standalone engine invocation follows the same fill-before-commit boundary.
    fill_pending_purchases()
    main(sys.argv[1])
