"""Bounded read-only supplement to the cached acceptance-time audit.

Replays momentum for the 16 changed entries only; never builds or writes events.
Preserves the builder's price-symbol selection and reports ticker-history gaps.
"""
import gzip
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from psycopg import IsolationLevel
from psycopg.rows import dict_row
from src.database import get_connection
from src.analysis.market_context import get_trailing_return
from src.analysis.experimental_signal import qualifies_experimental_signal
from src.backtesting.time_split_statistics import TRAIN_END
from src.backtesting.sec_sic_pilot import lookup, parse_header

BASE = Path('logs/research')
SOURCE = BASE / 'acceptance_timezone_2026-09-23_123358.json.gz'
READINESS = BASE / 'sector_readiness_2026-09-22_220915.json'
PILOT = BASE / 'sec_sic_pilot/pilot_2026-09-23_052233.json'


def excess(prices):
    returns = [get_trailing_return(prices[symbol], 20) for symbol in ('stock', 'SPY')]
    return round(returns[0] - returns[1], 2) if all(v is not None for v in returns) else None


def run():
    audit = json.load(gzip.open(SOURCE, 'rt'))
    saved = json.loads(READINESS.read_text())
    pilot = json.loads(PILOT.read_text())
    events = {r['id']: r for r in saved['events']}
    changed = [r for r in audit['exact_events'] if r.get('entry_changes')]
    if len(events) != 194 or len(changed) > 20:
        raise ValueError('Sample bound or identity changed')
    headers = []
    for obs in pilot['observations']:
        path = BASE/'sec_sic_pilot/headers'/f"{obs['cik']}_{obs['accession']}.json"
        cached = json.loads(path.read_text())
        if hashlib.sha256(cached['raw_header'].encode()).hexdigest() != obs['sha256']:
            raise ValueError('Header hash mismatch')
        parsed = parse_header(cached['raw_header'], obs['cik'], obs['accession'])
        if any(parsed[k] != obs[k] for k in parsed):
            raise ValueError('Header replay mismatch')
        headers.append(dict(accession=obs['accession'], sha256=obs['sha256'], verified=True))
    with get_connection() as conn:
        conn.read_only = True
        conn.isolation_level = IsolationLevel.REPEATABLE_READ
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SELECT current_timestamp AS snapshot,current_setting('transaction_read_only') AS read_only")
            metadata = cur.fetchone()
            results = []
            for item in changed:
                original = events[item['id']]
                cur.execute('SELECT security_id,entry_date,revenue_acceleration,operating_margin_change,pre_excess_20d FROM backtest_events WHERE id=%s', (item['id'],))
                live = cur.fetchone()
                if not live or any(str(live[k]) != str(original[k]) for k in live):
                    raise ValueError('Event drift')
                days = [date.fromisoformat(item[k]) for k in ('entry_date', 'corrected_entry_replay')]
                windows = []
                for day in days:
                    prices = {}
                    for label, symbol in (('stock', item['ticker']), ('SPY', 'SPY')):
                        cur.execute('SELECT trade_date,adjusted_close AS close FROM daily_prices WHERE UPPER(symbol)=UPPER(%s) AND trade_date<%s AND adjusted_close IS NOT NULL ORDER BY trade_date DESC LIMIT 21', (symbol, day))
                        prices[label] = list(reversed(cur.fetchall()))
                    if any(len(p) != 21 or any(not r['close'].is_finite() or r['close'] <= 0 for r in p) for p in prices.values()):
                        raise ValueError('Incomplete or invalid momentum prices')
                    windows.append(dict(day=day, prices=prices, pre_excess_20d=excess(prices), dates_aligned=[r['trade_date'] for r in prices['stock']] == [r['trade_date'] for r in prices['SPY']]))
                if windows[0]['pre_excess_20d'] != live['pre_excess_20d']:
                    raise ValueError('Baseline momentum replay mismatch')
                cur.execute("SELECT count(*) AS n FROM index_membership_history WHERE security_id=%s AND index_name='S&P 500' AND effective_from<=%s AND (effective_to IS NULL OR effective_to>=%s)", (item['security_id'], days[1], days[1]))
                membership = cur.fetchone()['n']
                cur.execute('SELECT ticker,effective_from,effective_to FROM security_ticker_history WHERE security_id=%s AND effective_from<=%s AND (effective_to IS NULL OR effective_to>=%s)', (item['security_id'], days[1], days[1]))
                tickers = cur.fetchall()
                corrected = dict(live, pre_excess_20d=windows[1]['pre_excess_20d'])
                results.append(dict(event_id=item['id'], security_id=item['security_id'], ticker=item['ticker'], windows=windows,
                    corrected_qualifies=qualifies_experimental_signal(corrected), membership_matches=membership,
                    corrected_ticker_history=tickers, split_changed=(days[0] <= TRAIN_END) != (days[1] <= TRAIN_END),
                    reconstructed_revenue_acceleration=original['reconstructed_revenue_acceleration'],
                    reconstructed_operating_margin_change=original['reconstructed_operating_margin_change']))
    # Evaluate whether normalized metadata selects a different pilot source at its
    # ORIGINAL decision clock. A missing header for a newly preferred filing is
    # explicitly unresolved; do not fetch it or infer its SIC.
    pilot_selection = []
    for target in pilot['targets']:
        prior = target.get('requested_filing')
        if prior is None:
            continue
        decision = datetime.fromisoformat(target['decision_at'])
        candidates = [r for r in audit['filings'] if r['company_id'] == target['company_id'] and r['form'] in ('10-K','10-Q','20-F','40-F')
                      and r.get('corrected_acceptance') and datetime.fromisoformat(r['corrected_acceptance']) < decision]
        candidates.sort(key=lambda r: (datetime.fromisoformat(r['corrected_acceptance']), r['accession_number']), reverse=True)
        preferred = candidates[0]['accession_number'] if candidates else None
        pilot_selection.append(dict(event_id=target['id'], old_accession=prior['accession_number'],
            preferred_comparable_accession=preferred, selection_changed=preferred != prior['accession_number'],
            comparable_only=True))
    summary = dict(changed_entries=len(results), lost_qualification=sum(not r['corrected_qualifies'] for r in results),
        lost_event_ids=[r['event_id'] for r in results if not r['corrected_qualifies']],
        membership_lost=sum(r['membership_matches'] == 0 for r in results), split_changes=sum(r['split_changed'] for r in results),
        momentum_date_misalignments=sum(not w['dates_aligned'] for r in results for w in r['windows']),
        changed_entries_without_dated_ticker_history=sum(not r['corrected_ticker_history'] for r in results),
        headers_verified=len(headers), pilot_source_selection_changes=sum(r['selection_changed'] for r in pilot_selection))
    result = dict(metadata=metadata, input_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (SOURCE, READINESS, PILOT)},
        summary=summary, changed_events=results, header_checks=headers, pilot_source_selection=pilot_selection)
    path = BASE/f"acceptance_signal_impact_{metadata['snapshot'].strftime('%Y-%m-%d_%H%M%S')}.json"
    path.write_text(json.dumps(result, default=str, indent=2)+'\n')
    print(path)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        raise SystemExit(f'Signal impact audit failed ({type(error).__name__}); raw diagnostics suppressed.') from None
