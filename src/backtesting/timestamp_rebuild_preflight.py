"""Read-only event preservation and drift check before the authorized rebuild.

Never imports SEC/prices, writes the database, or executes the event builder.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path

from psycopg.rows import dict_row
from src.database import get_connection
from src.backtesting.apply_acceptance_repair import configure, fingerprints, durable_json, PIN, instant
from src.backtesting.audit_sector_readiness import MEMBERSHIP
from src.backtesting.time_split_statistics import TRAIN_END, get_stats, get_distribution_stats
from src.analysis.experimental_signal import qualifies_experimental_signal

ROOT = Path('logs/research/timestamp_rebuild_2026-09-23')
REPAIR = Path('logs/research/acceptance_repair/execution_20260923_135745_721689/receipt.json')
MANIFEST = Path('logs/research/acceptance_repair/manifest.json.gz')
SAVED = Path('logs/research/sector_readiness_2026-09-22_220915.json')


def event_key(row):
    return (row['security_id'], str(row['period_end']))


def filing_drift(rows, manifest):
    current = {r['id']:r for r in rows}
    expected_ids = {r['filing_id'] for r in manifest['rows']}
    missing, changed = [], []
    categories = Counter()
    for old in manifest['rows']:
        now = current.get(old['filing_id'])
        if now is None:
            missing.append(old['filing_id'])
            continue
        expected = old['proposed_timestamp'] if old['category']=='safely_correctable' else old['stored_timestamp']
        checks = dict(acceptance_datetime=instant(str(now['acceptance_datetime'])) != instant(expected),
            company_id=now['company_id']!=old['company_id'], cik=str(now['cik']).zfill(10)!=old['cik'],
            accession=now['accession_number']!=old['accession'], filing_date=str(now['filing_date'])!=old['filing_date'])
        if any(checks.values()):
            changed.append(dict(filing_id=old['filing_id'], category=old['category'], fields=checks, expected=old, current=now))
        else:
            categories[old['category']] += 1
    return dict(total=len(rows), new=[r for r in rows if r['id'] not in expected_ids],
                missing=missing, changed=changed, unchanged_manifest_categories=dict(categories))


def signal_stats(rows):
    signals = [r for r in rows if r['membership_qualified'] and r['exact_signal']]
    result = {}
    for split in ('train','test'):
        group = [r for r in signals if r['split']==split]
        values = [r['excess_30d'] for r in group if r['excess_30d'] is not None]
        result[split] = dict(events=len(group), completed=len(values), standard=get_stats(group,'30d'),
            distribution=get_distribution_stats(group,'30d'), sum_excess=sum(values,Decimal(0)),
            mean_excess_unrounded=sum(values,Decimal(0))/len(values) if values else None)
    return result


def run():
    raw = MANIFEST.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:
        raise ValueError('Manifest hash differs')
    manifest=json.loads(gzip.decompress(raw))
    repair=json.loads(REPAIR.read_text())['read_only_post_commit']
    saved=json.loads(SAVED.read_text())
    with get_connection() as conn:
        configure(conn, True)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT current_timestamp AS snapshot,current_setting('transaction_read_only') AS read_only")
            metadata=cur.fetchone()
            cur.execute(f'SELECT be.*,s.ticker AS display_ticker,{MEMBERSHIP} AS membership_qualified FROM backtest_events be JOIN securities s ON s.id=be.security_id ORDER BY be.security_id,be.period_end,be.id')
            events=cur.fetchall()
            if len(events)>30000: raise ValueError('Event snapshot bound exceeded')
            for event in events:
                event.update(stable_key=list(event_key(event)), split='train' if event['entry_date']<=TRAIN_END else 'test',
                             exact_signal=qualifies_experimental_signal(event))
            cur.execute('SELECT f.*,c.cik,c.ticker AS display_ticker FROM filings f LEFT JOIN companies c ON c.id=f.company_id ORDER BY f.id')
            filings=cur.fetchall()
            if len(filings)>50000: raise ValueError('Filing snapshot bound exceeded')
            drift=filing_drift(filings,manifest)
            protected=fingerprints(cur)
            cur.execute('SELECT id,cash,prospective_cutover_at FROM paper_accounts ORDER BY id')
            paper=cur.fetchall()
            cur.execute("SELECT ff.* FROM financial_facts ff WHERE metric IN ('revenue','operating_income','gross_profit','diluted_eps') AND EXISTS (SELECT 1 FROM index_membership_history i WHERE i.security_id=ff.security_id AND i.index_name='S&P 500') ORDER BY ff.security_id,ff.metric,ff.period_end,ff.id")
            facts=cur.fetchall()
            if len(facts)>250000: raise ValueError('Fact provenance bound exceeded')
            cur.execute("SELECT * FROM security_ticker_history WHERE security_id=ANY(%s) ORDER BY security_id,id",(list({r['security_id'] for r in events}),))
            ticker_history=cur.fetchall()
            cur.execute("SELECT relname,reltuples::bigint AS estimated_rows,pg_total_relation_size(oid) AS bytes FROM pg_class WHERE oid='public.daily_prices'::regclass")
            prices_size=cur.fetchone()
    livefacts={r['id']:r for r in facts}
    oldfacts={r['id']:r for event in saved['events'] for p in event['provenance'].values() for r in p['inputs'] if r}
    fact_drift=[]
    for fid,old in oldfacts.items():
        now=livefacts.get(fid)
        keys=('security_id','company_id','metric','period_end','value','filed_date','accession_number','is_derived')
        fields=[k for k in keys if now is None or str(now[k])!=str(old[k])]
        if fields: fact_drift.append(dict(id=fid,fields=fields,old=old,current=now))
    bykey={event_key(r):r for r in events}
    event_drift=[]
    for old in saved['events']:
        now=bykey.get(event_key(old))
        keys=('entry_date','revenue_acceleration','operating_margin_change','pre_excess_20d','excess_30d')
        fields=[k for k in keys if now is None or str(now[k])!=str(old[k])]
        if fields: event_drift.append(dict(stable_key=event_key(old),fields=fields))
    summary=dict(total_events=len(events),historical_events=sum(r['membership_qualified'] for r in events),
        exact_signal_events=sum(r['membership_qualified'] and r['exact_signal'] for r in events),
        duplicate_stable_keys=[dict(key=k,count=n) for k,n in Counter(event_key(r) for r in events).items() if n>1],
        filings=len(filings),added_filings=len(drift['new']),missing_filings=len(drift['missing']),changed_manifest_filings=len(drift['changed']),
        unchanged_manifest_categories=drift['unchanged_manifest_categories'],
        matches_repair_protected_tables={k:v==repair['protected_tables'][k] for k,v in protected.items()},
        protected_counts={k:dict(prior=repair['protected_tables'][k]['rows'],current=v['rows']) for k,v in protected.items()},
        paper_accounts=paper,paper_matches_repair=json.dumps(paper,default=str)==json.dumps(repair['paper_accounts']),
        saved_exact_event_changes=len(event_drift),saved_exact_fact_dependency_changes=len(fact_drift),
        exact_signal_statistics=signal_stats(events))
    result=dict(metadata=metadata,summary=summary,protected_tables=protected,events=events,filings=filings,
        filing_drift=drift,financial_provenance=facts,ticker_history=ticker_history,
        saved_exact_event_drift=event_drift,saved_exact_fact_drift=fact_drift,prices_size=prices_size,
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (REPAIR,MANIFEST,SAVED)})
    ROOT.mkdir(exist_ok=True)
    path=ROOT/f"before_{metadata['snapshot'].strftime('%Y%m%d_%H%M%S')}.json.gz"
    data=gzip.compress(json.dumps(result,default=str,separators=(',',':')).encode(),mtime=0)
    with path.open('xb') as output: output.write(data)
    durable_json(path.with_suffix('.summary.json'),dict(snapshot=str(path),sha256=hashlib.sha256(data).hexdigest(),**summary))
    print(path)
    print(json.dumps(summary,default=str,indent=2))


if __name__=='__main__':
    try: run()
    except Exception as error:
        raise SystemExit(f'Rebuild preflight failed ({type(error).__name__}); no database writes performed.') from None
