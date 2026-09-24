"""Isolated SEC SIC pilot. Read-only DB; optional capped historical header reads.

No GICS conversion, production writes or backtest recalculation. Run --fetch
only to retrieve up to 40 small filing headers; default reuses pilot cache.
"""
import argparse
import hashlib
import html
import json
import re
import time as clock
from collections import Counter
from datetime import datetime, time, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from psycopg import IsolationLevel
from psycopg.rows import dict_row
from src.database import get_connection
from src.analysis.event_timing import EASTERN
from src.sec.sec_client import SEC_HEADERS
from src.sec.sec_http import _pace, _retry_wait
from src.sec.json_cache import atomic_json
from src.sec.acceptance_time import parse_header_acceptance

ROOT = Path('logs/research/sec_sic_pilot')
SAMPLE = {
    'AAPL': 'ordinary continuously listed issuer',
    'MSFT': 'ordinary issuer; different business from AAPL',
    'JPM': 'bank/financial issuer',
    'FE': 'regulated utility',
    'GEN': 'known GEN/NLOK and earlier name/ticker changes',
    'META': 'FB/META name/ticker change',
    'GOOG': 'Alphabet class C; shared issuer with GOOGL',
    'GOOGL': 'Alphabet class A; shared issuer with GOOG',
    'GE': 'restructuring/spinoff parent',
    'GEHC': 'separate spinoff security',
    'EXC': 'spinoff parent',
    'CEG': 'separate spinoff security',
    'FLT': 'historical ticker/name and missing-sector case',
    'ATVI': 'acquired/former constituent',
    'TWTR': 'acquired/delisted former constituent',
}
MEMBER = """EXISTS (SELECT 1 FROM index_membership_history m WHERE
 m.security_id=be.security_id AND m.index_name='S&P 500'
 AND m.effective_from<=be.entry_date
 AND (m.effective_to IS NULL OR m.effective_to>=be.entry_date))"""


def parse_header(raw, cik, accession):
    text = BeautifulSoup(html.unescape(raw), 'html.parser').get_text('\n')
    accepted = re.search(r'ACCEPTANCE-DATETIME[>:\s]*(\d{14})', text)
    # Header documents sometimes expose the timestamp as a tag's text.
    if not accepted:
        accepted = re.search(r'ACCEPTANCE-DATETIME[^0-9]{0,20}(\d{14})', html.unescape(raw))
    if not accepted:
        raise ValueError('Missing historical acceptance timestamp')
    acc = re.search(r'ACCESSION NUMBER:\s*([0-9-]+)', text)
    if not acc or acc.group(1) != accession:
        raise ValueError('Accession mismatch or missing')
    matches = []
    for block in re.split(r'\b(?:FILER|REPORTING-OWNER|SUBJECT COMPANY|ISSUER):', text)[1:]:
        c = re.search(r'CENTRAL INDEX KEY:\s*(\d+)', block)
        sic = re.search(r'STANDARD INDUSTRIAL CLASSIFICATION:\s*([^\n\[]+)\s*\[(\d{4})\]', block)
        if c and int(c.group(1)) == int(cik) and sic:
            matches.append((sic.group(2), ' '.join(sic.group(1).split())))
    if len(set(matches)) != 1:
        raise ValueError('Missing or conflicting issuer SIC in header')
    stamp = parse_header_acceptance(accepted.group(1)).astimezone(EASTERN)
    return dict(cik=str(cik).zfill(10), accession=accession, sic=matches[0][0],
                description=matches[0][1], accepted_at=stamp.isoformat())


def lookup(observations, cik, decision):
    eligible = [o for o in observations if o['cik'] == cik
                and datetime.fromisoformat(o['accepted_at']) < decision]
    if not eligible:
        return dict(status='UNKNOWN', reason='No supported observation strictly before decision')
    newest = max(datetime.fromisoformat(o['accepted_at']) for o in eligible)
    latest = [o for o in eligible if datetime.fromisoformat(o['accepted_at']) == newest]
    if len({o['sic'] for o in latest}) != 1:
        return dict(status='AMBIGUOUS', reason='Conflicting latest observations')
    return dict(status='CLASSIFIED', sic=latest[0]['sic'], description=latest[0]['description'],
                available_before_decision=True, accepted_at=latest[0]['accepted_at'],
                accessions=sorted({o['accession'] for o in latest}),
                observation_age_days=(decision-newest).days)


def inventory():
    with get_connection() as conn:
        conn.read_only = True
        conn.isolation_level = IsolationLevel.REPEATABLE_READ
        with conn.cursor(row_factory=dict_row) as q:
            q.execute("SET LOCAL statement_timeout='15s'")
            q.execute("SELECT current_timestamp AS snapshot,current_setting('transaction_read_only') AS read_only")
            meta = q.fetchone()
            q.execute("""SELECT s.id AS security_id,s.ticker,s.company_id,c.cik
             FROM securities s JOIN companies c ON c.id=s.company_id
             WHERE s.ticker=ANY(%s) AND EXISTS (SELECT 1 FROM index_membership_history m
             WHERE m.security_id=s.id AND m.index_name='S&P 500') ORDER BY s.ticker""", (list(SAMPLE),))
            securities = q.fetchall()
            if len(securities) != len(SAMPLE):
                raise ValueError('Pilot security selection is missing or nonunique')
            targets = []
            for s in securities:
                sid = s['security_id']
                s['reason'] = SAMPLE[s['ticker']]
                q.execute("SELECT h.company_id,c.cik,h.effective_from,h.effective_to,h.source FROM security_issuer_history h JOIN companies c ON c.id=h.company_id WHERE h.security_id=%s", (sid,))
                s['issuer_history'] = q.fetchall()
                q.execute("SELECT ticker,effective_from,effective_to FROM security_ticker_history WHERE security_id=%s", (sid,))
                s['ticker_history'] = q.fetchall()
                q.execute(f"""SELECT be.id,be.security_id,be.entry_date,be.period_end,
                 (revenue_acceleration>=20 AND operating_margin_change>0 AND pre_excess_20d>0) AS exact_signal
                 FROM backtest_events be WHERE be.security_id=%s AND {MEMBER} ORDER BY be.entry_date,be.id""", (sid,))
                events = q.fetchall()
                s['event_count'] = len(events)
                s['exact_signal_count'] = sum(bool(e['exact_signal']) for e in events)
                picked = {0,len(events)//2,len(events)-1} if events else set()
                if s['ticker']=='GEN':
                    picked.update(i for i,e in enumerate(events) if str(e['entry_date'])=='2020-08-07')
                q.execute("SELECT count(*) AS count FROM filings WHERE company_id=%s", (s['company_id'],))
                s['existing_filing_count'] = q.fetchone()['count']
                for i, e in enumerate(events):
                    decision = datetime.combine(e['entry_date'], time(9,30), EASTERN)
                    q.execute("""SELECT DISTINCT ff.company_id,c.cik,f.acceptance_datetime
                     FROM financial_facts ff JOIN companies c ON c.id=ff.company_id
                     LEFT JOIN filings f ON f.accession_number=ff.accession_number AND f.company_id=ff.company_id
                     WHERE ff.security_id=%s AND ff.period_end=%s AND ff.metric='revenue'""",(sid,e['period_end']))
                    facts=q.fetchall()
                    dated=[h for h in s['issuer_history'] if h['effective_from'] is not None and h['effective_from']<=e['entry_date'] and (h['effective_to'] is None or h['effective_to']>=e['entry_date'])]
                    fact_ids={f['company_id'] for f in facts if f['acceptance_datetime'] and f['acceptance_datetime']<decision}
                    if len(dated)==1:
                        company_id,cik=dated[0]['company_id'],dated[0]['cik']; mapping='DATED_ISSUER'
                    elif not dated and len(fact_ids)==1:
                        f=next(f for f in facts if f['company_id'] in fact_ids)
                        company_id,cik=f['company_id'],f['cik']; mapping='EVENT_FACT_CORROBORATED_UNDATED_ISSUER'
                    else:
                        company_id,cik=None,None; mapping='UNKNOWN_OR_AMBIGUOUS_ISSUER'
                    active=[h['ticker'] for h in s['ticker_history'] if h['effective_from'] is not None and h['effective_from']<=e['entry_date'] and (h['effective_to'] is None or h['effective_to']>=e['entry_date'])]
                    target=dict(e,ticker=s['ticker'],sampled_for_retrieval=i in picked,decision_at=decision,cik=cik,company_id=company_id,
                                mapping=mapping,historical_tickers=active,fact_mapping_evidence=facts)
                    if company_id is not None and i in picked:
                        q.execute("""SELECT accession_number,filing_date,acceptance_datetime,form FROM filings
                         WHERE company_id=%s AND acceptance_datetime<%s AND form IN ('10-K','10-Q','20-F','40-F')
                         ORDER BY acceptance_datetime DESC,accession_number LIMIT 1""",(company_id,decision))
                        target['requested_filing']=q.fetchone()
                    targets.append(target)
            if sum(t['sampled_for_retrieval'] for t in targets)>40:
                raise ValueError('Pilot exceeds 40 event-date bound')
            return dict(metadata=meta,securities=securities,targets=targets)


def retrieve(cik, accession, fetch, budget):
    path=ROOT/'headers'/f'{cik}_{accession}.json'
    if path.exists():
        return json.loads(path.read_text()),False
    if not fetch or budget[0]<=0:
        return None,False
    budget[0]-=1
    url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/{accession}-index-headers.html'
    # Reuse existing identity, shared pacing/cooldown, atomic caching. The shared
    # JSON client cannot parse HTML; this bounded adapter reads header text only.
    _pace()
    with requests.get(url,headers=SEC_HEADERS,timeout=(10,20),stream=True) as response:
        if response.status_code==429 or response.status_code>=500:
            _retry_wait(response,0)
        if response.status_code!=200:
            return dict(status='HTTP_ERROR',http_status=response.status_code,url=url),True
        chunks=[]; size=0
        for chunk in response.iter_content(8192):
            size+=len(chunk)
            if size>262144: raise ValueError('Header size limit exceeded')
            chunks.append(chunk)
        raw=b''.join(chunks)
    result=dict(status='OK',url=url,observed_at=datetime.now(timezone.utc).isoformat(),
                sha256=hashlib.sha256(raw).hexdigest(),raw_header=raw.decode('utf-8',errors='replace'))
    atomic_json(path,result)
    return result,True


def run(fetch=False):
    data=inventory()
    observations={}; requests_used=0; failures=[]; budget=[40]
    attempts=set()
    started=clock.monotonic()
    for t in data['targets']:
        if not t['sampled_for_retrieval']:
            continue
        if clock.monotonic()-started>90:
            failures.append(dict(status='RETRIEVAL_TIME_BOUND',seconds=90))
            break
        filing=t.get('requested_filing')
        if not filing: continue
        key=(t['cik'],filing['accession_number'])
        if key in attempts: continue
        attempts.add(key)
        try:
            result,used=retrieve(*key,fetch,budget); requests_used+=int(used)
            if result is None: continue
            if result['status']!='OK':
                failures.append(dict(cik=key[0],accession=key[1],**result))
                # Fail closed on access denial/rate limiting, no alternate host.
                if result.get('http_status') in (401,403,429): break
                continue
            obs=parse_header(result['raw_header'],*key)
            obs.update(url=result['url'],observed_at=result['observed_at'],sha256=result['sha256'],
                       database_acceptance=filing['acceptance_datetime'],filing_date=filing['filing_date'])
            obs['acceptance_agrees_with_database']=(datetime.fromisoformat(obs['accepted_at'])==filing['acceptance_datetime'])
            observations[key]=obs
        except (ValueError,requests.RequestException) as error:
            failures.append(dict(cik=key[0],accession=key[1],status='ERROR',error_type=type(error).__name__))
    for t in data['targets']:
        t['lookup']=lookup(list(observations.values()),t['cik'],t['decision_at']) if t['cik'] else dict(status='UNKNOWN',reason='Issuer not resolved')
        # Metadata corroboration is useful evidence, but not a proven dated
        # security/issuer relationship. Keep this separate from SIC availability.
        t['strict_dated_mapping_supported']=(t['lookup']['status']=='CLASSIFIED' and t['mapping']=='DATED_ISSUER')
    data.update(observations=list(observations.values()),failures=failures,
                retrieval_requests=requests_used,budget=40,
                counts=dict(Counter(t['lookup']['status'] for t in data['targets'])))
    data['metadata'].update(classification_system='SEC SIC (not GICS)',
        decision_time='Entry date at 09:30 America/New_York; strictly prior acceptance only',
        selection='First/middle/last event per security plus GEN 2020-08-07; no performance selection',
        coverage_caveat='Latest supported sampled observation, not a complete intervening filing history',
        mapping_caveat='Event fact corroboration is not independently proven dated security/issuer identity')
    serial=json.loads(json.dumps(data,default=str))
    stamp=data['metadata']['snapshot'].strftime('%Y-%m-%d_%H%M%S')
    path=ROOT/f'pilot_{stamp}.json'
    atomic_json(path,serial)
    print(path)
    print(json.dumps(dict(counts=data['counts'],observations=len(observations),requests=requests_used,failures=failures),default=str))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--fetch',action='store_true')
    args=p.parse_args()
    try: run(args.fetch)
    except Exception as error:
        raise SystemExit(f'Pilot failed ({type(error).__name__}); raw diagnostics suppressed.') from None
