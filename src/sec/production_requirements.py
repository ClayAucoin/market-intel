"""Current revenue provenance requirements; never infer freshness from DB write times."""
from datetime import date, datetime, timedelta

from psycopg.rows import dict_row

from src.database import get_connection
from src.sec import production_report as reporting
from src.analysis.event_timing import EASTERN, MAX_ENTRY_DELAY_DAYS, get_candidate_entry_date
from src.backtesting.build_backtest_events import is_current_reporting_event
from src.paper_trading.paper_execution import observed_sessions
from src.paper_trading.paper_trading_engine import ACCOUNT_NAME


def stored_valid(row):
    accepted = row.get("acceptance_datetime")
    return (row.get("filing_company_id") == row["company_id"]
            and row.get("filing_date") is not None and accepted is not None
            and accepted.tzinfo is not None)


def potentially_current(row, now, cutover, sessions=None):
    """Exclude only provably ineligible sources. Unknown timing remains required.

    Missing acceptance allows either same-day premarket or next-day entry from
    the source filing date. Prior observed sessions eliminate both possibilities.
    No event row, insertion timestamp, or guessed weekday calendar is used.
    """
    if row["metric"] != "revenue" or cutover is None:
        return False
    filed, period = row.get("filed_date"), row.get("period_end")
    if filed is not None and period is not None and not is_current_reporting_event(row):
        return False
    today = now.astimezone(EASTERN).date()
    accepted = row.get("acceptance_datetime")
    filing_company = row.get("filing_company_id")
    if filing_company not in (None, row["company_id"]):
        return True
    if accepted is not None:
        if accepted.tzinfo is None or filing_company is None:
            return True
        if accepted < cutover or accepted > now:
            return False
        candidates = [get_candidate_entry_date(row)]
    elif filed is not None:
        # Incomplete old stored metadata is still historical when both source
        # dates rule out current entry. A differing recent filing date remains
        # required; do not silently prefer the older fact date.
        dates = {filed}
        if row.get("filing_date") is not None:
            dates.add(row["filing_date"])
        candidates = [candidate for day in dates for candidate in (day, day + timedelta(days=1))]
    else:
        return True
    return any(0 <= (today - candidate).days <= MAX_ENTRY_DELAY_DAYS
               and not (sessions and any(candidate <= session < today for session in sessions))
               for candidate in candidates)


def select_requirements(rows, now, cutover, sessions=None):
    required, stored, warnings = {}, {}, set()
    for row in rows:
        accession = row.get("accession_number")
        # Return reusable metadata for all fact-linked accessions. Eligibility
        # controls mandatory recovery, not whether metadata may be persisted.
        if accession and stored_valid(row):
            stored[accession] = {
                "accessionNumber": accession,
                "filingDate": row["filing_date"].isoformat(),
                "acceptanceDateTime": row["acceptance_datetime"].astimezone(EASTERN).isoformat(),
            }
        if not potentially_current(row, now, cutover, sessions):
            if accession and accession not in stored:
                warnings.add(accession)
            continue
        if not accession or row.get("filed_date") is None or row.get("period_end") is None:
            reporting.add("current_required_unresolved")
            raise ValueError("Current revenue source lacks accession, filing date or period")
        required.setdefault(accession, set()).add(row["filed_date"])
    warnings.difference_update(required)
    return required, stored, sorted(warnings)


def validate_revenue_sources(facts, concepts, unit, now=None):
    """Detect current malformed sources before the history parser can omit them.

    Absent concepts/units are availability, not a retrieval failure. Present
    reporting sources in the prospective timing window must have provenance.
    """
    from src.sec.xbrl_client import get_concept_values, QUARTERLY_FORMS, ANNUAL_FORMS

    today = (now or datetime.now(EASTERN)).astimezone(EASTERN).date()
    for concept in concepts:
        for value in get_concept_values(facts, concept, unit):
            if value.get("form") not in QUARTERLY_FORMS | ANNUAL_FORMS:
                continue
            filed = date.fromisoformat(value["filed"]) if value.get("filed") else None
            period = date.fromisoformat(value["end"]) if value.get("end") else None
            if filed is not None and not 0 <= (today - filed).days <= MAX_ENTRY_DELAY_DAYS + 1:
                continue
            if filed is not None and period is not None and not is_current_reporting_event(
                    {"filed_date": filed, "period_end": period}):
                continue
            if not value.get("accn") or filed is None or period is None or not value.get("start"):
                reporting.add("current_required_unresolved")
                raise ValueError("Potentially current revenue source has incomplete provenance or period")
            date.fromisoformat(value["start"])


def get_production_requirements(company_id, universe_name):
    now = datetime.now(EASTERN)
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT prospective_cutover_at FROM paper_accounts WHERE name = %s", (ACCOUNT_NAME,))
            account = cur.fetchone()
            if account is None:
                raise ValueError("Prospective paper account missing")
            reporting.cutover(account["prospective_cutover_at"])
            # Today's prices may not yet be refreshed. Only use prior sessions as
            # exclusion evidence, and retain requirements if the calendar is uncertain.
            sessions = observed_sessions(cur, now.date() - timedelta(days=MAX_ENTRY_DELAY_DAYS + 1),
                                         now.date() - timedelta(days=1))
            cur.execute("""
                SELECT DISTINCT ff.security_id, ff.accession_number, ff.company_id, ff.metric,
                       ff.period_end, ff.filed_date, f.company_id AS filing_company_id,
                       f.filing_date, f.acceptance_datetime
                FROM financial_facts ff
                JOIN analysis_universe_members a ON a.security_id = ff.security_id
                JOIN analysis_universes u ON u.id = a.universe_id
                LEFT JOIN filings f ON f.accession_number = ff.accession_number
                WHERE ff.company_id = %s AND u.name = %s
            """, (company_id, universe_name))
            rows = cur.fetchall()
            cutover = account["prospective_cutover_at"]
            current_periods = {(r["security_id"], r["period_end"]) for r in rows
                               if potentially_current(r, now, cutover, sessions)}
            for security_id, period_end in current_periods:
                # Match paper get_provenance exactly, including other issuers and
                # unmatched/null accessions. Do not arbitrarily pick a source.
                cur.execute("""
                    SELECT COUNT(*) AS sources FROM financial_facts
                    WHERE security_id = %s AND period_end = %s AND metric = 'revenue'
                """, (security_id, period_end))
                if cur.fetchone()["sources"] != 1:
                    reporting.add("current_required_unresolved")
                    raise ValueError("Current revenue provenance is missing or ambiguous")
            return select_requirements(rows, now, cutover, sessions)
