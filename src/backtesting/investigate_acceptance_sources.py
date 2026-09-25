"""Bounded acceptance source investigation; offline analysis, never a repair.

Only --fetch permits SEC reads; no database interface or production writes.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone, date
import fcntl
import gzip
import hashlib
import html
import json
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from src.sec.acceptance_time import parse_submissions_acceptance, parse_header_acceptance

ROOT = Path('logs/research/sec_acceptance_source_discrepancy_2026-09-24')
STAGE3 = Path('logs/research/sec_sic_stage3_2026-09-24')
STAGE2 = Path('logs/research/sec_sic_validation_2026-09-24')
MANIFEST = Path('logs/research/acceptance_repair/manifest.json.gz')
PREFLIGHT = Path('logs/research/timestamp_rebuild_2026-09-23/before_20260924_023350.json.gz')
AUDIT = Path('logs/research/acceptance_timezone_2026-09-23_131057.json.gz')
EASTERN = ZoneInfo('America/New_York')
CAP = 20


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    raw=Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith('.gz') else raw)


def save(path, value):
    from src.sec.json_cache import atomic_json
    atomic_json(path, value)


def columns(data):
    return data.get('filings', {}).get('recent', data)


def row_for(data, accession):
    table=columns(data)
    matches=[i for i,a in enumerate(table['accessionNumber']) if a==accession]
    if not matches:
        return None
    rows=[{k:table[k][i] for k in ('accessionNumber','acceptanceDateTime','form','filingDate')} for i in matches]
    if any(row!=rows[0] for row in rows):
        raise ValueError('Conflicting duplicate submission records')
    return rows[0]


def header_fields(raw, cik, accession):
    decoded=html.unescape(raw)
    stamps=re.findall(r'ACCEPTANCE-DATETIME[^0-9]{0,20}(\d{14})',decoded)
    if len(set(stamps))!=1:
        raise ValueError('Missing or conflicting header acceptance')
    text=BeautifulSoup(decoded,'html.parser').get_text('\n')
    acc=re.search(r'ACCESSION NUMBER:\s*([0-9-]+)',text)
    if not acc or acc.group(1)!=accession:
        raise ValueError('Accession mismatch')
    parts=re.split(r'\b(FILER|REPORTING-OWNER|SUBJECT COMPANY|ISSUER):',text)
    if not any(role=='FILER' and re.search(r'CENTRAL INDEX KEY:\s*0*'+str(int(cik))+r'\b',block)
               for role,block in zip(parts[1::2],parts[2::2])):
        raise ValueError('Target issuer not a FILER')
    form=re.search(r'CONFORMED SUBMISSION TYPE:\s*([^\n]+)',text)
    filed=re.search(r'FILED AS OF DATE:\s*(\d{8})',text)
    if not form or not filed:
        raise ValueError('Missing header provenance')
    return dict(raw_acceptance=stamps[0],form=form.group(1).strip(),
                filing_date=datetime.strptime(filed.group(1),'%Y%m%d').date().isoformat())


def compare(raw_submissions, raw_header):
    """Compare representations, without rewriting either or inferring a repair."""
    sub=parse_submissions_acceptance(raw_submissions)
    head=parse_header_acceptance(raw_header)
    if sub is None:
        raise ValueError('Missing source acceptance')
    eastern=head.astimezone(EASTERN)
    delta=(head-sub).total_seconds()
    sub_wall=datetime.fromisoformat(raw_submissions.replace('Z','+00:00')).replace(tzinfo=None)
    return dict(submissions_raw=raw_submissions,header_raw=raw_header,
                submissions_parsed_utc=sub.isoformat(),header_parsed_utc=head.isoformat(),
                header_eastern=eastern.isoformat(),eastern_abbreviation=eastern.tzname(),
                eastern_offset_seconds=eastern.utcoffset().total_seconds(),is_dst=bool(eastern.dst()),
                header_minus_submissions_seconds=delta,header_minus_submissions_hours=delta/3600,
                same_wall_clock=sub_wall==eastern.replace(tzinfo=None),
                exactly_eastern_offset_difference=delta==-eastern.utcoffset().total_seconds(),
                classification='SAME_INSTANT' if delta==0 else
                    'Z_REPEATS_EASTERN_WALL_CLOCK' if raw_submissions.endswith('Z') and sub_wall==eastern.replace(tzinfo=None) and delta==-eastern.utcoffset().total_seconds() else 'OTHER_DISAGREEMENT')


def canonical_url(item):
    cik=item['cik']
    if not re.fullmatch(r'\d{10}',cik): raise ValueError('Invalid CIK')
    if item['kind']=='submissions': return f'https://data.sec.gov/submissions/CIK{cik}.json'
    accession=item['accession']
    if item['kind']!='header' or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession): raise ValueError('Invalid accession')
    return f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/{accession}-index-headers.html'


def target(item):
    return ROOT/item['kind']/(f"{item['cik']}_{item['accession']}.json" if item['kind']=='header' else f"CIK{item['cik']}.json")


def prepare():
    if (ROOT/'plan.json').exists(): raise ValueError('Plan already frozen')
    manifest=read(MANIFEST);plan=[]
    for label in ('CIEN','TTWO'):
        rows=sorted([r for r in manifest['rows'] if r['ticker_label']==label],key=lambda r:r['filing_date'])
        excluded=[r for r in rows if r['category']=='exceptional_offset']
        safe=[r for r in rows if r['category']=='safely_correctable']
        for row,reason in [(excluded[0],'First excluded exceptional filing'),(excluded[-1],'Latest excluded exceptional filing'),(safe[-1],'Last safely repaired filing preceding exceptional range')]:
            item=dict(kind='header',cik=row['cik'],accession=row['accession'],reason=reason,category=row['category'],label=label)
            item['url']=canonical_url(item);plan.append(item)
        item=dict(kind='submissions',cik=rows[0]['cik'],label=label,reason='Raw current response to distinguish source vintage from project transformations')
        item['url']=canonical_url(item);plan.append(item)
    save(ROOT/'plan.json',plan)
    print('Frozen eight-response source check; cap 20 attempts including failures')


def fetch():
    import requests
    from src.sec.sec_client import SEC_HEADERS
    from src.sec.sec_http import _pace, _retry_wait
    ROOT.mkdir(parents=True,exist_ok=True)
    with (ROOT/'.fetch.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ledger_path=ROOT/'requests.json';ledger=read(ledger_path) if ledger_path.exists() else []
        if any(r.get('status') in (401,403,429) for r in ledger): raise ValueError('Prior denial: stop')
        for item in read(ROOT/'plan.json'):
            if item['url']!=canonical_url(item): raise ValueError('Invalid URL')
            if target(item).exists(): continue
            if len(ledger)>=CAP: raise ValueError('20-attempt cap')
            if sum(r['url']==item['url'] for r in ledger)>=3: raise ValueError('Three-attempt URL bound')
            _pace()
            record=dict(item,attempt=len(ledger)+1,retrieved_at=datetime.now(timezone.utc).isoformat(),outcome='IN_FLIGHT')
            ledger.append(record);save(ledger_path,ledger)
            try:
                with requests.get(item['url'],headers=SEC_HEADERS,timeout=(10,25),stream=True,allow_redirects=False) as response:
                    record['status']=response.status_code
                    if response.status_code!=200:
                        record['outcome']='HTTP_FAILURE'
                        delay=_retry_wait(response,0)
                        if delay is not None: time.sleep(delay)
                        raise RuntimeError('SEC HTTP failure: stop batch')
                    raw=b'';limit=262144 if item['kind']=='header' else 2500000
                    for chunk in response.iter_content(8192):
                        raw+=chunk
                        if len(raw)>limit: raise ValueError('Response size bound')
                    text=raw.decode('utf-8')
                    if item['kind']=='header': header_fields(text,item['cik'],item['accession'])
                    elif str(json.loads(text)['cik']).zfill(10)!=item['cik']: raise ValueError('Submissions CIK mismatch')
                    value=dict(item,retrieved_at=record['retrieved_at'],sha256=digest(raw),**{('raw_header' if item['kind']=='header' else 'raw_json'):text})
                    save(target(item),value);record.update(outcome='SUCCESS',bytes=len(raw),sha256=value['sha256'])
            except requests.RequestException as error:
                record.update(outcome='NETWORK_FAILURE',error_type=type(error).__name__)
                raise RuntimeError('Network failure; diagnostics suppressed') from None
            except (ValueError,UnicodeError):
                record['outcome']='VALIDATION_FAILURE';raise
            finally: save(ledger_path,ledger)
            print(record['attempt'],item['kind'],item['cik'],record['outcome'],flush=True)

def checked_fixture(path, field):
    value=read(path)
    if digest(value[field].encode())!=value['sha256']:
        raise ValueError('Source fixture hash mismatch')
    return value


def capture():
    """Freeze compact comparisons/event links; read saved artifacts only."""
    if (ROOT/'inputs.json').exists(): raise ValueError('Inputs already frozen')
    manifest_raw=MANIFEST.read_bytes()
    if digest(manifest_raw)!=MANIFEST.with_suffix('.gz.sha256').read_text().split()[0]:
        raise ValueError('Repair manifest pin mismatch')
    manifest=read(MANIFEST);snapshot=read(PREFLIGHT);audit=read(AUDIT)
    stage=read(STAGE3/'results.json');inventory=read(STAGE3/'inputs.json')
    by_key={(r['cik'],r['accession']):r for r in manifest['rows']}
    sources={str(p):digest(p.read_bytes()) for p in (MANIFEST,PREFLIGHT,AUDIT,STAGE3/'results.json',STAGE3/'inputs.json',STAGE3/'validation.json')}
    cache={};comparisons=[]
    for window in stage['windows']:
        cik=window['cik'];label=window['label']
        candidate_paths=[Path(p) for p in inventory['source_hashes'] if Path(p).name.startswith('CIK'+cik)]
        for observation in window['rules']['B']['observations_detail']:
            accession=observation['accession'];rawrow=next(r for r in inventory['catalogs'][cik] if r['accessionNumber']==accession)
            original_sources=[]
            for path in candidate_paths:
                if not path.exists(): continue
                if str(path) not in cache:
                    payload=read(path);raw_field='raw_json' in payload
                    if raw_field:
                        checked_fixture(path,'raw_json');payload=json.loads(payload['raw_json'])
                    cache[str(path)]=(payload,raw_field)
                    sources[str(path)]=digest(path.read_bytes())
                payload,raw_field=cache[str(path)];source_row=row_for(payload,accession)
                if source_row:
                    if source_row['acceptanceDateTime']!=rawrow['acceptanceDateTime']:
                        raise ValueError('Comparison source changed since Stage 3')
                    original_sources.append(dict(path=str(path),sha256=sources[str(path)],raw_response_preserved=raw_field,
                        original_stage3_hash=inventory['source_hashes'][str(path)],
                        whole_file_matches_stage3=sources[str(path)]==inventory['source_hashes'][str(path)],
                        payload_location='filings.recent' if 'filings' in payload else 'historical_shard',
                        raw_acceptance=source_row['acceptanceDateTime']))
            if not original_sources: raise ValueError('No original source record for comparison')
            hp=Path(observation['source_path']);header=checked_fixture(hp,'raw_header');fields=header_fields(header['raw_header'],cik,accession)
            if fields['form']!=rawrow['form'] or fields['filing_date']!=rawrow['filingDate']: raise ValueError('Header/catalogue identity mismatch')
            row=by_key.get((cik,accession))
            comparisons.append(dict(label=label,cik=cik,accession=accession,form=fields['form'],filing_date=fields['filing_date'],
                submissions_raw=rawrow['acceptanceDateTime'],header_raw=fields['raw_acceptance'],header_path=str(hp),
                header_sha256=header['sha256'],header_url=header['url'],submissions_sources=original_sources,
                repair_category=row['category'] if row else 'ABSENT',manifest_row=row))
    # Save original manifest evidence and raw new SEC response values side by side.
    exceptions=[]
    new_sub={}
    for cik in ('0000936395','0000946581'):
        path=ROOT/'submissions'/f'CIK{cik}.json';value=checked_fixture(path,'raw_json')
        new_sub[cik]=(json.loads(value['raw_json']),value)
    snap_filings={f['id']:f for f in snapshot['filings']}
    for row in manifest['rows']:
        if row['category']!='exceptional_offset': continue
        data,source=new_sub[row['cik']];new=row_for(data,row['accession'])
        hp=ROOT/'header'/f"{row['cik']}_{row['accession']}.json"
        header=checked_fixture(hp,'raw_header') if hp.exists() else None
        exceptions.append(dict(manifest_row=row,new_submissions=new,new_submissions_sha256=source['sha256'],
            new_submissions_url=source['url'],new_retrieved_at=source['retrieved_at'],
            header_path=str(hp) if header else None,header_raw=header_fields(header['raw_header'],row['cik'],row['accession'])['raw_acceptance'] if header else None,
            saved_postrepair_timestamp=snap_filings[row['filing_id']]['acceptance_datetime']))
    facts={f['id']:f for f in snapshot['financial_provenance']}
    events={(e['security_id'],e['period_end']):e for e in snapshot['events'] if e['membership_qualified']}
    exceptional_acc={x['manifest_row']['accession'] for x in exceptions};links=[]
    for link in audit['current_revenue_links']:
        if link['accession_number'] not in exceptional_acc: continue
        fact=facts.get(link['fact_id'])
        if not fact: continue
        event=events.get((fact['security_id'],fact['period_end']))
        if event:
            links.append(dict(accession=link['accession_number'],fact_id=fact['id'],security_id=fact['security_id'],
                              period_end=fact['period_end'],event_id=event['id'],saved_entry_date=event['entry_date'],
                              exact_signal=event['exact_signal'],membership_qualified=event['membership_qualified'],
                              evidence='Saved original audit current-revenue fact ID joined to corrected snapshot stable event key'))
    probes=[]
    for item in read(ROOT/'plan.json'):
        if item['kind']!='header': continue
        row=by_key[item['cik'],item['accession']]
        header=checked_fixture(target(item),'raw_header');fields=header_fields(header['raw_header'],item['cik'],item['accession'])
        current=row_for(new_sub[item['cik']][0],item['accession'])
        probes.append(dict(label=item['label'],cik=item['cik'],accession=item['accession'],form=fields['form'],filing_date=fields['filing_date'],
                           header_raw=fields['raw_acceptance'],header_sha256=header['sha256'],header_path=str(target(item)),header_url=header['url'],
                           manifest_row=row,new_submissions=current))
    former=[]
    for cik,sid in [('0000718877',10411),('0001418091',10462)]:
        former.append(dict(cik=cik,security_id=sid,manifest_filings=sum(r['cik']==cik for r in manifest['rows']),
                           saved_baseline_filings=sum(str(f['cik']).zfill(10)==cik for f in snapshot['filings']),
                           saved_baseline_events=sum(e['security_id']==sid for e in snapshot['events']),
                           saved_financial_rows=sum(f['security_id']==sid for f in snapshot['financial_provenance'])))
    # The old anomaly caches can be recovered without touching working-tree caches.
    # Pin the exact matching Git object; reject provenance claims if the hash differs.
    import subprocess
    vintage_proof=[]
    for cik in ('0000936395','0000946581'):
        path=f'data/cache/sec/submissions/CIK{cik}.json';revision='f8ff747'
        raw=subprocess.check_output(['git','show',f'{revision}:{path}'])
        expected=manifest['source_files'][path]['sha256']
        if digest(raw)!=expected: raise ValueError('Original cache Git vintage hash mismatch')
        old=json.loads(raw)
        own=[e for e in exceptions if e['manifest_row']['cik']==cik]
        if any(row_for(old,e['manifest_row']['accession'])['acceptanceDateTime']!=e['manifest_row']['source_evidence'][0]['raw'] for e in own):
            raise ValueError('Manifest raw value mismatch')
        vintage_proof.append(dict(cik=cik,path=path,git_revision=subprocess.check_output(['git','rev-parse',revision]).decode().strip(),
                                  sha256=expected,verified_rows=len(own),raw_transport_preserved=False))
    save(ROOT/'inputs.json',dict(comparisons=comparisons,exceptional_rows=exceptions,header_probes=probes,
        saved_event_links=links,former_absence=former,manifest_counts=manifest['counts'],manifest_sha256=digest(manifest_raw),
        unresolved_summary=dict(count=205,without_source_evidence=sum(r['category']=='unresolved_source' and not r['source_evidence'] for r in manifest['rows']),
                                by_label=dict(Counter(r['ticker_label'] for r in manifest['rows'] if r['category']=='unresolved_source'))),
        original_audit_header_checks=audit['cache']['header_checks'],original_audit_formats=audit['cache']['cache_formats'],
        corrected_baseline=dict(snapshot=snapshot['metadata'],events=snapshot['summary']['historical_events'],exact_signals=snapshot['summary']['exact_signal_events']),
        original_cache_vintage_proof=vintage_proof,source_hashes=sources))
    print('Captured 125 comparisons, 71 excluded rows and compact saved event links; no database or price access')


def candidate(stamp, filed):
    from src.analysis.event_timing import get_candidate_entry_date
    return get_candidate_entry_date(dict(acceptance_datetime=stamp,filed_date=date.fromisoformat(filed))).isoformat()


def analyze():
    inputs=read(ROOT/'inputs.json');cases=[]
    for row in inputs['comparisons']:
        fixture=checked_fixture(Path(row['header_path']),'raw_header')
        if header_fields(fixture['raw_header'],row['cik'],row['accession'])['raw_acceptance']!=row['header_raw']: raise ValueError('Frozen header mismatch')
        cases.append(dict(row,comparison=compare(row['submissions_raw'],row['header_raw'])))
    probes=[]
    for p in inputs['header_probes']:
        fixture=checked_fixture(Path(p['header_path']),'raw_header')
        if header_fields(fixture['raw_header'],p['cik'],p['accession'])['raw_acceptance']!=p['header_raw']: raise ValueError('Probe changed')
        old=p['manifest_row'];header=parse_header_acceptance(p['header_raw'])
        probes.append(dict(p,manifest_source_comparison=compare(old['source_evidence'][0]['raw'],p['header_raw']),
                           new_source_comparison=compare(p['new_submissions']['acceptanceDateTime'],p['header_raw']) if p['new_submissions'] else None,
                           stored_minus_header_seconds=(datetime.fromisoformat(old['stored_timestamp'])-header).total_seconds(),
                           repaired_minus_header_seconds=(datetime.fromisoformat(old['proposed_timestamp'])-header).total_seconds() if old['proposed_timestamp'] else None))
    exceptions=[]
    for e in inputs['exceptional_rows']:
        row=e['manifest_row'];old=datetime.fromisoformat(row['stored_timestamp'])
        head=parse_header_acceptance(e['header_raw']) if e['header_raw'] else None
        new=parse_submissions_acceptance(e['new_submissions']['acceptanceDateTime']) if e['new_submissions'] else None
        if head and new and head!=new: raise ValueError('New response disagrees with header probe')
        reference=head or new
        if reference is None: raise ValueError('Missing exceptional reference')
        old_source=parse_submissions_acceptance(row['source_evidence'][0]['raw'])
        exceptions.append(dict(e,reference_utc=reference.isoformat(),reference_basis='INDEPENDENT_HEADER' if head else 'NEW_SUBMISSIONS_ONLY',
            source_vintage_delta_seconds=(new-old_source).total_seconds() if new else None,
            old_source_wall_equals_reference_eastern=old_source.replace(tzinfo=None)==reference.astimezone(EASTERN).replace(tzinfo=None),
            source_delta_equals_eastern_offset=(reference-old_source).total_seconds()==-reference.astimezone(EASTERN).utcoffset().total_seconds(),
            stored_minus_reference_seconds=(old-reference).total_seconds(),
            old_candidate=candidate(old,row['filing_date']),reference_candidate=candidate(reference,row['filing_date']),
            original_exclusion_preserved=True))
    by_acc={e['manifest_row']['accession']:e for e in exceptions};links=[]
    for link in inputs['saved_event_links']:
        ex=by_acc[link['accession']]
        links.append(dict(link,old_candidate=ex['old_candidate'],reference_candidate=ex['reference_candidate'],reference_basis=ex['reference_basis'],
                          candidate_changed=ex['old_candidate']!=ex['reference_candidate'],
                          corrected_actual_session_not_replayed=True))
    former=[c for c in cases if c['label'] in ('ATVI','TWTR')];controls=[c for c in cases if c not in former]
    summary=dict(former_cases=len(former),former_patterns=dict(Counter(c['comparison']['classification'] for c in former)),
        former_delta_seconds=dict(Counter(str(c['comparison']['header_minus_submissions_seconds']) for c in former)),
        former_repair_intersection=dict(Counter(c['repair_category'] for c in former)),
        controls=len(controls),control_patterns=dict(Counter(c['comparison']['classification'] for c in controls)),
        controls_by_issuer=dict(Counter(c['label'] for c in controls)),controls_repair_intersection=dict(Counter(c['repair_category'] for c in controls)),
        exceptional_header_probes=sum(p['manifest_row']['category']=='exceptional_offset' for p in probes),
        safe_header_probes=sum(p['manifest_row']['category']=='safely_correctable' for p in probes),
        exceptional_reference_bases=dict(Counter(e['reference_basis'] for e in exceptions)),
        source_vintage_changes=sum(e['source_vintage_delta_seconds'] not in (None,0) for e in exceptions),
        exceptional_candidate_changes=sum(e['old_candidate']!=e['reference_candidate'] for e in exceptions),
        linked_historical_events=len(links),linked_exact_signals=sum(e['exact_signal'] for e in links),
        linked_changed_candidates=sum(e['candidate_changed'] for e in links),
        linked_exact_signal_changed_candidates=sum(e['exact_signal'] and e['candidate_changed'] for e in links))
    ledger=read(ROOT/'requests.json')
    result=dict(scope='Read-only source semantics investigation, not SIC Stage 4 or timestamp repair',
                former_cases=former,current_issuer_controls=controls,header_probes=probes,exceptional_population=exceptions,
                event_impact=links,summary=summary,former_absence=inputs['former_absence'],
                unresolved_summary=inputs['unresolved_summary'],corrected_baseline=inputs['corrected_baseline'],
                original_audit_header_checks=inputs['original_audit_header_checks'],original_cache_vintage_proof=inputs['original_cache_vintage_proof'],
                requests=dict(attempted=len(ledger),succeeded=sum(x['outcome']=='SUCCESS' for x in ledger),failed=sum(x['outcome']!='SUCCESS' for x in ledger),cap=CAP),
                inputs_sha256=digest((ROOT/'inputs.json').read_bytes()))
    save(ROOT/'results.json',result)
    print(json.dumps(dict(summary=summary,requests=result['requests']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--fetch',action='store_true')
    p.add_argument('--capture',action='store_true');p.add_argument('--analyze',action='store_true')
    args=p.parse_args()
    if args.prepare:prepare()
    if args.fetch:fetch()

    if args.capture:capture()
    if args.analyze:analyze()
