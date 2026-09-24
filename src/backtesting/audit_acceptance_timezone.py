"""Read-only, cache-only timestamp audit; never imports or rebuilds data."""
import json
import gzip
import re
from collections import Counter, defaultdict
from datetime import datetime, date, time, timezone, timedelta
from pathlib import Path

from psycopg import IsolationLevel
from psycopg.rows import dict_row
from src.database import get_connection
from src.analysis.event_timing import EASTERN, get_candidate_entry_date
from src.backtesting.audit_sector_readiness import MEMBERSHIP, availability

UTC = timezone.utc
BASE = Path('logs/research')
SAVED = BASE / 'sector_readiness_2026-09-22_220915.json'


def legacy_parse_acceptance_datetime(value):
    """Frozen pre-correction behavior for historical audit reproducibility only."""
    if not value:
        return None
    return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=EASTERN)


def normalize_explicit(value):
    """Audit reference only. Never guess timezone for naive SEC strings."""
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def timestamp_format(value):
    if not value:
        return 'missing'
    if value.endswith('Z'):
        return 'explicit_Z'
    if re.search(r'[+-]\d\d:\d\d$', value):
        return 'explicit_offset'
    return 'naive'


def candidate(accepted, filed):
    return get_candidate_entry_date(dict(acceptance_datetime=accepted, filed_date=filed))


def evidence(filings):
    wanted = {(str(f['cik']).zfill(10), f['accession_number']) for f in filings}
    values = defaultdict(dict)
    formats = Counter()
    paths = sorted(Path('data/cache/sec/submissions').glob('*.json'))
    if len(paths) > 2000 or sum(p.stat().st_size for p in paths) > 700_000_000:
        raise ValueError('Cache scan bound exceeded')
    for path in paths:
        cik = path.name[3:13]
        payload = json.loads(path.read_text())
        rows = payload.get('filings', {}).get('recent', payload)
        for i, acc in enumerate(rows.get('accessionNumber', [])):
            raw = rows.get('acceptanceDateTime', [])[i] if i < len(rows.get('acceptanceDateTime', [])) else None
            formats[timestamp_format(raw)] += 1
            if (cik, acc) not in wanted:
                continue
            stamp = normalize_explicit(raw)
            if stamp is not None:
                values[cik, acc][(stamp, rows['filingDate'][i])] = dict(
                    raw=raw, source=str(path), accepted=stamp, filing_date=rows['filingDate'][i])
    # Independently saved original headers, already parsed and hash-tested by pilot.
    pilot = json.loads((BASE/'sec_sic_pilot/pilot_2026-09-23_052233.json').read_text())
    header_checks = []
    for obs in pilot['observations']:
        key = obs['cik'], obs['accession']
        stamp = datetime.fromisoformat(obs['accepted_at']).astimezone(UTC)
        existing = {k[0] for k in values[key]}
        header_checks.append(dict(cik=key[0], accession=key[1],
            cache_present=bool(existing), header_agrees=existing == {stamp}))
        if not existing:
            values[key][(stamp, obs['filing_date'])] = dict(raw=obs['accepted_at'],
                source=obs['url'], accepted=stamp, filing_date=obs['filing_date'])
    return values, dict(cache_files=len(paths), cache_formats=dict(formats), header_checks=header_checks)


def run():
    saved = json.loads(SAVED.read_text())
    with get_connection() as conn:
        conn.read_only = True
        conn.isolation_level = IsolationLevel.REPEATABLE_READ
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SELECT current_timestamp AS snapshot,current_setting('transaction_read_only') AS read_only,current_setting('TimeZone') AS session_timezone")
            meta = cur.fetchone()
            cur.execute("SELECT f.id,f.company_id,c.cik,c.ticker,f.accession_number,f.form,f.filing_date,f.report_date,f.acceptance_datetime FROM filings f JOIN companies c ON c.id=f.company_id ORDER BY f.id")
            filings = cur.fetchall()
            if len(filings)>300000:
                raise ValueError('Filing bound exceeded')
            cached, cachemeta = evidence(filings)
            detail=[]; corrected={}; stored={}; counters=Counter(); offsets=Counter()
            for f in filings:
                old=f['acceptance_datetime']; acc=f['accession_number']; stored[acc]=f
                choices=cached.get((str(f['cik']).zfill(10),acc),{})
                stamps={k[0] for k in choices}
                row=dict(f, evidence=list(choices.values()))
                if not stamps:
                    row['status']='NO_EXPLICIT_CACHED_EVIDENCE'
                elif len(stamps)!=1:
                    row['status']='CONFLICTING_CACHE'
                else:
                    new=next(iter(stamps)); corrected[acc]=new
                    row['corrected_acceptance']=new
                    if old is None:
                        row['status']='MISSING_DATABASE_TIMESTAMP'
                    else:
                        delta=(old-new).total_seconds(); offsets[str(delta/3600)]+=1
                        row.update(offset_hours=delta/3600, utc_date_changed=old.astimezone(UTC).date()!=new.date(),
                            candidate_date_changed=candidate(old,f['filing_date'])!=candidate(new,f['filing_date']),
                            legacy_parser_reproduces=any(legacy_parse_acceptance_datetime(v['raw'])==old for v in choices.values()),
                            filing_date_agrees=all(str(f['filing_date'])==k[1] for k in choices))
                        row['status']='MATCH' if delta==0 else 'DIFFERENT'
                counters[row['status']]+=1; detail.append(row)
            cur.execute(f"SELECT be.id,be.security_id,be.period_end,be.entry_date,s.ticker,be.revenue_acceleration,be.operating_margin_change,be.pre_excess_20d FROM backtest_events be JOIN securities s ON s.id=be.security_id WHERE {MEMBERSHIP}")
            events=cur.fetchall(); byid={r['id']:r for r in events}
            cur.execute(f"""SELECT be.id AS event_id,be.entry_date,ff.id AS fact_id,ff.accession_number,
                ff.company_id,f.company_id AS filing_company_id,ff.filed_date
                FROM backtest_events be JOIN financial_facts ff ON ff.security_id=be.security_id
                AND ff.period_end=be.period_end AND ff.metric='revenue'
                LEFT JOIN filings f ON f.accession_number=ff.accession_number WHERE {MEMBERSHIP}""")
            current_links=cur.fetchall(); linkresults=[]
            for r in current_links:
                acc=r['accession_number']; old=stored.get(acc,{}).get('acceptance_datetime'); new=corrected.get(acc)
                cutoff=datetime.combine(r['entry_date'],time(9,30),EASTERN)
                item=dict(r, comparable=old is not None and new is not None)
                if item['comparable']:
                    item.update(old_available=old<=cutoff,new_available=new<=cutoff,
                        old_candidate=candidate(old,r['filed_date']),new_candidate=candidate(new,r['filed_date']))
                linkresults.append(item)
            factids=sorted({f['id'] for e in saved['events'] for p in e['provenance'].values() for f in p['inputs'] if f})
            cur.execute("SELECT ff.id,ff.security_id,ff.company_id,ff.metric,ff.period_end,ff.value,ff.filed_date,ff.accession_number,ff.is_derived,f.company_id AS filing_company_id,f.acceptance_datetime FROM financial_facts ff LEFT JOIN filings f ON f.accession_number=ff.accession_number WHERE ff.id=ANY(%s)",(factids,))
            facts={f['id']:f for f in cur.fetchall()}
            exact=[]
            for event in saved['events']:
                live=byid.get(event['id'])
                if live is None or any(str(live[k])!=str(event[k]) for k in ('security_id','entry_date','period_end','revenue_acceleration','operating_margin_change','pre_excess_20d')):
                    raise ValueError('Saved exact sample has drifted')
                cutoff=datetime.combine(live['entry_date'],time(9,30),EASTERN)
                out=dict(id=event['id'],security_id=event['security_id'],ticker=event['ticker'],split=event['split'],entry_date=live['entry_date'],components={})
                for name, p in event['provenance'].items():
                    before=[]; after=[]; changes=[]; coverage=True
                    for oldfact in p['inputs']:
                        if oldfact is None:
                            before.append(None);after.append(None);coverage=False;continue
                        f=facts[oldfact['id']]
                        if any(str(f[k])!=str(oldfact[k]) for k in ('security_id','company_id','metric','period_end','value','filed_date','accession_number','is_derived')):
                            raise ValueError('Saved fact dependency has drifted')
                        before.append(f); g=dict(f); new=corrected.get(f['accession_number'])
                        if new is None: coverage=False
                        else: g['acceptance_datetime']=new
                        after.append(g)
                        changes.append(dict(fact_id=f['id'],accession=f['accession_number'],old=f['acceptance_datetime'],new=new,
                            timestamp_status_changed=new is not None and f['acceptance_datetime'] is not None and (f['acceptance_datetime']<=cutoff)!=(new<=cutoff)))
                    out['components'][name]=dict(before=availability(before,cutoff),after=availability(after,cutoff),all_inputs_compared=coverage,facts=changes)
                source=event['provenance']['revenue']['inputs'][0]
                old=stored.get(source['accession_number'],{}).get('acceptance_datetime') if source else None
                new=corrected.get(source['accession_number']) if source else None
                if old and new:
                    dates=[]
                    for stamp in (old,new):
                        cand=candidate(stamp,date.fromisoformat(source['filed_date']))
                        cur.execute("SELECT min(trade_date) AS day FROM daily_prices WHERE symbol=%s AND trade_date BETWEEN %s AND %s",(live['ticker'],cand,cand+timedelta(days=7)))
                        dates.append(cur.fetchone()['day'])
                    out.update(old_entry_replay=dates[0],corrected_entry_replay=dates[1],entry_changes=dates[0]!=dates[1])
                    if dates[1] is not None:
                        newcut=datetime.combine(dates[1],time(9,30),EASTERN)
                        for name,p in event['provenance'].items():
                            shifted=[]
                            for oldfact in p['inputs']:
                                if oldfact is None:
                                    shifted.append(None);continue
                                f=dict(facts[oldfact['id']])
                                f['acceptance_datetime']=corrected.get(f['accession_number'],f['acceptance_datetime'])
                                shifted.append(f)
                            out['components'][name]['at_corrected_entry']=availability(shifted,newcut)
                exact.append(out)
            cur.execute("SELECT id,name,cash,prospective_cutover_at FROM paper_accounts")
            accounts=cur.fetchall()
            cur.execute("SELECT count(*) AS signals FROM paper_signals")
            paper=dict(accounts=accounts,**cur.fetchone())
            cur.execute("SELECT count(*) AS positions FROM paper_positions")
            paper.update(cur.fetchone())
            for account in accounts:
                cut=account['prospective_cutover_at']
                account['cutover_crossings']=[dict(accession=r['accession_number'],old=r['acceptance_datetime'],new=r['corrected_acceptance']) for r in detail if cut and r.get('corrected_acceptance') and r['acceptance_datetime'] and (r['acceptance_datetime']>=cut)!=(r['corrected_acceptance']>=cut)]
    different=[r for r in detail if r['status']=='DIFFERENT']
    summary=dict(filings=len(filings),with_acceptance=sum(f['acceptance_datetime'] is not None for f in filings),
        statuses=dict(counters),offset_hours=dict(offsets),affected_companies=len({r['company_id'] for r in different}),
        affected_forms=dict(Counter(r['form'] for r in different)),
        affected_filing_range=[min(str(r['filing_date']) for r in different),max(str(r['filing_date']) for r in different)],
        utc_date_changes=sum(r.get('utc_date_changed',False) for r in detail),
        candidate_date_changes=sum(r.get('candidate_date_changed',False) for r in detail),
        legacy_parser_reproduces_differences=sum(r.get('legacy_parser_reproduces',False) for r in different),
        filing_date_mismatches=sum(r.get('filing_date_agrees') is False for r in detail),
        historical_events=len(events),current_revenue_links=len(linkresults),
        current_revenue_links_comparable=sum(r['comparable'] for r in linkresults),
        current_revenue_availability_changes=sum(r['comparable'] and r['old_available']!=r['new_available'] for r in linkresults),
        current_revenue_candidate_changes=sum(r['comparable'] and r['old_candidate']!=r['new_candidate'] for r in linkresults),
        exact_events=len(exact),exact_entry_changes=sum(r.get('entry_changes',False) for r in exact),
        exact_old_entry_replay_mismatches=sum(r.get('old_entry_replay')!=r['entry_date'] for r in exact),
        exact_any_input_status_changes=sum(any(f['timestamp_status_changed'] for c in r['components'].values() for f in c['facts']) for r in exact),
        exact_component_summary={name:dict(
            all_inputs_compared=sum(r['components'][name]['all_inputs_compared'] for r in exact),
            timestamp_any_changes=sum(any(f['timestamp_status_changed'] for f in r['components'][name]['facts']) for r in exact),
            late_status_changes=sum(r['components'][name]['before']['late']!=r['components'][name]['after']['late'] for r in exact),
            direct_available_changes=sum(r['components'][name]['before']['direct_sources_available']!=r['components'][name]['after']['direct_sources_available'] for r in exact),
            corrected_entry_late_changes=sum(r['components'][name].get('at_corrected_entry',{}).get('late')!=r['components'][name]['before']['late'] for r in exact),
            corrected_entry_direct_available_changes=sum(r['components'][name].get('at_corrected_entry',{}).get('direct_sources_available')!=r['components'][name]['before']['direct_sources_available'] for r in exact)) for name in ('revenue','operating_margin')})
    result=dict(metadata=meta,cache=cachemeta,summary=summary,filings=detail,current_revenue_links=linkresults,exact_events=exact,paper=paper)
    path=BASE/f"acceptance_timezone_{meta['snapshot'].strftime('%Y-%m-%d_%H%M%S')}.json.gz"
    with gzip.open(path,'xt',encoding='utf-8') as output:
        json.dump(result,output,default=str,separators=(',',':'))
    print(path);print(json.dumps(summary,indent=2));print(json.dumps(paper,default=str))


if __name__=='__main__':
    try:
        run()
    except Exception as error:
        raise SystemExit(f'Timestamp audit failed ({type(error).__name__}); raw diagnostics suppressed.') from None
