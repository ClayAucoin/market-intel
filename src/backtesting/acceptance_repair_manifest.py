"""Offline SEC timestamp repair manifest and optional READ-ONLY DB preflight.

No application mode exists. This tool cannot update filings or rebuild events.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from src.sec.acceptance_time import parse_submissions_acceptance
from src.backtesting.audit_acceptance_timezone import legacy_parse_acceptance_datetime
from src.backtesting.audit_sector_readiness import MEMBERSHIP

AUDIT = Path('logs/research/acceptance_timezone_2026-09-23_131057.json.gz')
OUTPUT = Path('logs/research/acceptance_repair/manifest.json.gz')
CACHE = Path('data/cache/sec/submissions')
EXPECTED = dict(safely_correctable=29837, already_correct=984,
                exceptional_offset=71, unresolved_source=205)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def instant(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Naive saved audit instant')
    return parsed.astimezone(timezone.utc)


def classify(old, sources):
    """Only a single source instant reproducing the known bug is auto-proposed."""
    stamps = {parse_submissions_acceptance(e['raw']) for e in sources}
    if not sources or None in stamps or len(stamps) != 1:
        return 'unresolved_source', None
    corrected = stamps.pop()
    if old == corrected:
        return 'already_correct', corrected
    if old is not None and (old - corrected).total_seconds() in (14400, 18000) and all(
            legacy_parse_acceptance_datetime(e['raw']) == old for e in sources):
        return 'safely_correctable', corrected
    return 'exceptional_offset', corrected


def validate_local_sources(filings):
    """Verify every audit source against its current file, keyed by CIK/accession.

    Hash/read each cited cache file once. A changed/missing source aborts manifest
    generation; it is not silently replaced by another source or guessed value.
    """
    grouped = defaultdict(list)
    for row in filings:
        for evidence in row['evidence']:
            path = Path(evidence['source'])
            if path.parent != CACHE or path.suffix != '.json':
                raise ValueError('Non-submissions evidence requires separate review')
            grouped[path].append((row, evidence))
    if len(grouped) > 2000 or sum(p.stat().st_size for p in grouped) > 700_000_000:
        raise ValueError('Local evidence size bound exceeded')
    identities = {}
    for path, wanted in sorted(grouped.items()):
        data = path.read_bytes()
        payload = json.loads(data)
        cik = path.name[3:13]
        if not path.name.startswith('CIK') or not cik.isdigit():
            raise ValueError('Invalid source filename identity')
        if 'cik' in payload and str(payload['cik']).zfill(10) != cik:
            raise ValueError('Cache envelope CIK mismatch')
        columns = payload.get('filings', {}).get('recent', payload)
        index = defaultdict(list)
        accessions = columns['accessionNumber']
        for key in ('acceptanceDateTime', 'filingDate'):
            if len(columns[key]) != len(accessions):
                raise ValueError('Invalid source column lengths')
        for i, accession in enumerate(accessions):
            index[accession].append(i)
        for row, evidence in wanted:
            if str(row['cik']).zfill(10) != cik:
                raise ValueError('Audit/source CIK mismatch')
            matches = index.get(row['accession_number'], [])
            if not matches or any(columns['acceptanceDateTime'][i] != evidence['raw'] or
                                  columns['filingDate'][i] != evidence['filing_date'] for i in matches):
                raise ValueError('Audit/source accession evidence mismatch')
            parsed = parse_submissions_acceptance(evidence['raw'])
            if parsed != instant(evidence['accepted']) or evidence['filing_date'] != row['filing_date']:
                raise ValueError('Source timestamp or filing date differs from audit')
        identities[str(path)] = dict(sha256=digest(data), bytes=len(data))
    return identities


def build(audit, source_hashes):
    rows = []
    seen = set()
    for filing in audit['filings']:
        if filing['id'] in seen:
            raise ValueError('Duplicate filing ID')
        seen.add(filing['id'])
        sources = [dict(e, sha256=source_hashes[e['source']]['sha256']) for e in filing['evidence']]
        old = instant(filing['acceptance_datetime'])
        category, corrected = classify(old, sources)
        if corrected != instant(filing.get('corrected_acceptance')):
            raise ValueError('Normalization disagrees with audit')
        expected_status = {'safely_correctable': 'DIFFERENT', 'already_correct': 'MATCH',
                           'exceptional_offset': 'DIFFERENT', 'unresolved_source': 'NO_EXPLICIT_CACHED_EVIDENCE'}[category]
        if filing['status'] != expected_status:
            raise ValueError('Classification disagrees with audit')
        rows.append(dict(filing_id=filing['id'], company_id=filing['company_id'],
            cik=str(filing['cik']).zfill(10), ticker_label=filing['ticker'],
            accession=filing['accession_number'], form=filing['form'], filing_date=filing['filing_date'],
            stored_timestamp=old, source_evidence=sources, source_normalized_utc=corrected,
            proposed_timestamp=corrected if category == 'safely_correctable' else None,
            database_minus_source_seconds=(old-corrected).total_seconds() if old and corrected else None,
            category=category))
    counts = dict(Counter(r['category'] for r in rows))
    if counts != EXPECTED or len(rows) != audit['summary']['filings']:
        raise ValueError('Manifest population differs from approved audit; STOP')
    offsets = Counter(str(r['database_minus_source_seconds']/3600) for r in rows if r['database_minus_source_seconds'] is not None)
    if dict(offsets) != audit['summary']['offset_hours']:
        raise ValueError('Offset distribution differs from audit; STOP')
    return dict(version=1, created_at=datetime.now(timezone.utc), mode='PROPOSAL_ONLY',
        audit_snapshot=audit['metadata'], counts=counts, offset_hours=dict(offsets),
        reconciles_with_audit=True, source_files=source_hashes,
        cutover_preconditions=[dict(id=a['id'], prospective_cutover_at=a['prospective_cutover_at']) for a in audit['paper']['accounts']],
        rows=rows)


def verify_database(manifest):
    """Compare every row/identity and cutover against current DB without writing."""
    from psycopg import IsolationLevel
    from psycopg.rows import dict_row
    from src.database import get_connection

    with get_connection() as conn:
        conn.read_only = True
        conn.isolation_level = IsolationLevel.REPEATABLE_READ
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SELECT current_timestamp AS snapshot,current_setting('transaction_read_only') AS read_only")
            meta = cur.fetchone()
            cur.execute('SELECT f.id,f.company_id,c.cik,f.accession_number,f.acceptance_datetime,f.filing_date FROM filings f LEFT JOIN companies c ON c.id=f.company_id ORDER BY f.id')
            live = {r['id']: r for r in cur.fetchall()}
            changed = []
            for row in manifest['rows']:
                current = live.get(row['filing_id'])
                if current is None or (current['company_id'], str(current['cik']).zfill(10), current['accession_number'],
                        current['acceptance_datetime'], str(current['filing_date'])) != (
                        row['company_id'], row['cik'], row['accession'], instant(row['stored_timestamp']), row['filing_date']):
                    changed.append(row['filing_id'])
            extra = sorted(set(live) - {r['filing_id'] for r in manifest['rows']})
            cur.execute('SELECT id,prospective_cutover_at FROM paper_accounts ORDER BY id')
            accounts = cur.fetchall()
            cutover_matches = {a['id']: a['prospective_cutover_at'] for a in accounts} == {
                a['id']: instant(a['prospective_cutover_at']) for a in manifest['cutover_preconditions']}
            cur.execute(f'SELECT count(*) AS total, count(*) FILTER (WHERE {MEMBERSHIP}) AS historical_membership FROM backtest_events be')
            event_counts = cur.fetchone()
    return dict(metadata=meta, live_filings=len(live), changed_or_missing_filing_ids=changed,
        extra_filing_ids=extra, cutover_matches=cutover_matches, backtest_event_counts=event_counts,
        passed=not changed and not extra and cutover_matches)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-db', action='store_true', help='Read-only verification of existing manifest')
    args = parser.parse_args()
    if args.verify_db:
        raw = OUTPUT.read_bytes()
        expected = OUTPUT.with_suffix(OUTPUT.suffix + '.sha256').read_text().split()[0]
        if digest(raw) != expected:
            raise ValueError('Manifest hash mismatch')
        manifest = json.loads(gzip.decompress(raw))
        result = verify_database(manifest)
        result['manifest_sha256'] = digest(raw)
        path = OUTPUT.parent / f"preflight_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        with path.open('x') as output:
            json.dump(result, output, default=str, indent=2)
        print(path)
        print(json.dumps(result, default=str, indent=2))
        if not result['passed']:
            raise ValueError('Live DB differs from manifest; STOP before repair')
        return
    raw = AUDIT.read_bytes()
    audit = json.loads(gzip.decompress(raw))
    hashes = validate_local_sources(audit['filings'])
    manifest = build(audit, hashes)
    manifest['audit_file'] = dict(path=str(AUDIT), sha256=digest(raw))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    data = gzip.compress(json.dumps(manifest, default=str, separators=(',', ':')).encode(), mtime=0)
    with OUTPUT.open('xb') as output:
        output.write(data)
    with OUTPUT.with_suffix(OUTPUT.suffix + '.sha256').open('x') as output:
        output.write(digest(data)+'  '+OUTPUT.name+'\n')
    print(OUTPUT)
    print(json.dumps(manifest['counts'], indent=2))
    print(f'Verified {len(hashes)} local source files. No database connection or writes.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(f'Manifest operation failed ({type(error).__name__}); raw diagnostics suppressed. No repair executed.') from None
