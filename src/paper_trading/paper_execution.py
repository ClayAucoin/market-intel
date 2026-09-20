"""Paper-only timing and reservation rules; no historical calculations change."""

from datetime import datetime, timedelta
from decimal import Decimal

from src.analysis.event_timing import (
    EASTERN, MARKET_CLOSE, MAX_ENTRY_DELAY_DAYS, get_candidate_entry_date,
)
from src.backtesting.build_backtest_events import is_current_reporting_event


def eastern_now():
    return datetime.now(EASTERN)


def completed_through(now):
    local = now.astimezone(EASTERN)
    return local.date() if local.time() >= MARKET_CLOSE else local.date() - timedelta(days=1)


def positive_price(value):
    return value is not None and Decimal(value).is_finite() and value > 0


def observed_sessions(cur, start, end):
    """Return sessions only when the requested interval is unambiguous.

    Weekends are non-sessions. Every weekday in [start, end] must have valid
    SPY evidence: absent data cannot prove a market closure. Without a local
    exchange calendar this deliberately fails closed on weekday holidays too.
    A prior anchor and cross-symbol checks provide additional integrity checks.
    """
    if start > end:
        return None
    anchor_start = start - timedelta(days=MAX_ENTRY_DELAY_DAYS)
    cur.execute("""
        SELECT trade_date, adjusted_open, adjusted_close
        FROM daily_prices
        WHERE symbol = 'SPY' AND trade_date BETWEEN %s AND %s
        ORDER BY trade_date
    """, (anchor_start, end))
    prices = cur.fetchall()
    dates = [p["trade_date"] for p in prices]
    if (not any(d < start for d in dates) or len(set(dates)) != len(dates)
            or any(d.weekday() >= 5 for d in dates)
            or any(not positive_price(p["adjusted_open"])
                   or not positive_price(p["adjusted_close"]) for p in prices)):
        return None
    cur.execute("""
        SELECT DISTINCT p.trade_date
        FROM daily_prices p
        WHERE p.trade_date BETWEEN %s AND %s
          AND EXISTS (
              SELECT 1 FROM securities s
              JOIN analysis_universe_members a ON a.security_id = s.id
              JOIN analysis_universes u ON u.id = a.universe_id
              WHERE u.name = 'expanded_500' AND UPPER(s.ticker) = UPPER(p.symbol)
          )
    """, (anchor_start, end))
    if any(p["trade_date"] not in dates for p in cur.fetchall()):
        return None
    observed = set(dates)
    day = start
    while day <= end:
        if day.weekday() < 5 and day not in observed:
            return None
        day += timedelta(days=1)
    return [d for d in dates if d >= start]


def freshness_reason(row, provenance, cutover, now, sessions):
    local = now.astimezone(EASTERN)
    today = local.date()
    if cutover is None:
        return "Prospective cutover is unset; new commitments disabled."
    if local.weekday() >= 5 or local.time() < MARKET_CLOSE:
        return "Commitments require a weekday after-close production run."
    if row["entry_date"] != today:
        return "Historical event is not eligible today."
    if len(provenance) != 1:
        return "Revenue filing provenance is missing or ambiguous."
    source = provenance[0]
    accepted = source["acceptance_datetime"]
    if (not source["accession_number"] or accepted is None
            or accepted.tzinfo is None or source["filing_company_id"] != source["company_id"]
            or source["filed_date"] is None or source["filing_date"] is None):
        return "Revenue filing provenance is incomplete."
    if accepted < cutover or accepted > now:
        return "Filing is pre-cutover or has a future acceptance timestamp."
    if not is_current_reporting_event({
        "filed_date": source["filed_date"], "period_end": row["period_end"],
    }):
        return "Revenue fact is not a current reporting event."
    candidate = get_candidate_entry_date({
        "acceptance_datetime": accepted, "filed_date": source["filing_date"],
    })
    if not 0 <= (today - candidate).days <= MAX_ENTRY_DELAY_DAYS:
        return "Filing candidate is outside the existing entry timing window."
    if not sessions or sessions[0] != today:
        return "Today is not the first unambiguous observed SPY session."
    return None


def reservation_action(account, positions, pending, ticker):
    amount = account["trade_size"]
    reserved = sum((p["committed_amount"] for p in pending), Decimal(0))
    if account["cash"] - reserved < amount:
        return "SKIP_CASH", "Spendable cash after pending reservations is insufficient."
    invested = sum((p["invested_amount"] for p in positions), Decimal(0))
    exposure = sum((p["invested_amount"] for p in positions
                    if p["ticker"].upper() == ticker.upper()), Decimal(0))
    exposure += sum((p["committed_amount"] for p in pending
                     if p["ticker"].upper() == ticker.upper()), Decimal(0))
    maximum = (account["cash"] + invested) * account["ticker_cap_percent"] / Decimal(100)
    if exposure + amount > maximum:
        return "SKIP_CAP", "Open cost plus pending purchases exceeds the ticker cap."
    return "PENDING_BUY", "Funded commitment for the next observed session's open."
