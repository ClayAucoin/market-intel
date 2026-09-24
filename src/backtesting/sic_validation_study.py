"""Bounded isolated SEC SIC research. No database connection or production writes."""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import re
import html
from bs4 import BeautifulSoup
import time

import requests
from src.backtesting.sec_sic_pilot import parse_header
from src.sec.sec_client import SEC_HEADERS
from src.sec.sec_http import _pace, _retry_wait

ROOT = Path('logs/research/sec_sic_validation_2026-09-24')
PILOT = Path('logs/research/sec_sic_pilot')
BASELINE = Path('logs/research/timestamp_rebuild_2026-09-23/provenance_inputs.json.gz')
MAX_REQUESTS = 80
CANDIDATES = ('XYZ', 'KKR', 'BX', 'TPL', 'ROP', 'DHR', 'FTV', 'MMM', 'HON', 'AXON', 'IBM', 'WBD')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, default=str, indent=2)+'\n')


def instant(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError('Timezone required')
    return dt.astimezone(timezone.utc)


def lookup(observations, cik, cutoff):
    """Inclusive latest evidence; age is disclosure, never continuity proof."""
    if cutoff.tzinfo is None:
        raise ValueError('Aware decision required')
    eligible = [o for o in observations if o['cik'] == cik and instant(o['accepted_at']) <= cutoff]
    if not eligible:
        return dict(status='UNKNOWN', reason='No verified prior issuer observation')
    newest = max(instant(o['accepted_at']) for o in eligible)
    latest = [o for o in eligible if instant(o['accepted_at']) == newest]
    if len({o['sic'] for o in latest}) != 1:
        return dict(status='AMBIGUOUS', reason='Conflicting latest issuer observations')
    return dict(status='CLASSIFIED', sic=latest[0]['sic'], accepted_at=newest.isoformat(),
                accessions=sorted({o['accession'] for o in latest}),
                age_days=(cutoff-newest).total_seconds()/86400,
                continuity_proven=False)


def transitions(observations):
    """Bound observed changes, without inventing an effective corporate-action date."""
    out=[]
    for cik in sorted({o['cik'] for o in observations}):
        ordered=sorted([o for o in observations if o['cik']==cik], key=lambda o:(instant(o['accepted_at']),o['accession']))
        previous=None
        for stamp in sorted({instant(o['accepted_at']) for o in ordered}):
            same=[o for o in ordered if instant(o['accepted_at'])==stamp]
            if len({o['sic'] for o in same}) != 1:
                previous=None
                continue
            current=same[-1]
            if previous and previous['sic']!=current['sic']:
                out.append(dict(cik=cik,old_sic=previous['sic'],new_sic=current['sic'],
                    last_old=previous,first_new=current,effective_date_known=False,
                    boundary='Observation interval only; new code usable no earlier than first_new acceptance'))
            previous=current
    return out


def density(observations):
    times=sorted({instant(o['accepted_at']) for o in observations})
    gaps=[(b-a).total_seconds()/86400 for a,b in zip(times,times[1:])]
    return dict(observations=len(observations),unique_instants=len(times),
                median_gap_days=statistics.median(gaps) if gaps else None,
                maximum_gap_days=max(gaps) if gaps else None)


def prepare():
    ROOT.mkdir(parents=True,exist_ok=True)
    if (ROOT/'local_inventory.json').exists():
        raise ValueError('Refuse to overwrite inventory')
    raw=BASELINE.read_bytes();base=json.loads(gzip.decompress(raw))
    pilot=json.loads((PILOT/'pilot_2026-09-23_052233.json').read_text())
    securities=[]; requests_plan=[]
    wanted=set(CANDIDATES)|{s['ticker'] for s in pilot['securities']}
    for security in base['securities']:
        if security['ticker'] not in wanted:
            continue
        sid=security['security_id'];facts=[f for f in base['facts'] if f['security_id']==sid]
        companies={f['company_id'] for f in facts}
        old=next((s for s in pilot['securities'] if s['security_id']==sid),None)
        if old:companies.add(old['company_id'])
        filings=[f for f in base['filings'] if f['company_id'] in companies]
        item=dict(security,company_ids=sorted(companies),ciks=sorted({str(f['cik']).zfill(10) for f in filings}|({old['cik']} if old else set())),
            events=[dict(security_id=sid,period_end=e['period_end'],entry_date=e['entry_date']) for e in base['events'] if e['security_id']==sid and e['membership_qualified']],
            membership=[m for m in base['membership'] if m['security_id']==sid],prior_pilot_identity=old,
            mapping_status='Local fact/company mapping; not an independently proved dated security-to-issuer interval',
            filings=filings)
        securities.append(item)
        if security['ticker'] in CANDIDATES:
            regular=sorted([f for f in filings if f['form']=='10-K' and '2018-01-01'<=f['filing_date']<='2026-09-23'],key=lambda f:f['filing_date'])
            if regular:
                for f in (regular[0],regular[-1]):requests_plan.append(header_request(str(f['cik']).zfill(10),f['accession_number'],'candidate endpoint '+security['ticker']))
    save(ROOT/'local_inventory.json',dict(baseline_sha256=digest(raw),baseline_metadata=base['metadata'],
        accepted_baseline_events=14742,accepted_exact_signals=191,securities=securities,
        existing_pilot_observations=pilot['observations'],request_cap=MAX_REQUESTS))
    for cik in ('0000718877','0001418091'):
        requests_plan.append(dict(kind='submissions',cik=cik,url=f'https://data.sec.gov/submissions/CIK{cik}.json',reason='Former issuer missing local cache'))
    save(ROOT/'plan_01.json',requests_plan)
    print('Prepared',len(securities),'securities and',len(requests_plan),'bounded requests')


def header_request(cik,accession,reason):
    return dict(kind='header',cik=cik,accession=accession,
        url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/{accession}-index-headers.html',reason=reason)


def fetch(plan_path):
    plan=json.loads(Path(plan_path).read_text())
    ledger_path=ROOT/'requests.json'
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    if any(r.get('status') in (401,403,429) for r in ledger):
        raise ValueError('Prior SEC access denial/rate limit: no further requests')
    started=time.monotonic()
    for item in plan:
        if item['kind'] not in ('header','submissions'):raise ValueError('Unsupported research source')
        if not re.fullmatch(r'[0-9]{10}',item['cik']):raise ValueError('Invalid CIK')
        if item['kind']=='header' and not re.fullmatch(r'[0-9]{10}-[0-9]{2}-[0-9]{6}',item['accession']):raise ValueError('Invalid accession')
        expected=header_request(item['cik'],item['accession'],'')['url'] if item['kind']=='header' else f'https://data.sec.gov/submissions/CIK{item["cik"]}.json'
        if item['url']!=expected:raise ValueError('Noncanonical SEC URL')
        name=f"{item['cik']}_{item['accession']}.json" if item['kind']=='header' else f"CIK{item['cik']}.json"
        target=ROOT/item['kind']/name
        prior=PILOT/'headers'/name
        if target.exists() or (item['kind']=='header' and prior.exists()):continue
        if sum(r['url']==item['url'] for r in ledger)>=3:
            raise ValueError('Per-URL three-attempt bound reached')
        if len(ledger)>=MAX_REQUESTS or time.monotonic()-started>180:
            raise ValueError('Bounded retrieval limit reached')
        _pace()
        record=dict(item,retrieved_at=datetime.now(timezone.utc).isoformat())
        try:
            with requests.get(item['url'],headers=SEC_HEADERS,timeout=(10,25),stream=True) as response:
                record['status']=response.status_code
                if response.status_code in (401,403,429) or response.status_code>=500:
                    _retry_wait(response,0)
                    ledger.append(record);save(ledger_path,ledger)
                    raise ValueError('SEC access/transient failure; stop bounded batch')
                if response.status_code!=200:
                    ledger.append(record);save(ledger_path,ledger);continue
                limit=262144 if item['kind']=='header' else 2500000
                chunks=[];size=0
                for chunk in response.iter_content(8192):
                    size+=len(chunk)
                    if size>limit:raise ValueError('Response size bound')
                    chunks.append(chunk)
                raw=b''.join(chunks)
                text=raw.decode('utf-8',errors='strict')
                if item['kind']=='header':
                    parsed=parse_header(text,item['cik'],item['accession'])
                    value=dict(record,sha256=digest(raw),raw_header=text,parsed=parsed)
                else:
                    data=json.loads(text)
                    if str(data['cik']).zfill(10)!=item['cik']:raise ValueError('CIK mismatch')
                    value=dict(record,sha256=digest(raw),raw_json=text)
                save(target,value);record.update(bytes=size,sha256=digest(raw),evidence=str(target))
        except requests.RequestException as error:
            record.update(error_type=type(error).__name__)
            ledger.append(record);save(ledger_path,ledger)
            raise ValueError('Network failure; stop, raw diagnostics suppressed') from None
        except (ValueError,UnicodeError) as error:
            if record not in ledger:
                record['error_type']=type(error).__name__
                ledger.append(record);save(ledger_path,ledger)
            raise
        ledger.append(record);save(ledger_path,ledger)
        print(item['kind'],item['cik'],record.get('status'),flush=True)


def verified_observations():
    observations={}
    for directory in (PILOT/'headers',ROOT/'header'):
        for path in sorted(directory.glob('*.json')):
            cached=json.loads(path.read_text());raw=cached['raw_header']
            if digest(raw.encode())!=cached['sha256']:raise ValueError('Header hash changed')
            cik,accession=path.stem.split('_',1)
            o=parse_header(raw,cik,accession)
            text=BeautifulSoup(html.unescape(raw),'html.parser').get_text('\n')
            def field(pattern):
                found=re.search(pattern,text)
                return found.group(1).strip() if found else None
            form=field(r'CONFORMED SUBMISSION TYPE:\s*([^\n]+)')
            filed=field(r'FILED AS OF DATE:\s*(\d{8})')
            block=next((b for b in re.split(r'\b(?:FILER|REPORTING-OWNER|SUBJECT COMPANY|ISSUER):',text)[1:]
                if re.search(r'CENTRAL INDEX KEY:\s*0*'+str(int(cik))+r'\b',b)),None)
            if block is None or form is None or filed is None:raise ValueError('Incomplete header provenance')
            name=re.search(r'COMPANY CONFORMED NAME:\s*([^\n]+)',block)
            o.update(form=form,filing_date=datetime.strptime(filed,'%Y%m%d').date().isoformat(),
                issuer_name=name.group(1).strip() if name else None,source_path=str(path),
                raw_sha256=cached['sha256'],source_url=cached['url'],
                retrieved_at=cached.get('retrieved_at',cached.get('observed_at')))
            key=(cik,accession)
            if key in observations and observations[key]['raw_sha256']!=o['raw_sha256']:
                raise ValueError('Conflicting duplicate source')
            observations[key]=o
    return list(observations.values())


def analyze():
    from zoneinfo import ZoneInfo
    eastern=ZoneInfo('America/New_York')
    inventory=json.loads((ROOT/'local_inventory.json').read_text())
    securities=inventory['securities']+json.loads((ROOT/'supplemental_inventory.json').read_text())
    observations=verified_observations()
    changes=transitions(observations)
    preflight_path=Path('logs/research/timestamp_rebuild_2026-09-23/before_20260924_023350.json.gz')
    preflight_raw=preflight_path.read_bytes()
    preflight=json.loads(gzip.decompress(preflight_raw))
    ticker_history=preflight['ticker_history']
    events=[];identities=[];issuer_stats=[]
    for s in securities:
        sid=s['security_id']; ciks=s['ciks']
        own=[o for o in observations if o['cik'] in ciks]
        local_history=[h for h in ticker_history if h['security_id']==sid]
        old=s.get('prior_pilot_identity') or {}
        identities.append(dict(security_id=sid,display_ticker=s['ticker'],company_ids=s['company_ids'],ciks=ciks,
            source_basis=s['mapping_status'],dated_issuer_history=old.get('issuer_history',[]),
            local_ticker_history=local_history,verified_header_names=sorted({o['issuer_name'] for o in own if o['issuer_name']}),
            public_issuer_observations=len(own),public_CIK_header_identity_verified=bool(own),
            independent_dated_security_binding_proven=False,
            event_count=len(s['events']),local_filing_count=len(s['filings'])))
        for e in s['events']:
            cutoff=datetime.combine(datetime.fromisoformat(e['entry_date']).date(),datetime.min.time(),eastern).replace(hour=9,minute=30)
            result=lookup(observations,ciks[0],cutoff) if len(ciks)==1 else dict(status='UNKNOWN',reason='Nonunique issuer binding')
            tickers=[h['ticker'] for h in local_history if h['effective_from'] and h['effective_from']<=e['entry_date'] and (not h['effective_to'] or h['effective_to']>=e['entry_date'])]
            events.append(dict(e,display_ticker=s['ticker'],decision_at=cutoff.isoformat(),historically_supported_tickers=tickers,
                issuer_lookup=result,security_binding='CORROBORATED_NOT_INDEPENDENTLY_DATED'))
    for cik in sorted({c for s in securities for c in s['ciks']}):
        own=[o for o in observations if o['cik']==cik]
        members=[s for s in securities if cik in s['ciks']]
        sidset={s['security_id'] for s in members}
        lookups=[e['issuer_lookup'] for e in events if e['security_id'] in sidset]
        ages=[r['age_days'] for r in lookups if r['status']=='CLASSIFIED']
        issuer_stats.append(dict(cik=cik,security_ids=sorted(sidset),display_tickers=[s['ticker'] for s in members],
            **density(own),event_count=len(lookups),lookup_counts=dict(Counter(r['status'] for r in lookups)),
            median_event_age_days=statistics.median(ages) if ages else None,
            maximum_event_age_days=max(ages) if ages else None,events_age_over_365_days=sum(a>365 for a in ages)))
    probes=[]
    for transition in changes:
        cutoff=instant(transition['first_new']['accepted_at'])
        local=cutoff.astimezone(eastern)
        saturday=(local+timedelta(days=(5-local.weekday())%7 or 7)).replace(hour=12,minute=0,second=0,microsecond=0)
        monday=(saturday+timedelta(days=2)).replace(hour=9,minute=30)
        for label,clock in [('one_microsecond_before',cutoff-timedelta(microseconds=1)),('exactly_at_acceptance',cutoff),
                ('one_microsecond_after',cutoff+timedelta(microseconds=1)),('following_weekend',saturday),('following_monday_open',monday)]:
            probes.append(dict(cik=transition['cik'],kind=label,decision_at=clock.isoformat(),
                observed_lookup=lookup(observations,transition['cik'],clock),clock_is_synthetic=True))
    for transition in changes:
        boundary=instant(transition['first_new']['accepted_at'])
        ids={s['security_id'] for s in securities if transition['cik'] in s['ciks']}
        relevant=sorted([e for e in events if e['security_id'] in ids],key=lambda e:instant(e['decision_at']))
        before=[e for e in relevant if instant(e['decision_at'])<boundary]
        after=[e for e in relevant if instant(e['decision_at'])>=boundary]
        for label,event in [('last_actual_event_before',before[-1] if before else None),('first_actual_event_at_or_after',after[0] if after else None)]:
            if event:
                probes.append(dict(cik=transition['cik'],kind=label,decision_at=event['decision_at'],
                    observed_lookup=event['issuer_lookup'],clock_is_synthetic=False,security_id=event['security_id'],period_end=event['period_end']))
    windows=[]
    for ticker,start,end in [('HON','2018-01-01','2022-01-01'),('JCI','2020-01-01','2024-01-01')]:
        s=next(s for s in securities if s['ticker']==ticker);cik=s['ciks'][0]
        regular=[f for f in s['filings'] if f['form'] in ('10-K','10-Q') and start<=f['filing_date']<end]
        own=[o for o in observations if o['cik']==cik and start<=o['filing_date']<end]
        expected={f['accession_number'] for f in regular};actual={o['accession'] for o in own}
        subset=[e for e in events if e['security_id']==s['security_id'] and start<=e['entry_date']<end]
        ages=[e['issuer_lookup']['age_days'] for e in subset if e['issuer_lookup']['status']=='CLASSIFIED']
        windows.append(dict(display_ticker=ticker,security_id=s['security_id'],cik=cik,start=start,end_exclusive=end,
            scope='10-K/10-Q in saved baseline filing inventory; not all SEC forms',
            expected_regular_filings=len(expected),verified_regular_filings=len(actual),missing_accessions=sorted(expected-actual),
            **density(own),events=len(subset),lookup_counts=dict(Counter(e['issuer_lookup']['status'] for e in subset)),
            median_event_age_days=statistics.median(ages) if ages else None,maximum_event_age_days=max(ages) if ages else None))
    former=[]
    for ticker,cik in [('ATVI','0000718877'),('TWTR','0001418091')]:
        cached=json.loads((ROOT/'submissions'/f'CIK{cik}.json').read_text())
        if digest(cached['raw_json'].encode())!=cached['sha256']:raise ValueError('Submissions hash changed')
        data=json.loads(cached['raw_json']);s=next(s for s in securities if s['ticker']==ticker)
        former.append(dict(display_ticker=ticker,security_id=s['security_id'],cik=cik,SEC_name=data['name'],
            current_SEC_tickers=data['tickers'],local_events=len(s['events']),local_filings=len(s['filings']),
            public_submission_retrieval='SUCCESS',verified_SIC_observations=[o for o in observations if o['cik']==cik],
            issuer_classification='SUCCESS',security_identity='Local mapping corroborated by SEC name/CIK; dated security binding not independently established',
            source_sha256=cached['sha256']))
    ledger=json.loads((ROOT/'requests.json').read_text())
    result=dict(baseline=dict(events=14742,exact_signals=191,snapshot=inventory['baseline_metadata'],
                    source_sha256=inventory['baseline_sha256'],ticker_snapshot_sha256=digest(preflight_raw)),
        method=dict(classification='SEC SIC',cutoff='Entry date 09:30 America/New_York',inclusive_acceptance=True,
            continuity_in_gaps='Not established',production_methodology_changed=False),
        securities_examined=len(securities),issuers_examined=len(issuer_stats),observations=observations,
        transitions=changes,transition_probes=probes,identities=identities,issuer_density=issuer_stats,dense_windows=windows,
        event_lookups=events,former_issuers=former,
        summary=dict(events=len(events),lookup_counts=dict(Counter(e['issuer_lookup']['status'] for e in events)),
            events_without_supported_historical_ticker=sum(not e['historically_supported_tickers'] for e in events),
            independently_dated_security_bindings=0,
            observations=len(observations),transitions=len(changes),
            requests_attempted=len(ledger),http_statuses=dict(Counter(str(r.get('status','network_error')) for r in ledger))))
    save(ROOT/'results.json',result)
    print(json.dumps(dict(summary=result['summary'],transitions=[dict(cik=t['cik'],old=t['old_sic'],new=t['new_sic'],last_old=t['last_old']['accepted_at'],first_new=t['first_new']['accepted_at']) for t in changes],dense_windows=windows),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--fetch-plan');p.add_argument('--analyze',action='store_true')
    a=p.parse_args()
    if a.prepare:prepare()
    if a.analyze:analyze()
    if a.fetch_plan:fetch(a.fetch_plan)
