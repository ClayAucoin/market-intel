"""Bounded, isolated historical SEC SIC research. No default action or DB path.

Preparation freezes saved evidence; planning and analysis are strictly offline.
Only explicit fetch with a pinned versioned plan can invoke transport.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
import fcntl
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from src.backtesting.sic_stage3 import periodic, parse_observation, body_identity, canonical_url
from src.backtesting.sic_validation_study import lookup, transitions, density, instant
from src.sec.acceptance_time import parse_submissions_acceptance
from src.sec.json_cache import atomic_json, validate_columns, validate_submissions

DEFAULT_ROOT = Path('logs/research/sec_sic_stage4_2026-09-26')
STAGE3 = Path('logs/research/sec_sic_stage3_2026-09-24')
CACHE = Path('data/cache/sec/submissions')
CAP = 240
ENVELOPES = dict(catalogue=20, periodic=90, identity=50, seed=20, eight_k=30, contingency=30)
NEW_CASES = [
    ('DELL_LEGACY', '0000826083', '2012', '2014', ['Dell Inc'], 'Dell pair'),
    ('DELL', '0001571996', '2017', '2019', ['Dell Technologies Inc'], 'Dell pair'),
    ('GM_LEGACY', '0000040730', '2008', '2010', ['General Motors Corp', 'Motors Liquidation Co'], 'GM pair'),
    ('GM', '0001467858', '2010', '2012', ['General Motors Co'], 'GM pair'),
    ('FOX_LEGACY', '0001308161', '2018', '2020', ['Twenty-First Century Fox Inc', 'TFCF Corp', 'News Corp'], 'Fox pair'),
    ('FOX', '0001754308', '2018', '2020', ['Fox Corp', 'Fox Corporation'], 'Fox pair'),
    ('DD', '0001666700', '2018', '2020', ['DowDuPont Inc', 'DuPont de Nemours Inc'], 'Dow/DuPont pair'),
    ('DOW', '0001751788', '2018', '2020', ['Dow Inc'], 'Dow/DuPont pair'),
    ('KRFT', '0001572709', '2014', '2016', ['Kraft Foods Group Inc'], 'Kraft pair'),
    ('KHC', '0001637459', '2014', '2016', ['Kraft Heinz Co', 'Kraft Heinz Company'], 'Kraft pair'),
]
PROTECTED = [STAGE3, Path('logs/research/sec_sic_pilot'),
             Path('logs/research/sec_sic_validation_2026-09-24'),
             Path('logs/research/sec_acceptance_source_discrepancy_2026-09-24'),
             Path('logs/research/ttwo_acceptance_correction_2026-09-25'),
             Path('logs/research/ttwo_acceptance_correction_2026-09-26_v2'), Path('data'), Path('src'), Path('tests')]


class GuardFailure(ValueError):
    """Safe stop; messages never include transport exceptions/credentials."""


def require(condition, message):
    if not condition:
        raise GuardFailure(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def digest(value):
    return sha(encoded(value))


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def frozen(path, value):
    """Exclusive creation and fsync: never replace evidence/plans/reviews/results."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(encoded(value))
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(path.parent)


def safe_root(root):
    root = Path(root)
    resolved = root.resolve()
    for protected in PROTECTED:
        p = protected.resolve()
        require(not resolved.is_relative_to(p) and not p.is_relative_to(resolved), 'Package overlaps protected project artifacts')
    require(resolved != Path.cwd().resolve(), 'Package cannot be repository root')
    return root


@contextmanager
def locked(root):
    root = safe_root(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise GuardFailure('Package is locked by another process') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def code_pins():
    paths = [Path(__file__), Path('src/backtesting/sic_stage3.py'),
             Path('src/backtesting/sic_validation_study.py'), Path('src/backtesting/sec_sic_pilot.py'),
             Path('src/sec/acceptance_time.py'), Path('src/sec/json_cache.py'), Path('src/sec/sec_http.py'),
             Path('src/sec/sec_client.py'), Path('src/analysis/event_timing.py')]
    return {str(p.relative_to(Path.cwd()) if p.is_absolute() else p): sha(p.read_bytes()) for p in paths}


def url(item):
    cik = item['cik']
    require(bool(re.fullmatch(r'\d{10}', cik)), 'Invalid candidate CIK')
    if item['kind'] == 'catalogue':
        return f'https://data.sec.gov/submissions/CIK{cik}.json'
    if item['kind'] == 'shard':
        name = item['document']
        require(bool(re.fullmatch(r'CIK' + cik + r'-submissions-\d{3}\.json', name)), 'Invalid shard identifier')
        return 'https://data.sec.gov/submissions/' + name
    if item['kind'] == 'exhibit':
        return canonical_url(dict(item, kind='body'))
    return canonical_url(item)


def evidence_raw(root, entry):
    path = Path(root) / entry['blob']
    require(path.resolve().is_relative_to(Path(root).resolve()), 'Evidence path escapes package')
    raw = gzip.decompress(path.read_bytes())
    require(sha(raw) == entry['sha256'], 'Saved evidence hash mismatch')
    return raw


def store_raw(root, item, raw, provenance):
    h = sha(raw)
    name = f'evidence/{h}.gz'
    p = Path(root) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        require(sha(gzip.decompress(p.read_bytes())) == h, 'Existing blob changed')
    else:
        with p.open('xb') as handle:
            handle.write(gzip.compress(raw, mtime=0))
            handle.flush()
            os.fsync(handle.fileno())
        sync_directory(p.parent)
    return dict(item=item, url=url(item), sha256=h, blob=name, provenance=provenance)


def catalogue_rows(data):
    columns = data.get('filings', {}).get('recent', data)
    validate_columns(columns)
    require(isinstance(columns.get('form'), list), 'Catalogue lacks forms')
    keys = ('accessionNumber', 'filingDate', 'acceptanceDateTime', 'form', 'primaryDocument', 'reportDate')
    return [{k: columns[k][n] for k in keys if k in columns} for n in range(len(columns['accessionNumber']))]


def name_key(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())


def candidate_check(case, sources):
    """Name disagreement blocks discovery; matching current names never accepts identity."""
    support, contradictions = [], []
    expected = {name_key(n) for n in case['expected_names']}
    for source in sources:
        data = source['data']
        if 'cik' not in data:
            continue
        names = [data.get('name', '')] + [r['name'] for r in data.get('formerNames', []) if 'name' in r]
        record = dict(path=source['path'], sha256=source['sha256'], names=names)
        if str(data['cik']).zfill(10) != case['cik'] or not expected.intersection(name_key(n) for n in names):
            contradictions.append(record)
        else:
            support.append(record)
    return dict(status='BLOCKED_CONTRADICTION' if contradictions else ('SUPPORTED_CANDIDATE' if support else 'UNSUPPORTED_DISCOVERY'),
                supporting_sources=support, contradictions=contradictions,
                issuer_identity_accepted=False, relationship_verified=False)


def prepare(root, stage3=STAGE3, cache=CACHE, roster=None, ticker_path=Path('data/cache/sec/company_tickers_exchange.json')):
    """Freeze only saved inputs; parameters allow small temporary offline fixtures."""
    root, stage3, cache = safe_root(root), Path(stage3), Path(cache)
    with locked(root):
        require(not (root / 'inputs.json').exists() and not (root / 'reuse_manifest.json').exists(), 'Package is already frozen or incomplete; use a new directory')
        saved = read(stage3 / 'inputs.json')
        results = read(stage3 / 'results.json')
        validation = read(stage3 / 'validation.json')
        for name in ('inputs.json', 'results.json', 'identity_review.json', 'policy_recommendations.json'):
            p = stage3 / name
            pins = [entry for entry in validation['files'] if Path(entry['path']).resolve() == p.resolve()]
            require(len(pins) == 1 and sha(p.read_bytes()) == pins[0]['sha256'], 'Stage 3 saved metadata pin mismatch')
        if roster is None:
            roster = []
            for r in saved['roster']:
                names = sorted({n for i in r['identities'] for n in i.get('verified_header_names', [])})
                roster.append(dict(label=r['label'], cik=r['cik'], start=r['start'], end_exclusive=r['end_exclusive'],
                                   expected_names=names, reason=r['reason'], saved_local_identities=r['identities'], candidate_pair=None))
            for label, cik, start, end, names, pair in NEW_CASES:
                roster.append(dict(label=label, cik=cik, start=start+'-01-01', end_exclusive=end+'-01-01',
                                   expected_names=names, reason='Adverse identity/coverage candidate; ' + pair,
                                   saved_local_identities=[], candidate_pair=pair))
            require(len(roster) == 20, 'Default roster must contain twenty issuers')
        require(len({r['cik'] for r in roster}) == len(roster), 'Roster CIKs must be unique')
        for r in roster:
            require(bool(re.fullmatch(r'\d{10}', r['cik'])), 'Invalid roster CIK')
            require(date.fromisoformat(r['start']) < date.fromisoformat(r['end_exclusive']), 'Invalid window')
        sources = {str(stage3 / n): sha((stage3 / n).read_bytes()) for n in ('inputs.json', 'results.json', 'identity_review.json', 'policy_recommendations.json', 'validation.json')}
        entries = []
        for obs in results['observations']:
            if obs['cik'] not in {r['cik'] for r in roster}:
                continue
            p = Path(obs['source_path']); d = read(p); raw = d['raw_header'].encode()
            require(sha(raw) == d['sha256'] == obs['sha256'], 'Stage 3 header pin mismatch')
            item = dict(kind='header', cik=obs['cik'], accession=obs['accession'])
            entries.append(store_raw(root, item, raw, dict(source_path=str(p), container_sha256=sha(p.read_bytes()), vintage=d.get('retrieved_at', d.get('observed_at')), basis='saved_raw_response')))
        for p in sorted((stage3 / 'body').glob('*.json')):
            d = read(p)
            if d['cik'] not in {r['cik'] for r in roster}:
                continue
            raw = gzip.decompress(Path(d['raw_gzip']).read_bytes())
            require(sha(raw) == d['sha256'], 'Stage 3 body pin mismatch')
            item = {k: d[k] for k in ('kind', 'cik', 'accession', 'document')}
            entries.append(store_raw(root, item, raw, dict(source_path=str(p), container_sha256=sha(p.read_bytes()), vintage=d.get('retrieved_at'), basis='saved_raw_response')))
        # Reuse original-vintage catalogue/shard sources only when the Stage 3
        # extraction pin still matches. This also makes nearest prewindow seeds
        # discoverable without refreshing changed main-response caches.
        for source, h in saved.get('source_hashes', {}).items():
            p = Path(source)
            match = re.fullmatch(r'CIK(\d{10})(-submissions-\d{3})?\.json', p.name)
            if not match or match[1] not in {r['cik'] for r in roster} or not p.exists() or sha(p.read_bytes()) != h:
                continue
            d = read(p)
            if 'raw_json' in d:
                raw = d['raw_json'].encode()
                require(sha(raw) == d['sha256'], 'Original submissions raw pin mismatch')
                basis = 'saved_raw_response'
            else:
                raw = p.read_bytes(); basis = 'saved_cache_serialization_not_HTTP_bytes'
            data = json.loads(raw)
            item = dict(kind='shard' if match[2] else 'catalogue', cik=match[1])
            if match[2]: item['document'] = p.name
            if item['kind'] == 'catalogue': validate_submissions(data, match[1])
            else: validate_columns(data)
            entries.append(store_raw(root, item, raw, dict(source_path=str(p), container_sha256=h, basis=basis)))
            if match[1] in saved['catalogs']:
                by_acc = {r['accessionNumber']: r for r in saved['catalogs'][match[1]]}
                for row in catalogue_rows(data):
                    require(row['accessionNumber'] not in by_acc or by_acc[row['accessionNumber']] == row, 'Original pinned catalogue conflicts with frozen rows')
                    by_acc[row['accessionNumber']] = row
                saved['catalogs'][match[1]] = sorted(by_acc.values(), key=lambda r: (r['filingDate'], r['accessionNumber']))
        checks, caches, vintage_changes = {}, [], []
        ticker = read(ticker_path) if Path(ticker_path).exists() else None
        if ticker:
            sources[str(ticker_path)] = sha(Path(ticker_path).read_bytes())
        for case in roster:
            found = []
            # Original Stage 3 catalogue rows stay frozen, regardless of current cache vintage.
            if case['cik'] in saved['catalogs']:
                for i in case.get('saved_local_identities', []):
                    for name in i.get('verified_header_names', []):
                        found.append(dict(path=str(stage3 / 'inputs.json'), sha256=sources[str(stage3 / 'inputs.json')], data=dict(cik=case['cik'], name=name)))
            else:
                for p in sorted(cache.glob('CIK'+case['cik']+'*.json')):
                    raw = p.read_bytes(); d = json.loads(raw)
                    found.append(dict(path=str(p), sha256=sha(raw), data=d))
                    kind = 'shard' if '-submissions-' in p.name else 'catalogue'
                    item = dict(kind=kind, cik=case['cik'])
                    if kind == 'shard': item['document'] = p.name
                    entries.append(store_raw(root, item, raw, dict(source_path=str(p), container_sha256=sha(raw), basis='saved_cache_serialization_not_HTTP_bytes')))
                    caches.append(str(p))
            if ticker:
                for row in ticker['data']:
                    obj = dict(zip(ticker['fields'], row))
                    if str(obj['cik']).zfill(10) == case['cik']:
                        found.append(dict(path=str(ticker_path), sha256=sources[str(ticker_path)], data=dict(cik=case['cik'], name=obj['name'])))
            checks[case['cik']] = candidate_check(case, found)
        for p, h in saved.get('source_hashes', {}).items():
            if not Path(p).exists() or sha(Path(p).read_bytes()) != h:
                vintage_changes.append(dict(path=p, original_sha256=h, status='PINNED_EXTRACTION_SOURCE_UNAVAILABLE_OR_CHANGED'))
        frozen(root / 'reuse_manifest.json', entries)
        frozen(root / 'candidate_review.json', checks)
        frozen(root / 'relationships.json', dict(status='UNREVIEWED_TEMPLATE', issuer_reviews=[], relationships=[],
                                               eight_k_intervals=[], clock_reviews=[], continuation=None,
                                               note='Create a versioned review file; do not edit frozen artifacts. Unknown boundaries/IDs remain null.'))
        inputs = dict(version=1, roster=roster, catalogs=saved['catalogs'], events=saved['events'], baseline=saved.get('baseline'),
                      source_pins=sources, source_vintage_limits=vintage_changes, new_cache_sources=caches,
                      code_sha256=code_pins(), cap=CAP, envelopes=ENVELOPES,
                      frozen_files={n: sha((root / n).read_bytes()) for n in ('reuse_manifest.json', 'candidate_review.json', 'relationships.json')},
                      adopted_decisions=dict(eight_k='Complete explicitly selected action/transition intervals; disclose remainder',
                                             timestamp='Explicit reviewed header research clock; preserve and quarantine disagreements',
                                             identity='Candidates are not accepted issuer/security relationships',
                                             classification='SEC SIC, not GICS', production_changes=False))
        frozen(root / 'inputs.json', inputs)
        frozen(root / 'inputs.sha256', sha((root / 'inputs.json').read_bytes()))
        frozen(root / 'requests.json', [])
        return dict(status='PREPARED_OFFLINE', inputs_sha256=sha((root / 'inputs.json').read_bytes()),
                    candidates=len(roster), blocked=[c for c, r in checks.items() if r['contradictions']],
                    unknown=[c for c, r in checks.items() if r['status'] == 'UNSUPPORTED_DISCOVERY'])


def load_inputs(root):
    root = safe_root(root)
    raw = (root / 'inputs.json').read_bytes()
    require(sha(raw) == read(root / 'inputs.sha256'), 'Frozen inputs changed')
    data = json.loads(raw)
    require(data['cap'] == CAP and data['envelopes'] == ENVELOPES, 'Budget configuration changed')
    for name, h in data['frozen_files'].items():
        require(sha((root / name).read_bytes()) == h, 'Frozen package artifact changed')
    require(data['code_sha256'] == code_pins(), 'Research code changed; review a new package')
    return data


def ledger(root, pending_batch=None):
    root = Path(root)
    rows = []
    reservations = sorted((root / 'attempts').glob('*.json'))
    for n, p in enumerate(reservations, 1):
        require(p.name == f'{n:06d}.json', 'Attempt ledger has a gap')
        row = read(p)
        require(row['attempt'] == n and row['outcome'] == 'IN_FLIGHT', 'Invalid durable reservation')
        outcome = root / 'outcomes' / p.name
        if outcome.exists():
            result = read(outcome)
            require(result['reservation_sha256'] == sha(p.read_bytes()), 'Reservation/outcome mismatch')
            row = dict(row, **result['result'])
        rows.append(row)
    require(read(root / 'requests.json') == rows, 'Ledger snapshot missing or changed; do not reset counts')
    require({p.name for p in (root / 'outcomes').glob('*.json')} <= {p.name for p in reservations}, 'Orphaned outcomes: reservation history was removed')
    require({p.name for p in (root / 'responses').glob('*.json')} <= {p.name for p in reservations}, 'Orphaned responses: reservation history was removed')
    if not rows:
        for batch in (root / 'batches').glob('plan_*.json'):
            if batch.name == pending_batch: continue
            require(not read(root / 'plans' / batch.name)['requests'], 'Reserved nonempty batch without attempt history; reconcile, never reset')
    return rows


def reserve(root, item, plan_name, charged):
    rows = ledger(root, pending_batch=plan_name)
    require(len(rows) < CAP, '240-attempt cap reached')
    require(Counter(r['charged_envelope'] for r in rows)[charged] < ENVELOPES[charged], 'Allocation envelope exhausted')
    require(sum(r['url'] == url(item) for r in rows) < 3, 'Three-attempt URL limit')
    if charged == 'identity':
        kind = 'header' if item['kind'] == 'header' else 'document'
        limit = 20 if kind == 'header' else 30
        require(sum(r['charged_envelope'] == 'identity' and ('header' if r['item']['kind'] == 'header' else 'document') == kind for r in rows) < limit, 'Identity sub-envelope exhausted')
    row = dict(attempt=len(rows)+1, item=item, url=url(item), plan=plan_name, charged_envelope=charged,
               outcome='IN_FLIGHT', reserved_at=datetime.now(timezone.utc).isoformat())
    frozen(Path(root) / 'attempts' / f"{row['attempt']:06d}.json", row)
    atomic_json(Path(root) / 'requests.json', rows + [row])
    return row


def finish(root, reservation, result):
    root = Path(root); n = reservation['attempt']
    frozen(root / 'outcomes' / f'{n:06d}.json', dict(reservation_sha256=sha((root / 'attempts' / f'{n:06d}.json').read_bytes()), result=result))
    # Rebuild snapshot from immutable records, never reset reservation history.
    rows = read(root / 'requests.json')
    rows[n-1] = dict(reservation, **result)
    atomic_json(root / 'requests.json', rows)


def all_evidence(root):
    entries = read(Path(root) / 'reuse_manifest.json')
    for row in ledger(root):
        if 'evidence' in row:
            entries.append(row['evidence'])
    for path in sorted((Path(root) / 'responses').glob('*.json')):
        response = read(path)
        reservation = Path(root) / 'attempts' / path.name
        require(response['reservation_sha256'] == sha(reservation.read_bytes()), 'Response reservation pin mismatch')
        entry = response['evidence']
        require(entry['url'] == read(reservation)['url'], 'Response URL mismatch')
        entries.append(entry)
    entries = list({(e['url'], e['sha256']): e for e in entries}.values())
    for e in entries:
        evidence_raw(root, e)
    return entries


def by_url(entries, target):
    found = [e for e in entries if e['url'] == target]
    require(len({e['sha256'] for e in found}) <= 1, 'Conflicting saved URL vintages; no automatic selection/refetch')
    return found[0] if found else None


def inventories(root, inputs, entries):
    catalogs, missing_shards, checks = {}, {}, read(Path(root) / 'candidate_review.json')
    for case in inputs['roster']:
        cik = case['cik']; rows = {}; missing = []
        found = []; main = by_url(entries, url(dict(kind='catalogue', cik=cik)))
        known = cik in inputs['catalogs'] or main is not None
        for row in inputs['catalogs'].get(cik, []): rows[row['accessionNumber']] = row
        if main:
            try:
                data = json.loads(evidence_raw(root, main))
                validate_submissions(data, cik)
            except (ValueError, UnicodeError, KeyError):
                checks = dict(checks, **{cik: dict(status='BLOCKED_INVALID_CATALOGUE', supporting_sources=[], issuer_identity_accepted=False,
                                                 contradictions=[dict(path=main['blob'], sha256=main['sha256'], reason='Invalid catalogue or CIK')])})
                catalogs[cik] = dict(known=False, rows=list(rows.values()))
                missing_shards[cik] = []
                continue
            found.append(dict(path=main['provenance'].get('source_path', main['blob']), sha256=main['sha256'], data=data))
            # Record CIK/name contradictions before accepting catalogue extraction.
            if str(data.get('cik', '')).zfill(10) == cik:
                validate_submissions(data, cik)
                tables = [data]
                for shard in data['filings'].get('files', []):
                    if shard.get('filingTo', case['start']) < case['start'] or shard.get('filingFrom', case['end_exclusive']) >= case['end_exclusive']:
                        continue
                    item = dict(kind='shard', cik=cik, document=shard['name'])
                    e = by_url(entries, url(item))
                    if e:
                        try:
                            table = json.loads(evidence_raw(root, e))
                            validate_columns(table)
                            tables.append(table)
                        except (ValueError, UnicodeError):
                            missing.append(dict(item, saved_processing_failure=True))
                    else: missing.append(item)
                for table in tables:
                    for row in catalogue_rows(table):
                        acc = row['accessionNumber']
                        if acc in rows and rows[acc] != row:
                            checks = dict(checks, **{cik: dict(status='BLOCKED_CATALOGUE_CONFLICT', supporting_sources=[], issuer_identity_accepted=False,
                                                             contradictions=[dict(path=main['blob'], accession=acc, reason='Conflicting catalogue duplicate')])})
                            known = False
                            continue
                        rows[acc] = row
            else:
                known = False
        check = candidate_check(case, found)
        if checks[cik]['contradictions']:
            check = checks[cik]
        elif not found:
            check = checks[cik]
        for entry in entries:
            if entry['item']['cik'] != cik or entry['item']['kind'] not in ('body', 'exhibit'): continue
            try:
                facts = body_identity(evidence_raw(root, entry).decode())['facts']
                ciks = {f['value'].zfill(10) for f in facts if f['concept'] == 'EntityCentralIndexKey'}
            except UnicodeError:
                continue
            if ciks and ciks != {cik}:
                check = dict(check, status='BLOCKED_DOCUMENT_CIK_CONTRADICTION',
                             contradictions=check['contradictions'] + [dict(path=entry['blob'], sha256=entry['sha256'], reason='Primary/exhibit CIK tags contradict candidate')])
        catalogs[cik] = dict(known=known, rows=sorted(rows.values(), key=lambda r: (r['filingDate'], r['accessionNumber'])))
        missing_shards[cik] = missing
        checks = dict(checks, **{cik: check})
    return catalogs, missing_shards, checks


def review_file(root, path=None, pin=None):
    if path is None:
        require(pin is None, 'Review hash supplied without file')
        return dict(issuer_reviews=[], relationships=[], eight_k_intervals=[], clock_reviews=[], continuation=None), None
    path = Path(path)
    require(bool(re.fullmatch(r'review_\d{2,}\.json', path.name)), 'Review must be versioned review_NN.json')
    require(pin is not None and sha(path.read_bytes()) == pin, 'Explicit review hash mismatch')
    d = read(path)
    require(d['inputs_sha256'] == sha((Path(root) / 'inputs.json').read_bytes()), 'Review refers to different inputs')
    require(bool(d.get('reviewed_by')), 'Review lacks reviewer')
    cases = {r['cik']: r for r in read(Path(root)/'inputs.json')['roster']}
    for collection in ('issuer_reviews', 'relationships', 'eight_k_intervals', 'clock_reviews', 'identity_requests'):
        require(isinstance(d.get(collection, []), list), 'Review collection must be an array')
        for r in d.get(collection, []):
            require(r.get('cik') in cases, 'Review introduces an unrostered issuer')
            if collection == 'eight_k_intervals':
                case = cases[r['cik']]
                date.fromisoformat(r['start']); date.fromisoformat(r['end_exclusive'])
                require(case['start'] <= r['start'] < r['end_exclusive'] <= case['end_exclusive'], '8-K interval exceeds frozen window')
                require(r.get('reason') and isinstance(r.get('reviewed'), bool), 'Interval lacks reason/review decision')
            if collection in ('issuer_reviews', 'relationships'):
                require(r.get('status') in ('ACCEPTED', 'UNKNOWN', 'CONFLICT', 'CANDIDATE'), 'Unknown identity review status')
                if r.get('knowledge_at'): instant(r['knowledge_at'])
                if r['status'] == 'ACCEPTED': require(r.get('knowledge_at') and r.get('reviewed_by') and r.get('evidence'), 'Accepted identity review is incomplete')
                for key in ('effective_from', 'effective_to'):
                    if r.get(key): instant(r[key])
                if r.get('effective_from') and r.get('effective_to'):
                    require(instant(r['effective_from']) < instant(r['effective_to']), 'Identity interval is reversed')
    return d, dict(path=str(path), sha256=pin)


def in_intervals(case, row, review):
    return any(i['cik'] == case['cik'] and i['start'] <= row['filingDate'] < i['end_exclusive']
               and i.get('reason') and i.get('reviewed') is True for i in review.get('eight_k_intervals', []))


def stop_review(rows, review):
    require(not any(r.get('status') in (401, 403, 429) or 300 <= r.get('status', 0) < 400 or r['outcome'] == 'SIZE_FAILURE' for r in rows), 'Persistent denial/redirect/size stop; no further retrieval')
    problems = [r['attempt'] for r in rows if r['outcome'] != 'SUCCESS']
    if rows:
        require(review.get('continuation') == dict(ledger_sha256=digest(rows), acknowledged_attempts=problems), 'Failure/interruption requires pinned continuation review')


def request_candidates(inputs, catalogs, shards, checks, review):
    candidates = []
    for case in inputs['roster']:
        cik = case['cik']
        if checks[cik]['contradictions']: continue
        if not catalogs[cik]['known']:
            candidates.append(dict(kind='catalogue', cik=cik, envelope='catalogue', reason='Unverified discovery catalogue'))
            continue
        candidates += [dict(i, envelope='catalogue', reason='Missing overlapping historical shard') for i in shards[cik]]
        inside = [r for r in catalogs[cik]['rows'] if case['start'] <= r['filingDate'] < case['end_exclusive']]
        candidates += [dict(kind='header', cik=cik, accession=r['accessionNumber'], expected_form=r['form'], envelope='periodic', reason='Mandatory periodic baseline') for r in inside if periodic(r['form'])]
        earlier = [r for r in catalogs[cik]['rows'] if r['filingDate'] < case['start'] and periodic(r['form'])]
        if earlier:
            r = earlier[-1]
            candidates.append(dict(kind='header', cik=cik, accession=r['accessionNumber'], expected_form=r['form'], envelope='seed', reason='Nearest catalogued prewindow periodic seed'))
        # Complete all catalogue accessions in reviewed action/transition intervals.
        candidates += [dict(kind='header', cik=cik, accession=r['accessionNumber'], expected_form=r['form'], envelope='eight_k', reason='Reviewed complete action/transition interval') for r in inside if r['form'] in ('8-K', '8-K/A') and in_intervals(case, r, review)]
    for item in review.get('identity_requests', []):
        require(item['kind'] in ('header', 'body', 'exhibit'), 'Invalid identity request kind')
        require(item.get('reason'), 'Identity request lacks reason')
        candidates.append(dict(item, envelope='identity'))
    order = dict(catalogue=0, periodic=1, identity=2, seed=3, eight_k=4)
    return sorted(candidates, key=lambda i: order[i['envelope']])


def baseline_ready(root, inputs, catalogs, shards, checks, entries):
    obs, _, _, _ = header_observations(root, inputs, entries, catalogs)
    verified = {(o['cik'], o['accession']) for o in obs if periodic(o['form'])}
    for case in inputs['roster']:
        cik = case['cik']
        if checks[cik]['contradictions']: continue
        if not catalogs[cik]['known'] or shards[cik]: return False
        if any((cik, r['accessionNumber']) not in verified for r in catalogs[cik]['rows']
               if case['start'] <= r['filingDate'] < case['end_exclusive'] and periodic(r['form'])):
            return False
    return True


def plan_requests(root, review_path=None, review_pin=None):
    root = safe_root(root)
    with locked(root):
        inputs = load_inputs(root); rows = ledger(root); entries = all_evidence(root)
        review, review_ref = review_file(root, review_path, review_pin)
        stop_review(rows, review)
        catalogs, shards, checks = inventories(root, inputs, entries)
        require_acknowledgements(root, inputs, entries, catalogs, checks, review)
        items, seen, used = [], set(), Counter(r['charged_envelope'] for r in rows)
        identity_kinds = Counter('header' if r['item']['kind'] == 'header' else 'document' for r in rows if r['charged_envelope'] == 'identity')
        candidates = request_candidates(inputs, catalogs, shards, checks, review)
        missing_k = {url(i) for i in candidates if i['envelope'] == 'eight_k' and not by_url(entries, url(i))}
        require(len(missing_k) + used['eight_k'] <= ENVELOPES['eight_k'], 'Selected complete 8-K intervals exceed envelope; review intervals, never silently trim')
        for item in candidates:
            validate_item(item, inputs, catalogs, shards, checks, review)
            target = url(item)
            if target in seen: continue
            seen.add(target)
            if by_url(entries, target): continue
            if item['envelope'] == 'eight_k' and not baseline_ready(root, inputs, catalogs, shards, checks, entries): break
            previous = sum(r['url'] == target for r in rows)
            require(previous < 3, 'Three-attempt URL limit')
            charged = 'contingency' if previous else item['envelope']
            if used[charged] >= ENVELOPES[charged]:
                # Do not silently omit a higher-priority unfinished requirement.
                break
            if charged == 'identity':
                kind = 'header' if item['kind'] == 'header' else 'document'
                if identity_kinds[kind] >= (20 if kind == 'header' else 30): break
                identity_kinds[kind] += 1
            if len(rows) + len(items) >= CAP: break
            batch = 10 if items and any(i['kind'] in ('catalogue', 'shard') for i in items) or item['kind'] in ('catalogue', 'shard') else 20
            if len(items) >= batch: break
            item = dict(item, url=target, charged_envelope=charged)
            items.append(item); used[charged] += 1
        number = len(list((root / 'plans').glob('plan_*.json'))) + 1
        path = root / 'plans' / f'plan_{number:02d}.json'
        data = dict(version=1, inputs_sha256=sha((root / 'inputs.json').read_bytes()), ledger_sha256=digest(rows),
                    evidence_sha256=digest(entries), review=review_ref, requests=items,
                    blocked_cases={c: v for c, v in checks.items() if v['contradictions']},
                    envelopes=ENVELOPES, cap=CAP, no_automatic_budget_transfer=True)
        frozen(path, data)
        return dict(status='PLAN_SAVED_OFFLINE', path=str(path), sha256=sha(path.read_bytes()), planned_attempts=len(items), blocked_cases=list(data['blocked_cases']))


def validate_item(item, inputs, catalogs, shards, checks, review):
    case = next((r for r in inputs['roster'] if r['cik'] == item['cik']), None)
    require(case is not None and not checks[case['cik']]['contradictions'], 'Unknown or contradicted candidate; retrieval blocked')
    require(item['envelope'] in ENVELOPES and item['envelope'] != 'contingency', 'Request purpose envelope invalid')
    url(item)
    if item['kind'] == 'catalogue':
        require(item['envelope'] == 'catalogue' and not catalogs[case['cik']]['known'], 'Unnecessary discovery refresh')
    elif item['kind'] == 'shard':
        require(item['envelope'] == 'catalogue' and any(i['document'] == item['document'] for i in shards[case['cik']]), 'Unlisted or unnecessary shard')
    else:
        row = next((r for r in catalogs[case['cik']]['rows'] if r['accessionNumber'] == item['accession']), None)
        require(row is not None, 'Accession absent from frozen catalogue')
        require(item.get('expected_form', row['form']) == row['form'], 'Request form mismatch')
        if item['envelope'] == 'periodic': require(item['kind'] == 'header' and periodic(row['form']), 'Not a periodic header')
        elif item['envelope'] == 'eight_k': require(item['kind'] == 'header' and row['form'] in ('8-K', '8-K/A') and in_intervals(case, row, review), '8-K outside reviewed intervals')
        elif item['envelope'] == 'seed': require(item['kind'] == 'header' and periodic(row['form']) and row['filingDate'] < case['start'], 'Invalid prewindow seed')
        elif item['envelope'] == 'identity':
            require(any(url(i) == url(item) for i in review.get('identity_requests', [])), 'Identity request not reviewed')
            if item['kind'] == 'body': require(item['document'] == row.get('primaryDocument'), 'Body is not catalogue primary document')


def transport(item):
    """One call only. No implicit retries, importer, redirects or DB fallback."""
    import requests
    from src.sec.sec_client import SEC_HEADERS
    from src.sec.sec_http import _pace
    _pace()
    limit = 262144 if item['kind'] == 'header' else (16000000 if item['kind'] in ('body', 'exhibit') else 8000000)
    with requests.get(url(item), headers=SEC_HEADERS, timeout=(10, 30), stream=True, allow_redirects=False) as response:
        if response.status_code != 200:
            return response.status_code, b'', 'HTTP_FAILURE'
        chunks, size = [], 0
        for chunk in response.iter_content(8192):
            size += len(chunk)
            if size > limit: return 200, b'', 'SIZE_FAILURE'
            chunks.append(chunk)
        return 200, b''.join(chunks), 'SUCCESS'


def fetch(root, plan_path, plan_pin):
    root = safe_root(root); plan_path = Path(plan_path)
    with locked(root):
        require(plan_path.resolve().parent == (root / 'plans').resolve() and re.fullmatch(r'plan_\d{2,}\.json', plan_path.name), 'Plan must be a versioned package plan')
        require(plan_pin and sha(plan_path.read_bytes()) == plan_pin, 'Explicit plan hash mismatch')
        plan = read(plan_path); inputs = load_inputs(root); rows = ledger(root); entries = all_evidence(root)
        require(plan['inputs_sha256'] == sha((root / 'inputs.json').read_bytes()), 'Plan inputs changed')
        require(plan['ledger_sha256'] == digest(rows) and plan['evidence_sha256'] == digest(entries), 'Stale plan; ledger/evidence changed')
        require(plan['cap'] == CAP and plan['envelopes'] == ENVELOPES, 'Plan changes allocation')
        ref = plan['review']; review, _ = review_file(root, ref['path'], ref['sha256']) if ref else review_file(root)
        stop_review(rows, review)
        catalogs, shards, checks = inventories(root, inputs, entries)
        require_acknowledgements(root, inputs, entries, catalogs, checks, review)
        items = plan['requests']; batch = 10 if any(i['kind'] in ('catalogue', 'shard') for i in items) else 20
        require(len(items) <= batch and len({url(i) for i in items}) == len(items), 'Batch size/duplicate violation')
        simulated = Counter(r['charged_envelope'] for r in rows)
        identity_kinds = Counter('header' if r['item']['kind'] == 'header' else 'document' for r in rows if r['charged_envelope'] == 'identity')
        for item in items:
            validate_item(item, inputs, catalogs, shards, checks, review)
            if item['envelope'] == 'eight_k':
                require(baseline_ready(root, inputs, catalogs, shards, checks, entries), 'Periodic baseline incomplete; 8-K layer blocked')
            require(item['url'] == url(item), 'Noncanonical request URL')
            if by_url(entries, item['url']): continue
            previous = sum(r['url'] == item['url'] for r in rows)
            require(previous < 3, 'Three-attempt URL limit')
            require(item['charged_envelope'] == ('contingency' if previous else item['envelope']), 'Budget transfer/retry charge invalid')
            charged = item['charged_envelope']; simulated[charged] += 1
            require(simulated[charged] <= ENVELOPES[charged], 'Allocation envelope exhausted')
            if charged == 'identity': identity_kinds['header' if item['kind'] == 'header' else 'document'] += 1
        require(sum(simulated.values()) <= CAP, '240-attempt cap reached')
        require(identity_kinds['header'] <= 20 and identity_kinds['document'] <= 30, 'Identity sub-envelope exhausted')
        batch_path = root / 'batches' / plan_path.name
        require(not batch_path.exists(), 'Plan batch already reserved; create a new reviewed plan')
        frozen(batch_path, dict(plan_sha256=plan_pin, ledger_before_sha256=digest(rows)))
        # Each plan may run once. Crash recovery uses a new versioned plan/review.
        for item in items:
            if by_url(entries, item['url']): continue
            reservation = reserve(root, item, plan_path.name, item['charged_envelope'])
            try:
                status, raw, outcome = transport(item)
            except Exception:
                finish(root, reservation, dict(outcome='NETWORK_FAILURE'))
                raise GuardFailure('Transport failure recorded; review before retry') from None
            result = dict(outcome=outcome, status=status)
            if outcome == 'SUCCESS':
                entry = store_raw(root, item, raw, dict(basis='new_raw_response', reserved_at=reservation['reserved_at']))
                frozen(root / 'responses' / f"{reservation['attempt']:06d}.json",
                       dict(reservation_sha256=sha((root/'attempts'/f"{reservation['attempt']:06d}.json").read_bytes()), evidence=entry))
                result['evidence'] = entry
                try:
                    text = raw.decode('utf-8')
                    if item['kind'] in ('catalogue', 'shard'):
                        data = json.loads(text)
                        if item['kind'] == 'catalogue': validate_submissions(data, item['cik'])
                        else: validate_columns(data)
                    elif item['kind'] == 'header':
                        obs = parse_observation(text, item['cik'], item['accession'])
                        expected = next(r['form'] for r in catalogs[item['cik']]['rows'] if r['accessionNumber'] == item['accession'])
                        require(obs['form'] == expected, 'Header form mismatch')
                    else:
                        ciks = {f['value'].zfill(10) for f in body_identity(text)['facts'] if f['concept'] == 'EntityCentralIndexKey'}
                        require(not ciks or ciks == {item['cik']}, 'Document CIK mismatch')
                except (ValueError, UnicodeError):
                    result['outcome'] = 'PROCESSING_FAILURE'
            finish(root, reservation, result)
            if result['outcome'] != 'SUCCESS':
                raise GuardFailure('Batch stopped; raw successful responses retained, review required')
            # A discovery contradiction stops this batch before further requests.
            _, _, current = inventories(root, inputs, all_evidence(root))
            if current[item['cik']]['contradictions']:
                raise GuardFailure('Fetched evidence contradicts candidate; case blocked for review')
            # Newly discovered clock conflicts stop this batch; continuing unrelated
            # requests requires a new plan acknowledging the saved conflict.
            if item['kind'] == 'header':
                _, _, clocks, _ = header_observations(root, inputs, [entry], catalogs)
                if clocks and not all(clock_approved(c, review) for c in clocks):
                    raise GuardFailure('Source-clock conflict saved; review before another batch')
        return dict(status='BATCH_SAVED', attempts=len(ledger(root)), plan=plan_path.name)


def header_observations(root, inputs, entries, catalogs):
    observations, rejected, conflicts, documents = [], [], [], []
    for e in entries:
        item = e['item']
        try:
            raw = evidence_raw(root, e).decode('utf-8')
        except UnicodeError:
            rejected.append(dict(cik=item['cik'], url=e['url'], sha256=e['sha256'], reason='Invalid UTF-8 response retained'))
            continue
        if item['kind'] in ('body', 'exhibit'):
            documents.append(dict(e, extracted=body_identity(raw)))
        if item['kind'] != 'header': continue
        try:
            o = parse_observation(raw, item['cik'], item['accession'])
            row = next((r for r in catalogs[item['cik']]['rows'] if r['accessionNumber'] == item['accession']), None)
            if row is not None: require(o['form'] == row['form'], 'Header/catalogue form mismatch')
            clock = re.search(r'ACCEPTANCE-DATETIME[^0-9]{0,20}(\d{14})', html.unescape(raw))
            o.update(url=e['url'], sha256=e['sha256'], raw_header_clock=clock.group(1) if clock else None,
                     raw_submissions_clock=row.get('acceptanceDateTime') if row else None, clock_basis='verified_header_research_only', clock_conflict=False)
            if row:
                try:
                    stamp = parse_submissions_acceptance(row.get('acceptanceDateTime'))
                except ValueError:
                    stamp = None
                o['submissions_utc'] = stamp.isoformat() if stamp else None
                if stamp is None or stamp != instant(o['accepted_at']):
                    o['clock_conflict'] = True
                    conflicts.append(dict(cik=o['cik'], accession=o['accession'], raw_header=o['raw_header_clock'],
                                          raw_submissions=o['raw_submissions_clock'], header_utc=instant(o['accepted_at']).isoformat(),
                                          submissions_utc=o['submissions_utc'], header_sha256=e['sha256']))
            observations.append(o)
        except ValueError:
            rejected.append(dict(cik=item['cik'], accession=item['accession'], url=e['url'], sha256=e['sha256'], reason='Header issuer/FILER/form/time eligibility failed'))
    unique = {(o['cik'], o['accession'], o['sha256']): o for o in observations}
    return list(unique.values()), rejected, conflicts, documents


def clock_approved(conflict, review):
    return any(r['cik'] == conflict['cik'] and r['accession'] == conflict['accession']
               and r['header_sha256'] == conflict.get('header_sha256', conflict.get('sha256'))
               and r.get('basis') == 'verified_header_research_only' and r.get('reviewed_by')
               for r in review.get('clock_reviews', []))


def require_acknowledgements(root, inputs, entries, catalogs, checks, review):
    blocked = sorted(c for c, v in checks.items() if v['contradictions'])
    require(not blocked or review.get('acknowledged_contradictions') == blocked, 'Candidate contradictions require saved review; affected cases stay blocked')
    _, _, clocks, _ = header_observations(root, inputs, entries, catalogs)
    pending = sorted(c['cik'] + '/' + c['accession'] + '/' + c['header_sha256'] for c in clocks if not clock_approved(c, review))
    require(not pending or review.get('acknowledged_clock_conflicts') == pending, 'Source-clock conflicts require saved acknowledgement or explicit research-clock review')


def source_review_valid(root, proof, entries, observations, cik, review):
    e = by_url(entries, proof['url'])
    require(e is not None and e['sha256'] == proof['sha256'] and e['item']['cik'] == cik, 'Review source missing/mismatched')
    item = e['item']
    o = next((o for o in observations if o['cik'] == cik and o['accession'] == item.get('accession')), None)
    require(o is not None, 'Review source lacks eligible dated issuer header')
    raw = evidence_raw(root, e).decode()
    text = ' '.join(BeautifulSoup(raw, 'html.parser').get_text(' ', strip=True).split())
    require(proof.get('location') and proof.get('quote') and proof['quote'] in text, 'Review requires exact saved source quote/location')
    if item['kind'] in ('body', 'exhibit'):
        tags = body_identity(raw)['facts']
        ciks = {f['value'].zfill(10) for f in tags if f['concept'] == 'EntityCentralIndexKey'}
        require(not ciks or ciks == {cik}, 'Document CIK contradicts review')
    if o['clock_conflict'] and not clock_approved(o, review): return None
    return instant(o['accepted_at'])


def identity_gate(root, review, entries, observations, cik, cutoff, security_id=None):
    if security_id is not None:
        issuer = identity_gate(root, review, entries, observations, cik, cutoff)
        if issuer != 'ACCEPTED': return issuer
    candidates = [r for r in review.get('issuer_reviews' if security_id is None else 'relationships', [])
                  if (r['cik'] == cik if security_id is None else r.get('security_id') == security_id)]
    valid, disputed, undated_conflict = [], False, False
    for r in candidates:
        if r.get('status') == 'CONFLICT':
            if r.get('knowledge_at') and instant(r['knowledge_at']) <= cutoff: disputed = True
            elif not r.get('knowledge_at'): undated_conflict = True
            continue
        if r.get('status') != 'ACCEPTED': continue
        require(r.get('reviewed_by') and r.get('evidence'), 'Accepted identity lacks reviewed evidence')
        stamps = [source_review_valid(root, p, entries, observations, r['cik'], review) for p in r['evidence']]
        if any(stamp is None for stamp in stamps): continue
        knowledge = max(stamps + [instant(r['knowledge_at'])])
        if cutoff < knowledge: continue
        if security_id is not None:
            if not r.get('effective_from') or not r.get('class_title') or not r.get('interval_basis'): continue
            require(any(next(e for e in entries if e['url'] == p['url'])['item']['kind'] in ('body', 'exhibit') for p in r['evidence']), 'Security binding needs class/action document evidence')
            require(any(r['class_title'] in p['quote'] for p in r['evidence']), 'Class title is unsupported by quoted evidence')
            if r.get('symbol'):
                require(any(r['symbol'] in p['quote'] and r['class_title'] in p['quote'] for p in r['evidence']), 'Symbol/class association is not supported by quoted evidence')
            if cutoff < instant(r['effective_from']): continue
            if r.get('effective_to') and cutoff >= instant(r['effective_to']): continue
        valid.append(r)
    if undated_conflict: return 'UNKNOWN'
    if disputed or len(valid) > 1: return 'AMBIGUOUS'
    return 'ACCEPTED' if valid and valid[0]['cik'] == cik else 'UNKNOWN'


def gated_lookup(root, review, entries, obs, cik, cutoff, security_id=None, identity_observations=None):
    identity = identity_gate(root, review, entries, identity_observations if identity_observations is not None else obs, cik, cutoff, security_id)
    if identity != 'ACCEPTED': return dict(status=identity if identity == 'AMBIGUOUS' else 'UNKNOWN', reason='Unresolved identity/knowledge-time binding')
    eligible, timing = [], []
    for o in obs:
        if o['cik'] != cik: continue
        if o['clock_conflict']:
            approved = clock_approved(o, review)
            times = [instant(o['accepted_at'])] + ([instant(o['submissions_utc'])] if o.get('submissions_utc') else [])
            if not approved and min(times) <= cutoff:
                return dict(status='UNKNOWN', reason='Unreviewed source-clock conflict', accession=o['accession'])
            if min(times) <= cutoff < max(times): timing.append(o['accession'])
        eligible.append(o)
    result = lookup(eligible, cik, cutoff)
    return dict(result, clock_basis='verified_header_research_only', timing_conflicts=timing)


def analyze(root, review_path=None, review_pin=None):
    root = safe_root(root)
    with locked(root):
        inputs = load_inputs(root); entries = all_evidence(root); rows = ledger(root)
        review, ref = review_file(root, review_path, review_pin)
        catalogs, shards, checks = inventories(root, inputs, entries)
        obs, rejected, clocks, documents = header_observations(root, inputs, entries, catalogs)
        windows, real_events = [], []
        for case in inputs['roster']:
            cik = case['cik']; inside = [r for r in catalogs[cik]['rows'] if case['start'] <= r['filingDate'] < case['end_exclusive']]
            own = [o for o in obs if o['cik'] == cik]
            if checks[cik]['contradictions']: own = []
            regular = [o for o in own if periodic(o['form'])]
            broader = regular + [o for o in own if o['form'] in ('8-K', '8-K/A')]
            temporal_regular = [o for o in regular if not o['clock_conflict'] or clock_approved(o, review)]
            temporal_broader = [o for o in broader if not o['clock_conflict'] or clock_approved(o, review)]
            periodic_expected = {r['accessionNumber'] for r in inside if periodic(r['form'])}
            k_expected = {r['accessionNumber'] for r in inside if r['form'] in ('8-K', '8-K/A')}
            selected = {r['accessionNumber'] for r in inside if r['form'] in ('8-K', '8-K/A') and in_intervals(case, r, review)}
            fetched = {e['item']['accession'] for e in entries if e['item']['kind'] == 'header' and e['item']['cik'] == cik}
            eligible = {o['accession'] for o in own}
            probes = []
            for year in range(int(case['start'][:4]), int(case['end_exclusive'][:4])):
                for month in range(1, 13):
                    cutoff = datetime(year, month, 1, 9, 30, tzinfo=ZoneInfo('America/New_York'))
                    probes.append(dict(cutoff=cutoff.isoformat(), synthetic=True, trading_session=False,
                                       periodic=gated_lookup(root, review, entries, regular, cik, cutoff, identity_observations=obs),
                                       periodic_plus_8k=gated_lookup(root, review, entries, broader, cik, cutoff, identity_observations=obs)))
            complete = catalogs[cik]['known'] and not checks[cik]['contradictions'] and not shards[cik] and not (periodic_expected - eligible)
            windows.append(dict(label=case['label'], cik=cik, candidate_review=checks[cik], catalog_known=catalogs[cik]['known'], missing_shards=shards[cik],
                                periodic_complete=bool(complete), periodic_expected=sorted(periodic_expected), periodic_missing=sorted(periodic_expected-eligible),
                                eight_k_expected=sorted(k_expected), eight_k_selected=sorted(selected),
                                eight_k_unexamined_outside_intervals=sorted(k_expected-selected-fetched),
                                eight_k_selected_unretrieved=sorted(selected-fetched), eight_k_selected_ineligible=sorted((selected & fetched)-eligible),
                                eight_k_eligible=sorted(k_expected & eligible), eight_k_complete=bool(catalogs[cik]['known'] and not shards[cik] and k_expected <= eligible),
                                clock_quarantined_accessions=sorted(o['accession'] for o in own if o['clock_conflict'] and not clock_approved(o, review)),
                                periodic_density=density([o for o in temporal_regular if case['start'] <= o['filing_date'] < case['end_exclusive']]),
                                transition_bounds=dict(periodic=transitions(temporal_regular), periodic_plus_8k=transitions(temporal_broader)), probes=probes))
            ids = {i['security_id'] for i in case.get('saved_local_identities', [])}
            for event in inputs['events']:
                if event['security_id'] not in ids or not case['start'] <= event['entry_date'] < case['end_exclusive']: continue
                cutoff = instant(event['decision_at'])
                real_events.append(dict(event, cik=cik, real_saved_event=True, conditional_original_sample=True,
                                        periodic=gated_lookup(root, review, entries, regular, cik, cutoff, event['security_id'], obs),
                                        periodic_plus_8k=gated_lookup(root, review, entries, broader, cik, cutoff, event['security_id'], obs)))
        n = len(list((root / 'reports').glob('report_*'))) + 1
        destination = root / 'reports' / f'report_{n:02d}'
        require(not destination.exists(), 'Report destination already exists')
        destination.mkdir(parents=True)
        results = dict(method=inputs['adopted_decisions'], windows=windows, real_events=real_events, observations=obs,
                       supplemental_other_forms=[o for o in obs if not periodic(o['form']) and o['form'] not in ('8-K', '8-K/A')],
                       identity_documents=documents, rejected_headers=rejected, requests=dict(attempted=len(rows), envelopes=dict(Counter(r['charged_envelope'] for r in rows))),
                       provenance=dict(inputs_sha256=sha((root/'inputs.json').read_bytes()), ledger_sha256=digest(rows), review=ref))
        for name, data in [('results.json', results), ('coverage.json', windows), ('clock_conflicts.json', clocks),
                           ('identity_review.json', dict(candidates=checks, review=review, accepted_bindings_are_reviewed_not_inferred=True))]:
            frozen(destination / name, data)
        frozen(destination / 'validation.json', dict(code_sha256=inputs['code_sha256'], evidence_hashes_verified=len(entries),
                                                    network_used=False, database_used=False, partial_results_preserved=True,
                                                    files={p.name: sha(p.read_bytes()) for p in destination.glob('*.json')}))
        with (destination / 'README.md').open('x') as handle:
            handle.write('# Stage 4 saved offline report\n\nSEC SIC, not GICS. Candidates are not verified securities.\n\n'
                         f"Attempted: {len(rows)}/240. Periodic-complete issuer windows: {sum(w['periodic_complete'] for w in windows)}/{len(windows)}.\n\n"
                         'See coverage.json for all missing accessions and unexamined 8-K intervals; identity_review.json and clock_conflicts.json preserve unresolved evidence.\n'
                         'Synthetic probes are not trades or trading sessions. No production data or strategy changed.\n')
        return dict(status='OFFLINE_REPORT_SAVED', path=str(destination), partial=not all(w['periodic_complete'] for w in windows))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir', type=Path, default=DEFAULT_ROOT)
    modes = parser.add_mutually_exclusive_group()
    for mode in ('prepare', 'plan', 'fetch', 'analyze'): modes.add_argument('--'+mode, action='store_true')
    parser.add_argument('--request-plan', type=Path)
    parser.add_argument('--plan-sha256')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--review-sha256')
    args = parser.parse_args(argv)
    if not any((args.prepare, args.plan, args.fetch, args.analyze)):
        parser.print_help(); return
    if args.prepare: result = prepare(args.package_dir)
    elif args.plan: result = plan_requests(args.package_dir, args.review, args.review_sha256)
    elif args.fetch:
        require(args.request_plan is not None and args.plan_sha256, 'Fetch requires explicit request plan and SHA-256')
        result = fetch(args.package_dir, args.request_plan, args.plan_sha256)
    else: result = analyze(args.package_dir, args.review, args.review_sha256)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
