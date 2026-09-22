"""Bounded, read-only audit of stored exact-signal events; no recalculation writes.

Run with python -m src.backtesting.audit_sector_readiness. Generated JSON retains
event-level evidence; Markdown summarizes it. Only report files are written.
"""
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, time as day_time, timedelta
from decimal import Decimal
from pathlib import Path

from psycopg.rows import dict_row
from src.database import get_connection
from src.analysis.event_timing import EASTERN
from src.analysis.experimental_signal import qualifies_experimental_signal
from src.backtesting.time_split_statistics import TRAIN_END
from src.backtesting.build_backtest_events import (
    find_same_period_last_year, get_previous_quarter, get_growth_acceleration,
    get_margin_change,
)


MEMBERSHIP = """EXISTS (SELECT 1 FROM index_membership_history i
 WHERE i.security_id=be.security_id AND i.index_name='S&P 500'
 AND i.effective_from<=be.entry_date
 AND (i.effective_to IS NULL OR i.effective_to>=be.entry_date))"""


def stats(rows):
    values = [r['excess_30d'] for r in rows if r['excess_30d'] is not None]
    total = sum(values, Decimal(0))
    return dict(events=len(rows), securities=len({r['security_id'] for r in rows}),
                completed=len(values), sum_excess_pp=total,
                mean_excess_pp=total / len(values) if values else None)


def valid(value):
    return value is not None and value.is_finite() and value > 0


def availability(facts, decision):
    """Separate known late timestamps, missing evidence and derived lineage."""
    missing = not facts or any(f is None for f in facts)
    late = False
    derived = False
    for f in facts:
        if f is None:
            continue
        derived |= bool(f['is_derived'])
        accepted = f['acceptance_datetime']
        missing |= (not f['accession_number'] or accepted is None
                    or accepted.tzinfo is None or f['company_id'] != f['filing_company_id']
                    or f['filed_date'] is None)
        if accepted is not None and accepted.tzinfo is not None:
            late |= accepted > decision
        if f['filed_date'] is not None:
            late |= f['filed_date'] > decision.date()
    return dict(late=late, missing_evidence=missing, derived_lineage_unproven=derived,
                direct_sources_available=not (late or missing or derived))


def dependencies(revenue, income, period):
    current = next((f for f in revenue if f['period_end'] == period), None)
    op = next((f for f in income if f['period_end'] == period), None)
    prior = get_previous_quarter(revenue, current) if current else None
    year = lambda history, f: find_same_period_last_year(history, f) if f else None
    return ([current, year(revenue, current), prior, year(revenue, prior)],
            [current, year(revenue, current), op, year(income, op)])


def summarize(rows):
    result = {}
    for name in ('train', 'test'):
        group = [r for r in rows if r['split'] == name]
        sectors = defaultdict(list)
        companies = defaultdict(list)
        for r in group:
            sectors[r['sector']].append(r)
            companies[r['security_id']].append(r)
        company_stats = []
        total = stats(group)
        positive_sum = sum((max(r['excess_30d'] or Decimal(0), Decimal(0)) for r in group), Decimal(0))
        for sid, events in companies.items():
            s = dict(security_id=sid, ticker=events[0]['ticker'], **stats(events))
            s['event_share_pct'] = Decimal(len(events)) * 100 / len(group)
            s['net_excess_share_pct'] = s['sum_excess_pp'] * 100 / total['sum_excess_pp'] if total['sum_excess_pp'] else None
            s['positive_excess_share_pct'] = sum((max(r['excess_30d'] or Decimal(0), Decimal(0)) for r in events), Decimal(0)) * 100 / positive_sum if positive_sum else None
            rest = [r for r in group if r['security_id'] != sid]
            s['excluding_security'] = stats(rest)
            company_stats.append(s)
        company_stats.sort(key=lambda x: (-x['events'], x['security_id']))
        winners = sorted(company_stats, key=lambda x: -x['sum_excess_pp'])
        sensitivity = {}
        for n in (1, 3, 5):
            ids = {s['security_id'] for s in winners[:n]}
            removed = [r for r in group if r['security_id'] in ids]
            sensitivity[str(n)] = dict(removed=stats(removed), remaining=stats([r for r in group if r['security_id'] not in ids]), securities=sorted(ids))
        counters = Counter()
        for r in group:
            for key, value in r['checks'].items():
                if value is True:
                    counters[key] += 1
        result[name] = dict(total=total, labeled=stats([r for r in group if r['sector'] != 'UNKNOWN']),
                            unlabeled=stats(sectors.get('UNKNOWN', [])),
                            sectors={k: stats(v) for k,v in sorted(sectors.items())},
                            companies=company_stats, top_contributors=winners[:5],
                            remove_top_contributors=sensitivity, flags=dict(counters),
                            crossing_boundary=stats([r for r in group if r['checks']['boundary_crossing']]),
                            contained_completed=stats([r for r in group if r['excess_30d'] is not None and not r['checks']['boundary_crossing']]),
                            max_exit_mismatch_days=max((r['exit_mismatch_days'] or 0 for r in group), default=0),
                            exit_mismatch_histogram=dict(Counter(r['exit_mismatch_days'] for r in group if r['excess_30d'] is not None)))
    return result


def collect():
    started = time.monotonic()
    with get_connection() as conn:
        conn.read_only = True
        conn.isolation_level = __import__('psycopg').IsolationLevel.REPEATABLE_READ
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SELECT current_timestamp AS snapshot, current_setting('transaction_read_only') AS read_only")
            meta = cur.fetchone()
            cur.execute(f"SELECT count(*) AS events, count(*) FILTER (WHERE entry_date<=%s AND exit_date_30d>%s) AS all_training_boundary_crossings FROM backtest_events be WHERE {MEMBERSHIP}", (TRAIN_END, TRAIN_END))
            meta.update(cur.fetchone())
            cur.execute(f"""SELECT be.*, s.ticker,
             COALESCE((SELECT MAX(NULLIF(TRIM(a.sector),'')) FROM analysis_universe_members a WHERE a.security_id=be.security_id),'UNKNOWN') AS sector,
             (SELECT count(*) FROM index_membership_history i WHERE i.security_id=be.security_id AND i.index_name='S&P 500' AND i.effective_from<=be.entry_date AND (i.effective_to IS NULL OR i.effective_to>=be.entry_date)) AS membership_matches
             FROM backtest_events be JOIN securities s ON s.id=be.security_id
             WHERE {MEMBERSHIP} AND revenue_acceleration>=20 AND operating_margin_change>0 AND pre_excess_20d>0
             ORDER BY be.entry_date,be.security_id""")
            rows = cur.fetchall()
            if len(rows) > 2000:
                raise RuntimeError('Audit bound exceeded: more than 2000 signal events')
            ids = sorted({r['security_id'] for r in rows})
            cur.execute("""SELECT ff.id,ff.security_id,ff.company_id,ff.metric,ff.period_end,ff.value,
             ff.filed_date,ff.accession_number,ff.is_derived,f.company_id AS filing_company_id,f.acceptance_datetime
             FROM financial_facts ff LEFT JOIN filings f ON f.accession_number=ff.accession_number
             WHERE ff.security_id=ANY(%s) AND ff.metric IN ('revenue','operating_income')
             ORDER BY ff.period_end,ff.id""", (ids,))
            facts = defaultdict(list)
            for fact in cur.fetchall():
                facts[fact['security_id'], fact['metric']].append(fact)
            cur.execute("SELECT security_id,ticker,effective_from,effective_to FROM security_ticker_history WHERE security_id=ANY(%s)", (ids,))
            histories = defaultdict(list)
            for h in cur.fetchall():
                histories[h['security_id']].append(h)
            cur.execute("SELECT ticker,count(*) AS n FROM securities GROUP BY ticker HAVING count(*)>1")
            duplicate_tickers = {r['ticker'] for r in cur.fetchall()}
            for r in rows:
                if time.monotonic() - started > 120:
                    raise RuntimeError('Audit exceeded 120-second bound')
                assert qualifies_experimental_signal(r)
                day = r['entry_date']
                decision = datetime.combine(day, day_time(9,30), EASTERN)
                revenue = facts[r['security_id'], 'revenue']
                income = facts[r['security_id'], 'operating_income']
                rev_inputs, op_inputs = dependencies(revenue, income, r['period_end'])
                checks = {}
                provenance = {}
                for name, inputs, history in (('revenue', rev_inputs, revenue), ('operating_margin', op_inputs, revenue+income)):
                    evidence = availability(inputs, decision)
                    ambiguous = any(f is not None and sum(x['metric']==f['metric'] and x['period_end']==f['period_end'] for x in history)>1 for f in inputs)
                    evidence['ambiguous_selection'] = ambiguous
                    evidence['direct_sources_available'] &= not ambiguous
                    evidence['inputs'] = inputs
                    provenance[name] = evidence
                    for key, val in evidence.items():
                        if isinstance(val, bool): checks[name+'_'+key] = val
                current = rev_inputs[0]
                computed_rev = get_growth_acceleration(revenue, current) if current else None
                computed_op = get_margin_change(income, revenue, r['period_end'])
                checks['revenue_stored_value_differs'] = computed_rev != r['revenue_acceleration']
                checks['margin_stored_value_differs'] = computed_op != r['operating_margin_change']
                prices = {}
                for symbol in (r['ticker'], 'SPY'):
                    cur.execute("SELECT trade_date,adjusted_open,adjusted_close FROM daily_prices WHERE symbol=%s AND trade_date=%s", (symbol,day))
                    entry = cur.fetchall()
                    cur.execute("SELECT trade_date,adjusted_open,adjusted_close FROM daily_prices WHERE symbol=%s AND trade_date>=%s ORDER BY trade_date LIMIT 1", (symbol,day+timedelta(days=30)))
                    exit_row = cur.fetchone()
                    cur.execute("SELECT trade_date,adjusted_close FROM daily_prices WHERE UPPER(symbol)=UPPER(%s) AND trade_date<%s AND adjusted_close IS NOT NULL ORDER BY trade_date DESC LIMIT 21", (symbol,day))
                    prior = list(reversed(cur.fetchall()))
                    prices[symbol] = dict(entry=entry, exit=exit_row, prior=prior)
                stock, spy = prices[r['ticker']], prices['SPY']
                completed = r['excess_30d'] is not None
                exits = [stock['exit'], spy['exit']]
                mismatch = abs((exits[0]['trade_date']-exits[1]['trade_date']).days) if all(exits) else None
                checks['completed_exit_date_mismatch'] = completed and mismatch is not None and mismatch>0
                checks['missing_exit'] = not all(exits)
                checks['completed_missing_exit'] = completed and not all(exits)
                checks['invalid_exit_price'] = any(p is not None and not valid(p['adjusted_close']) for p in exits)
                checks['missing_or_invalid_entry'] = any(len(p['entry'])!=1 or not valid(p['entry'][0]['adjusted_open']) for p in (stock,spy))
                checks['stored_exit_differs_from_current_price_lookup'] = stock['exit'] is not None and r['exit_date_30d'] != stock['exit']['trade_date']
                checks['boundary_crossing'] = day<=TRAIN_END and completed and any(p is not None and p['trade_date']>TRAIN_END for p in exits)
                checks['momentum_insufficient_or_invalid'] = any(len(p['prior'])<21 or any(not valid(x['adjusted_close']) for x in p['prior']) for p in (stock,spy))
                checks['momentum_dates_misaligned'] = [p['trade_date'] for p in stock['prior']] != [p['trade_date'] for p in spy['prior']]
                calculated = None
                if not checks['momentum_insufficient_or_invalid']:
                    returns = [round((p['prior'][-1]['adjusted_close']/p['prior'][0]['adjusted_close']-1)*100,2) for p in (stock,spy)]
                    calculated = round(returns[0]-returns[1],2)
                checks['momentum_stored_value_differs'] = calculated != r['pre_excess_20d']
                active = [h for h in histories[r['security_id']] if h['effective_from'] is not None and h['effective_from']<=day and (h['effective_to'] is None or h['effective_to']>=day)]
                checks['no_dated_ticker_history'] = not active
                checks['ambiguous_dated_ticker_history'] = len(active)>1
                checks['historical_ticker_differs'] = any(h['ticker']!=r['ticker'] for h in active)
                checks['ticker_shared_by_security_ids'] = r['ticker'] in duplicate_tickers
                checks['duplicate_membership_join'] = r['membership_matches']>1
                r.update(split='train' if day<=TRAIN_END else 'test', checks=checks,
                         exit_mismatch_days=mismatch, provenance=provenance,
                         price_evidence=prices, active_ticker_history=active,
                         reconstructed_revenue_acceleration=computed_rev,
                         reconstructed_operating_margin_change=computed_op)
    return dict(metadata=meta, summary=summarize(rows), events=rows)


def main():
    report = collect()
    stamp = report['metadata']['snapshot'].strftime('%Y-%m-%d_%H%M%S')
    path = Path('logs/research') / f'sector_readiness_{stamp}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        json.dump(report, out, default=str, indent=2)
    print(path)
    print(json.dumps(dict(metadata=report['metadata'], summary={
        k: {key: value for key,value in v.items() if key != 'companies'}
        for k,v in report['summary'].items()}),default=str,indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never expose raw database exception strings or credential-bearing DSNs.
        raise SystemExit(f'Audit failed ({type(error).__name__}); no raw diagnostic emitted.') from None
