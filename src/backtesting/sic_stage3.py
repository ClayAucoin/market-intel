"""Isolated ten-issuer SIC form/identity experiment; offline replay by default.

Fetch is explicit, sequential, resumable, locked and capped across all invocations.
No database, production cache writes, event rebuilding or investment decisions.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import gzip
import html
import json
from pathlib import Path
import re
import statistics
import time

import requests
from bs4 import BeautifulSoup
from src.backtesting import sic_validation_study as prior
from src.sec.json_cache import atomic_json
from src.sec.sec_client import SEC_HEADERS
from src.sec.sec_http import _pace, _retry_wait

ROOT = Path('logs/research/sec_sic_stage3_2026-09-24')
CAP = 120
# Chosen before fetching, based on identity complexity/evidence density, not outcomes.
CASES = [
    ('AAPL', '2021', '2023', 'Ordinary current issuer; sparse previous three-point sample'),
    ('HON', '2018', '2020', 'Known 3714 to 3724 transition; dense reusable periodic evidence'),
    ('JCI', '2021', '2023', 'Known 7380 to 3585 transition; dense reusable periodic evidence'),
    ('META', '2021', '2023', 'FB/META ticker and issuer-name change within window'),
    ('GOOGL', '2021', '2023', 'Alphabet class A and class C; two stable securities, one issuer'),
    ('GE', '2023', '2025', 'Reorganization/spin-off parent; do not transfer its SIC to children'),
    ('GEHC', '2023', '2025', 'Separate spin-off issuer; little evidence before first local event'),
    ('ATVI', '2021', '2023', 'Former issuer with zero local events/filings; SEC availability test'),
    ('TWTR', '2020', '2022', 'Second former issuer; empty current ticker array; independent replication'),
    ('FLT', '2020', '2022', 'Sparse prior SIC and absent dated identity; adverse provenance case'),
]


def read(path):
    return json.loads(Path(path).read_text())


def periodic(form):
    return form in {'10-K', '10-K/A', '10-KT', '10-KT/A', '10-Q', '10-Q/A', '10-QT', '10-QT/A'}


def parse_observation(raw, cik, accession):
    """Rule B requires matching issuer FILER, not ownership/subject metadata."""
    observation = prior.parse_header(raw, cik, accession)
    text = BeautifulSoup(html.unescape(raw), 'html.parser').get_text('\n')
    parts = re.split(r'\b(FILER|REPORTING-OWNER|SUBJECT COMPANY|ISSUER):', text)
    matches = []
    for role, block in zip(parts[1::2], parts[2::2]):
        found = re.search(r'CENTRAL INDEX KEY:\s*(\d+)', block)
        sic = re.search(r'STANDARD INDUSTRIAL CLASSIFICATION:[^\n]*\[(\d{4})\]', block)
        if role == 'FILER' and found and int(found.group(1)) == int(cik) and sic:
            name = re.search(r'COMPANY CONFORMED NAME:\s*([^\n]+)', block)
            matches.append((sic.group(1), name.group(1).strip() if name else None))
    if not matches or {x[0] for x in matches} != {observation['sic']}:
        raise ValueError('No unambiguous issuer FILER SIC')
    form = re.search(r'CONFORMED SUBMISSION TYPE:\s*([^\n]+)', text)
    filed = re.search(r'FILED AS OF DATE:\s*(\d{8})', text)
    if not form or not filed:
        raise ValueError('Missing form/date')
    observation.update(form=form.group(1).strip(), issuer_name=matches[0][1], role='FILER',
                       filing_date=datetime.strptime(filed.group(1), '%Y%m%d').date().isoformat())
    return observation


def body_identity(raw):
    """Extract dated-document assertions; never infer an effective interval."""
    soup = BeautifulSoup(raw, 'html.parser')
    facts = []
    wanted = {'EntityRegistrantName', 'EntityCentralIndexKey', 'TradingSymbol', 'Security12bTitle', 'SecurityExchangeName'}
    for node in soup.find_all(attrs={'name': True}):
        concept = node.get('name', '').split(':')[-1]
        if concept in wanted:
            facts.append(dict(concept=concept, value=node.get_text(' ', strip=True), context=node.get('contextref')))
    contexts = {}
    for node in soup.find_all(lambda t: t.name and t.name.lower().endswith('context')):
        contexts[node.get('id')] = node.get_text(' ', strip=True)
    text = ' '.join(soup.get_text(' ', strip=True).split())
    terms = ('trading symbol', 'ticker symbol', 'spin-off', 'spin off', 'separation', 'distribution', 'June 9, 2022')
    snippets = []
    for term in terms:
        for match in list(re.finditer(re.escape(term), text, re.I))[:3]:
            snippets.append(dict(term=term, text=text[max(0, match.start()-180):match.end()+420]))
    return dict(facts=facts, contexts={f['context']: contexts.get(f['context']) for f in facts}, snippets=snippets,
                interval_proven=False)


def fixture(item):
    return ROOT / item['kind'] / f"{item['cik']}_{item['accession']}.json"


def canonical_url(item):
    cik, acc = item['cik'], item['accession']
    if not re.fullmatch(r'\d{10}', cik) or not re.fullmatch(r'\d{10}-\d{2}-\d{6}', acc):
        raise ValueError('Invalid SEC identity')
    base = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-", "")}/'
    if item['kind'] == 'header':
        return base + acc + '-index-headers.html'
    if item['kind'] != 'body' or not re.fullmatch(r'[\w.-]+\.(?:htm|html)', item['document']):
        raise ValueError('Invalid primary document')
    return base + item['document']


def existing_header(cik, accession):
    name = f'{cik}_{accession}.json'
    return next((p for p in (prior.PILOT/'headers'/name, prior.ROOT/'header'/name, ROOT/'header'/name) if p.exists()), None)


def prepare():
    if (ROOT/'inputs.json').exists():
        raise ValueError('Inputs already frozen; replay or fetch saved plan')
    saved = read(prior.ROOT/'results.json')
    roster, catalogs, sources, plan = [], {}, {}, []
    for label, start, end, reason in CASES:
        identities = [i for i in saved['identities'] if i['display_ticker'] in ({'GOOG', 'GOOGL'} if label == 'GOOGL' else {label})]
        cik = identities[0]['ciks'][0]
        assert all(i['ciks'] == [cik] for i in identities)
        start += '-01-01'; end += '-01-01'
        files = sorted(Path('data/cache/sec/submissions').glob(f'CIK{cik}*.json'))
        if not files:
            files = [prior.ROOT/'submissions'/f'CIK{cik}.json']
        rows = {}
        for path in files:
            raw = path.read_bytes(); data = json.loads(raw)
            if 'raw_json' in data:
                assert prior.digest(data['raw_json'].encode()) == data['sha256']
                data = json.loads(data['raw_json'])
            sources[str(path)] = prior.digest(raw)
            table = data.get('filings', {}).get('recent', data)
            for n, acc in enumerate(table.get('accessionNumber', [])):
                if start <= table['filingDate'][n] < end:
                    row = {k: table[k][n] for k in ('accessionNumber','filingDate','acceptanceDateTime','form','primaryDocument','reportDate') if k in table}
                    if acc in rows and rows[acc] != row:
                        raise ValueError('Conflicting catalogue duplicate')
                    rows[acc] = row
        catalog = sorted(rows.values(), key=lambda r: (r['filingDate'], r['accessionNumber']))
        catalogs[cik] = catalog
        roster.append(dict(label=label, cik=cik, start=start, end_exclusive=end, reason=reason, identities=identities))
        regular = [r for r in catalog if periodic(r['form'])]
        broad = [r for r in catalog if r['form'] == '8-K']
        # General sample: first 8-K in each calendar year plus first proxy.
        selected = [next(r for r in broad if r['filingDate'][:4] == year) for year in sorted({r['filingDate'][:4] for r in broad})]
        proxies = [r for r in catalog if r['form'] == 'DEF 14A']
        selected += proxies[:1]
        if label in {'HON','JCI'}:
            left, right = ('2019-04-18','2019-07-18') if label == 'HON' else ('2021-11-15','2022-02-02')
            # All issuer-side candidate forms in the known interval; ownership forms remain excluded.
            selected += [r for r in catalog if left <= r['filingDate'] <= right and r['form'] in {'8-K','8-K/A','DEF 14A','DEFA14A','SD','11-K','13F-HR'}]
        for row in {r['accessionNumber']:r for r in regular+selected}.values():
            item = dict(kind='header', cik=cik, accession=row['accessionNumber'], expected_form=row['form'],
                        reason='Complete periodic window' if periodic(row['form']) else 'Broader-form comparison')
            item['url'] = canonical_url(item)
            if not existing_header(cik, item['accession']): plan.append(item)
        # First annual cover for every issuer; extra covers around ticker change and spin-off.
        bodies = [next(r for r in regular if r['form']=='10-K')]
        if label == 'META':
            bodies += [next(r for r in regular if r['filingDate'] > '2022-06-09')]
            candidates = [r for r in broad if '2022-05-01' <= r['filingDate'] < '2022-06-10']
            if candidates: bodies += [candidates[-1]]
        if label == 'GEHC': bodies += broad[:1]
        for row in bodies:
            item = dict(kind='body', cik=cik, accession=row['accessionNumber'], document=row['primaryDocument'],
                        expected_form=row['form'], reason='Dated cover/identity evidence')
            item['url'] = canonical_url(item); plan.append(item)
    ids = {i['security_id'] for r in roster for i in r['identities']}
    events = [{k:e[k] for k in ('security_id','period_end','entry_date','decision_at','historically_supported_tickers')} for e in saved['event_lookups'] if e['security_id'] in ids]
    frozen = dict(roster=roster, catalogs=catalogs, events=events, baseline=saved['baseline'],
                  source_hashes={**sources,str(prior.ROOT/'results.json'):prior.digest((prior.ROOT/'results.json').read_bytes())},
                  design='Ten issuers, two calendar years each; form selection before retrieval; no returns used', request_cap=CAP)
    atomic_json(ROOT/'inputs.json', frozen)
    atomic_json(ROOT/'plan.json', plan)
    print(json.dumps(dict(planned_new_requests=len(plan), kinds=dict(Counter(p['kind'] for p in plan)), roster=[r['label'] for r in roster])))
    if len(plan)>CAP: raise ValueError('Plan exceeds cap')


def fetch(batch=30):
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT/'.fetch.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger_path = ROOT/'requests.json'
        ledger = read(ledger_path) if ledger_path.exists() else []
        if any(r.get('status') in (401,403,429) for r in ledger):
            raise ValueError('SEC denial/rate limit: stop study')
        attempts = 0
        for item in read(ROOT/'plan.json'):
            if item['url'] != canonical_url(item): raise ValueError('Noncanonical URL')
            if fixture(item).exists() or (item['kind']=='header' and existing_header(item['cik'], item['accession'])): continue
            if attempts >= batch: break
            if len(ledger) >= CAP: raise ValueError('120-attempt cap reached')
            if sum(r['url']==item['url'] for r in ledger)>=3: raise ValueError('Three-attempt URL cap')
            _pace()
            # Persist BEFORE the call: interruption/crash also consumes an attempt.
            record = dict(item, attempt=len(ledger)+1, retrieved_at=datetime.now(timezone.utc).isoformat(), outcome='IN_FLIGHT')
            ledger.append(record); atomic_json(ledger_path, ledger); attempts += 1
            try:
                with requests.get(item['url'], headers=SEC_HEADERS, timeout=(10,30), stream=True, allow_redirects=False) as response:
                    record['status'] = response.status_code
                    if response.status_code != 200:
                        record['outcome']='HTTP_FAILURE'; atomic_json(ledger_path, ledger)
                        delay = _retry_wait(response, 0)
                        if delay is not None: time.sleep(delay)
                        raise RuntimeError('HTTP failure: stopped batch')
                    chunks=[]; size=0; limit=262144 if item['kind']=='header' else 16000000
                    for chunk in response.iter_content(8192):
                        size += len(chunk)
                        if size>limit: raise ValueError('Response size limit')
                        chunks.append(chunk)
                    raw=b''.join(chunks); text=raw.decode('utf-8')
                    value=dict(item, retrieved_at=record['retrieved_at'], sha256=prior.digest(raw))
                    if item['kind']=='header':
                        value['raw_header']=text
                        # Ineligible headers remain evidence and are reported, not silently discarded.
                        try: value['parsed']=parse_observation(text,item['cik'],item['accession'])
                        except ValueError as error: value['ineligible_reason']=str(error)
                    else:
                        target=fixture(item).with_suffix('.html.gz'); target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(gzip.compress(raw, mtime=0))
                        value.update(raw_gzip=str(target), identity=body_identity(text))
                    atomic_json(fixture(item), value)
                    record.update(outcome='SUCCESS', bytes=size, sha256=value['sha256'], evidence=str(fixture(item)))
            except requests.RequestException as error:
                record.update(outcome='NETWORK_FAILURE', error_type=type(error).__name__)
                raise RuntimeError('Network failure; details suppressed') from None
            except (ValueError, UnicodeError):
                record.update(outcome='PROCESSING_FAILURE')
                raise
            finally:
                atomic_json(ledger_path, ledger)
            print(record['attempt'], item['kind'], item['cik'], record['outcome'], flush=True)


def observations(inputs):
    ciks={r['cik'] for r in inputs['roster']}; found={}; rejected=[]
    for directory in (prior.PILOT/'headers', prior.ROOT/'header', ROOT/'header'):
        for path in sorted(directory.glob('*.json')):
            cik, accession=path.stem.split('_',1)
            if cik not in ciks: continue
            value=read(path); raw=value['raw_header']
            if prior.digest(raw.encode()) != value['sha256']: raise ValueError('Header hash mismatch')
            try: obs=parse_observation(raw,cik,accession)
            except ValueError as error:
                rejected.append(dict(path=str(path),cik=cik,accession=accession,reason=str(error))); continue
            obs.update(source_path=str(path),source_url=value['url'],sha256=value['sha256'],retrieved_at=value.get('retrieved_at',value.get('observed_at')))
            key=(cik,accession)
            if key in found and found[key]['sha256']!=obs['sha256']: raise ValueError('Duplicate mismatch')
            found[key]=obs
    return sorted(found.values(),key=lambda o:(o['cik'],prior.instant(o['accepted_at']),o['accession'])), rejected


def summarize_lookups(rows):
    ages=[r['age_days'] for r in rows if r['status']=='CLASSIFIED']
    return dict(counts=dict(Counter(r['status'] for r in rows)), median_age_days=statistics.median(ages) if ages else None,
                maximum_age_days=max(ages) if ages else None, age_over_365_days=sum(a>365 for a in ages))


def paired_changes(left, right):
    pairs = [(a['lookup'], b['lookup']) for a, b in zip(left, right)]
    improvements = [a['age_days']-b['age_days'] for a,b in pairs
                    if a['status']==b['status']=='CLASSIFIED']
    return dict(newly_classified=sum(a['status']!='CLASSIFIED' and b['status']=='CLASSIFIED' for a,b in pairs),
                changed_sic=sum(a.get('sic')!=b.get('sic') for a,b in pairs
                                if a['status']==b['status']=='CLASSIFIED'),
                fresher=sum(delta>0 for delta in improvements),
                median_age_reduction_days=statistics.median(improvements) if improvements else None,
                maximum_age_reduction_days=max(improvements) if improvements else None)


def catalog_discrepancy(observation, row):
    if row is None:
        return dict(accession=observation['accession'], reason='Header absent from window catalogue')
    delta=(prior.instant(observation['accepted_at'])-prior.instant(row['acceptanceDateTime'])).total_seconds()
    if delta or row['form']!=observation['form']:
        return dict(accession=observation['accession'],header_accepted_at=observation['accepted_at'],
                    catalog_accepted_at=row['acceptanceDateTime'],header_minus_catalog_seconds=delta,
                    header_form=observation['form'],catalog_form=row['form'],
                    chosen_clock='Verified header; do not silently reinterpret catalogue Z suffix')
    return None


def identity_assessments(inputs, obs, bodies):
    assessments=[]
    for roster in inputs['roster']:
        cik=roster['cik']; documents=[]
        for body in [b for b in bodies if b['cik']==cik]:
            header=next((o for o in obs if o['cik']==cik and o['accession']==body['accession']), None)
            catalog=next(r for r in inputs['catalogs'][cik] if r['accessionNumber']==body['accession'])
            facts=body['identity']['facts']
            ciks={f['value'].zfill(10) for f in facts if f['concept']=='EntityCentralIndexKey'}
            if ciks and ciks!={cik}: raise ValueError('Primary document CIK mismatch')
            symbols=[]
            for fact in [f for f in facts if f['concept']=='TradingSymbol']:
                titles=[f['value'] for f in facts if f['concept']=='Security12bTitle' and f['context']==fact['context']]
                symbols.append(dict(symbol=fact['value'],titles=titles,context=fact['context'],
                                    context_evidence=body['identity']['contexts'].get(fact['context'])))
            documents.append(dict(accession=body['accession'],source_url=body['url'],sha256=body['sha256'],
                                  accepted_at=header['accepted_at'] if header else catalog['acceptanceDateTime'],
                                  acceptance_basis='verified_header' if header else 'frozen_SEC_submissions_catalogue',
                                  document_cik_tag_verified=bool(ciks),symbols=symbols,
                                  source_path=str(fixture(body)),snippets=body['identity']['snippets']))
        assessments.append(dict(label=roster['label'],cik=cik,security_ids=[i['security_id'] for i in roster['identities']],
                                issuer_CIK='DIRECT_DATED_HEADER_EVIDENCE',
                                ticker_share_class='DIRECT_AT_DOCUMENT_OBSERVATIONS' if any(d['symbols'] for d in documents) else 'UNRESOLVED',
                                security_id_to_CIK='LOCAL_MAPPING_CORROBORATED_BY_PUBLIC_IDENTITY; NO_INDEPENDENT_EFFECTIVE_DATED_INTERVAL',
                                full_window_identity_continuity_proven=False,
                                static_or_local_evidence=roster['identities'],documents=documents))
    return assessments


def analyze():
    inputs=read(ROOT/'inputs.json'); obs,rejected=observations(inputs)
    windows=[]; comparisons=[]; bodies=[]
    for path in sorted((ROOT/'body').glob('*.json')):
        value=read(path); raw=gzip.decompress(Path(value['raw_gzip']).read_bytes())
        if prior.digest(raw)!=value['sha256']: raise ValueError('Body hash mismatch')
        if body_identity(raw.decode())!=value['identity']: raise ValueError('Identity replay mismatch')
        bodies.append(value)
    for roster in inputs['roster']:
        cik=roster['cik']; start=roster['start']; end=roster['end_exclusive']
        own=[o for o in obs if o['cik']==cik]
        inside=[o for o in own if start<=o['filing_date']<end]
        events=[e for e in inputs['events'] if e['security_id'] in {i['security_id'] for i in roster['identities']} and start<=e['entry_date']<end]
        rules={}; records=[]
        for rule in ('A','B'):
            history=[o for o in own if rule=='B' or periodic(o['form'])]
            window=[o for o in inside if rule=='B' or periodic(o['form'])]
            lookups=[dict(e,lookup=prior.lookup(history,cik,prior.instant(e['decision_at']))) for e in events]
            # Calendar probes diagnose temporal coverage independently of quarterly event clustering.
            probes=[]
            for year in range(int(start[:4]),int(end[:4])):
                for month in range(1,13):
                    from zoneinfo import ZoneInfo
                    cutoff=datetime(year,month,1,9,30,tzinfo=ZoneInfo('America/New_York'))
                    probes.append(dict(decision_at=cutoff.isoformat(),clock_is_synthetic=True,lookup=prior.lookup(history,cik,cutoff)))
            rules[rule]=dict(**prior.density(window), codes=sorted({o['sic'] for o in window}),
                             observations_detail=window, transitions=prior.transitions(window),
                             gaps_days=[(b-a).total_seconds()/86400 for a,b in zip(
                                 sorted({prior.instant(o['accepted_at']) for o in window}),
                                 sorted({prior.instant(o['accepted_at']) for o in window})[1:])],
                             events=lookups,event_summary=summarize_lookups([e['lookup'] for e in lookups]),
                             monthly_probes=probes,monthly_summary=summarize_lookups([e['lookup'] for e in probes]))
        regs=[o for o in own if periodic(o['form'])]
        for broad in [o for o in inside if not periodic(o['form'])]:
            earlier=[o for o in regs if prior.instant(o['accepted_at'])<=prior.instant(broad['accepted_at'])]
            later=[o for o in regs if prior.instant(o['accepted_at'])>=prior.instant(broad['accepted_at'])]
            before=earlier[-1] if earlier else None; after=later[0] if later else None
            records.append(dict(observation=broad,previous_periodic=before,next_periodic=after,
                                differs_previous=bool(before and before['sic']!=broad['sic']),
                                differs_next=bool(after and after['sic']!=broad['sic']),
                                bracket_same_code_conflict=bool(before and after and before['sic']==after['sic']!=broad['sic'])))
        catalog=inputs['catalogs'][cik]
        catalog_by_acc={r['accessionNumber']:r for r in catalog}
        mismatches=[]
        for observation in inside:
            row=catalog_by_acc.get(observation['accession'])
            discrepancy=catalog_discrepancy(observation,row)
            if discrepancy: mismatches.append(discrepancy)
        actual={o['accession'] for o in inside if periodic(o['form'])}
        expected={r['accessionNumber'] for r in catalog if periodic(r['form'])}
        windows.append(dict(label=roster['label'],cik=cik,start=start,end_exclusive=end,
                            available_catalog_filings=len(catalog),available_forms=dict(Counter(r['form'] for r in catalog)),
                            catalog_header_mismatches=mismatches,
                            expected_periodic=len(expected),missing_periodic=sorted(expected-actual),rules=rules,
                            event_change=paired_changes(rules['A']['events'],rules['B']['events']),
                            monthly_change=paired_changes(rules['A']['monthly_probes'],rules['B']['monthly_probes'])))
        comparisons+=records
    ledger=read(ROOT/'requests.json') if (ROOT/'requests.json').exists() else []
    aggregate={rule:dict(events=summarize_lookups([e['lookup'] for w in windows for e in w['rules'][rule]['events']]),
                         monthly=summarize_lookups([e['lookup'] for w in windows for e in w['rules'][rule]['monthly_probes']]),
                         observations=sum(w['rules'][rule]['observations'] for w in windows)) for rule in ('A','B')}
    conflicts=[]
    for cik in {o['cik'] for o in obs}:
        own=[o for o in obs if o['cik']==cik]
        for stamp in {prior.instant(o['accepted_at']) for o in own}:
            group=[o for o in own if prior.instant(o['accepted_at'])==stamp]
            if len({o['sic'] for o in group})>1: conflicts.append(group)
    result=dict(method=dict(classification='SEC SIC, not GICS',lookup='latest verified issuer FILER SIC accepted <= cutoff',
                            rule_A='10-K/10-Q families including amendments and transition reports',
                            rule_B='Rule A plus sampled other forms with independently matching issuer FILER SIC',
                            continuity_proven=False,stale_threshold_days=365,stale_threshold_is_descriptive=True),
                roster=inputs['roster'],windows=windows,form_comparison=comparisons,observations=obs,
                rejected_headers=rejected,identity_documents=bodies,aggregate=aggregate,same_instant_conflicts=conflicts,
                identity_assessments=identity_assessments(inputs,obs,bodies),
                requests=dict(attempted=len(ledger),succeeded=sum(r['outcome']=='SUCCESS' for r in ledger),
                              failed=sum(r['outcome']!='SUCCESS' for r in ledger),cap=CAP),
                reproducibility=dict(inputs_sha256=prior.digest((ROOT/'inputs.json').read_bytes()),
                                     baseline=inputs['baseline'],database_required=False,network_required_for_replay=False))
    atomic_json(ROOT/'results.json',result)
    atomic_json(ROOT/'filing_form_comparison.json',dict(aggregate=aggregate,nearby_periodic=comparisons,
                same_instant_conflicts=conflicts,rejected=rejected,
                paired_changes={w['label']:dict(events=w['event_change'],monthly=w['monthly_change']) for w in windows}))
    atomic_json(ROOT/'identity_evidence.json',result['identity_assessments'])
    atomic_json(ROOT/'observation_density.json',windows)
    print(json.dumps(dict(requests=result['requests'],aggregate=aggregate,rejected_headers=rejected),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare',action='store_true'); parser.add_argument('--fetch',action='store_true')
    parser.add_argument('--batch',type=int,default=30); parser.add_argument('--analyze',action='store_true'); args=parser.parse_args()
    if args.prepare: prepare()
    if args.fetch: fetch(args.batch)
    if args.analyze: analyze()
