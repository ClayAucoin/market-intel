"""Apply only the explicitly approved, SHA-pinned SEC acceptance repair.

Default prepares/verifies without writes. --apply opts into one guarded transaction.
No imports, research rebuilds, trading, notifications, or automatic rollback repair.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import time

from psycopg import IsolationLevel, sql
from psycopg.rows import dict_row
from src.database import get_connection
from src.backtesting.acceptance_repair_manifest import OUTPUT, EXPECTED, classify, digest, instant
from src.backtesting.audit_sector_readiness import MEMBERSHIP
from src.analysis.event_timing import get_candidate_entry_date

PIN = 'f8bdc0b837287a2cd3d22a97115de268d1550863d72428b38a407c8ff9afed74'
SAFE = 'safely_correctable'
TOTAL = 31097
TARGET = 29837
PROTECTED = ('companies', 'financial_facts', 'backtest_events', 'paper_accounts',
             'paper_signals', 'paper_positions', 'index_membership_history')


class GuardFailure(Exception):
    """Messages are fixed safe diagnostics, never SQL/credentials/row contents."""


def require(ok, reason):
    if not ok:
        raise GuardFailure(reason)


def durable_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, default=str, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def load_pinned():
    raw = OUTPUT.read_bytes()
    require(digest(raw) == PIN, 'Pinned manifest SHA-256 mismatch')
    require(OUTPUT.with_suffix('.gz.sha256').read_text().split()[0] == PIN, 'Manifest sidecar mismatch')
    manifest = json.loads(gzip.decompress(raw))
    require(manifest['counts'] == EXPECTED, 'Manifest category counts differ')
    require(len(manifest['rows']) == TOTAL, 'Manifest total differs')
    require(len({r['filing_id'] for r in manifest['rows']}) == TOTAL, 'Duplicate filing IDs')
    require(len({r['accession'] for r in manifest['rows']}) == TOTAL, 'Duplicate accessions')
    require(dict(Counter(r['category'] for r in manifest['rows'])) == EXPECTED, 'Manifest row categories differ')
    audit = manifest['audit_file']
    require(digest(Path(audit['path']).read_bytes()) == audit['sha256'], 'Saved source audit hash differs')
    for source, evidence in manifest['source_files'].items():
        data = Path(source).read_bytes()
        require(len(data) == evidence['bytes'] and digest(data) == evidence['sha256'], 'Local source evidence hash differs')
    for row in manifest['rows']:
        category, normalized = classify(instant(row['stored_timestamp']), row['source_evidence'])
        require(category == row['category'], 'Source category differs')
        require(normalized == instant(row['source_normalized_utc']), 'Normalized source differs')
        expected = normalized if category == SAFE else None
        require(instant(row['proposed_timestamp']) == expected, 'Proposed or excluded timestamp differs')
        for source in row['source_evidence']:
            require(source['sha256'] == manifest['source_files'][source['source']]['sha256'], 'Source identity hash differs')
    return manifest


def configure(conn, read_only):
    conn.read_only = read_only
    conn.isolation_level = IsolationLevel.REPEATABLE_READ
    with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout='15s'")
        cur.execute("SET LOCAL lock_timeout='5s'")
        cur.execute("SET LOCAL idle_in_transaction_session_timeout='60s'")
        cur.execute("SET LOCAL timezone='UTC'")
        cur.execute("SET LOCAL datestyle='ISO, YMD'")


def fingerprints(cur):
    result = {}
    for table in PROTECTED:
        # SHA-256 of each complete logical row, then a stable ordered aggregate.
        cur.execute(sql.SQL("SELECT id, encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS hash FROM public.{} t ORDER BY id").format(sql.Identifier(table)))
        aggregate = hashlib.sha256()
        count = 0
        while batch := cur.fetchmany(2000):
            for row in batch:
                aggregate.update(f"{row['id']} {row['hash']}\n".encode())
                count += 1
        result[table] = dict(rows=count, sha256=aggregate.hexdigest())
    return result


def filing_check(manifest, filings, *, after):
    require(len(filings) == TOTAL, 'Live filing count differs')
    by_id = {r['id']: r for r in filings}
    require(len(by_id) == TOTAL, 'Duplicate live filing IDs')
    counts = Counter()
    old_safe_remaining = 0
    for row in manifest['rows']:
        current = by_id.get(row['filing_id'])
        require(current is not None, 'Expected filing ID missing')
        require((current['company_id'], current['cik'], current['accession_number'], current['form'], current['filing_date']) ==
                (row['company_id'], row['cik'], row['accession'], row['form'], row['filing_date']), 'Filing identity or date differs')
        expected = row['proposed_timestamp'] if after and row['category'] == SAFE else row['stored_timestamp']
        actual = instant(current['acceptance_datetime'])
        require(actual == instant(expected), 'Filing acceptance pre/postcondition differs')
        if row['category'] == SAFE and actual == instant(row['stored_timestamp']):
            old_safe_remaining += 1
        counts[row['category']] += 1
    require(dict(counts) == EXPECTED, 'Verified category population differs')
    require(old_safe_remaining == (0 if after else TARGET), 'Erroneous safe timestamp count differs')
    return dict(total=TOTAL, verified_categories=dict(counts), safe_old_remaining=old_safe_remaining,
                safe_corrected=TARGET if after else 0, identities_and_filing_dates_match=True)


def snapshot(conn, manifest, *, after=False):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT current_timestamp AS snapshot,current_setting('transaction_read_only') AS read_only")
        meta = cur.fetchone()
        cur.execute("SELECT count(*) AS n FROM pg_trigger WHERE tgrelid='public.filings'::regclass AND NOT tgisinternal")
        require(cur.fetchone()['n'] == 0, 'Unexpected filing trigger')
        cur.execute("SELECT count(*) AS n FROM pg_rules WHERE schemaname='public' AND tablename='filings'")
        require(cur.fetchone()['n'] == 0, 'Unexpected filing rule')
        cur.execute("SELECT relname,relkind,relrowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace AND relname=ANY(%s)", (['filings', *PROTECTED],))
        tables = cur.fetchall()
        require(len(tables) == len(PROTECTED)+1 and all(r['relkind']=='r' and not r['relrowsecurity'] for r in tables), 'Unexpected table type or row security')
        cur.execute("SELECT to_jsonb(f)::text AS row_json,lpad(c.cik::text,10,'0') AS cik FROM public.filings f LEFT JOIN public.companies c ON c.id=f.company_id ORDER BY f.id")
        full_rows = cur.fetchall()
        filings = [dict(json.loads(r['row_json']), cik=r['cik']) for r in full_rows]
        checked = filing_check(manifest, filings, after=after)
        other_fields = hashlib.sha256()
        for row in filings:
            copy = dict(row)
            del copy['acceptance_datetime']
            other_fields.update((json.dumps(copy, sort_keys=True, separators=(',', ':'))+'\n').encode())
        cur.execute('SELECT id,cash,prospective_cutover_at FROM public.paper_accounts ORDER BY id')
        paper = cur.fetchall()
        require({a['id']: a['prospective_cutover_at'] for a in paper} ==
                {a['id']: instant(a['prospective_cutover_at']) for a in manifest['cutover_preconditions']}, 'Immutable cutover differs')
        cur.execute(sql.SQL('SELECT count(*) AS total,count(*) FILTER (WHERE '+MEMBERSHIP+') AS historical_membership FROM public.backtest_events be'))
        event_counts = cur.fetchone()
        require(event_counts == dict(total=14824, historical_membership=14741), 'Audited backtest counts differ')
        protected = fingerprints(cur)
        cur.execute("SELECT column_name,udt_name,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name='filings' ORDER BY ordinal_position")
        columns = cur.fetchall()
    return dict(metadata=meta, filings=checked, non_acceptance_filing_sha256=other_fields.hexdigest(),
        protected_tables=protected, paper_accounts=paper, backtest_event_counts=event_counts,
        filing_columns=columns), full_rows


def unchanged(before, after):
    for field in ('non_acceptance_filing_sha256', 'protected_tables', 'paper_accounts', 'backtest_event_counts', 'filing_columns'):
        require(before[field] == after[field], 'Protected state changed: '+field)


def save_backup(directory, full_rows, manifest):
    path = directory/'filings_before.jsonl.gz'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as zipped:
            for row in full_rows:
                zipped.write((row['row_json']+'\n').encode())
        raw.flush()
        os.fsync(raw.fileno())
    with gzip.open(path, 'rt') as stream:
        restored = [json.loads(line) for line in stream]
    expected = [json.loads(row['row_json']) for row in full_rows]
    require(restored == expected and len(restored) == TOTAL, 'Backup restore/read-back mismatch')
    require({r['id']: instant(r['acceptance_datetime']) for r in restored} ==
            {r['filing_id']: instant(r['stored_timestamp']) for r in manifest['rows']}, 'Backup before-images differ')
    return dict(path=str(path), sha256=digest(path.read_bytes()), rows=len(restored),
                mode='0600', scope='complete public.filings rows; schema metadata in receipt',
                read_back_verified=True)


def update_safe(cur, manifest):
    safe = [r for r in manifest['rows'] if r['category'] == SAFE]
    require(len(safe) == TARGET, 'Safe update population differs')
    parameters = ([r['filing_id'] for r in safe], [r['company_id'] for r in safe],
                  [r['cik'] for r in safe], [r['accession'] for r in safe],
                  [instant(r['stored_timestamp']) for r in safe],
                  [instant(r['proposed_timestamp']) for r in safe], [r['filing_date'] for r in safe])
    cur.execute("""WITH correction AS (
        SELECT * FROM unnest(%s::bigint[],%s::bigint[],%s::text[],%s::text[],
                             %s::timestamptz[],%s::timestamptz[],%s::date[])
        AS x(id,company_id,cik,accession,old_stamp,new_stamp,filing_date))
        UPDATE public.filings f SET acceptance_datetime=x.new_stamp
        FROM correction x JOIN public.companies c ON c.id=x.company_id
        WHERE f.id=x.id AND f.company_id=x.company_id
          AND lpad(c.cik::text,10,'0')=x.cik AND f.accession_number=x.accession
          AND f.filing_date=x.filing_date AND f.acceptance_datetime=x.old_stamp
        RETURNING f.id""", parameters)
    updated = [row['id'] for row in cur.fetchall()]
    require(cur.rowcount == TARGET and len(updated) == TARGET and set(updated) == {r['filing_id'] for r in safe}, 'Updated row count or identity mismatch')
    return len(updated)


def correction_statistics(manifest):
    safe = [r for r in manifest['rows'] if r['category'] == SAFE]
    utc_changes = 0
    candidates = 0
    for row in safe:
        old, new = instant(row['stored_timestamp']), instant(row['proposed_timestamp'])
        utc_changes += old.date() != new.date()
        candidates += get_candidate_entry_date(dict(acceptance_datetime=old)) != get_candidate_entry_date(dict(acceptance_datetime=new))
    return dict(database_minus_source_seconds=dict(Counter(str(r['database_minus_source_seconds']) for r in safe)),
                utc_calendar_date_changes=utc_changes, calendar_candidate_date_changes=candidates,
                event_rows_rebuilt=0)


def run(apply=False):
    started = time.monotonic()
    manifest = load_pinned()
    directory = OUTPUT.parent / ('execution_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    directory.mkdir(mode=0o700)
    receipt_path = directory/'receipt.json'
    receipt = dict(manifest_sha256=PIN, manifest_path=str(OUTPUT),
        runner_sha256=digest(Path(__file__).read_bytes()), started_at=datetime.now(timezone.utc),
        apply_requested=apply, execution_state='PREPARING', counts=EXPECTED,
        correction_statistics=correction_statistics(manifest))
    durable_json(receipt_path, receipt)
    try:
        with get_connection() as conn:
            configure(conn, True)
            before, full_rows = snapshot(conn, manifest)
        receipt['before'] = before
        receipt['backup'] = save_backup(directory, full_rows, manifest)
        del full_rows
        receipt['execution_state'] = 'PREPARED'
        durable_json(receipt_path, receipt)
        if not apply:
            print(receipt_path)
            return receipt_path
        with get_connection() as conn:
            configure(conn, False)
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute('LOCK TABLE public.filings IN SHARE ROW EXCLUSIVE MODE')
                cur.execute(sql.SQL('LOCK TABLE {} IN SHARE MODE').format(sql.SQL(',').join(sql.Identifier('public', t) for t in PROTECTED)))
                locked, _ = snapshot(conn, manifest)
                unchanged(before, locked)
                require(locked['filings'] == before['filings'], 'Locked filing preconditions changed')
                cur.execute('SELECT txid_current() AS transaction_id,clock_timestamp() AS execution_time')
                receipt['transaction'] = cur.fetchone()
                receipt['execution_state'] = 'TRANSACTION_IN_PROGRESS'
                durable_json(receipt_path, receipt)
                receipt['updates'] = update_safe(cur, manifest)
                after, _ = snapshot(conn, manifest, after=True)
                unchanged(before, after)
                receipt['inside_transaction_after'] = after
                receipt['execution_state'] = 'VERIFIED_PENDING_COMMIT'
                durable_json(receipt_path, receipt)
            # Connection context commits only after every guard and durable write.
        receipt['execution_state'] = 'COMMITTED'
        receipt['commit_acknowledged_at'] = datetime.now(timezone.utc)
        durable_json(receipt_path, receipt)
        with get_connection() as conn:
            configure(conn, True)
            post, _ = snapshot(conn, manifest, after=True)
        unchanged(before, post)
        receipt['read_only_post_commit'] = post
        receipt['execution_state'] = 'COMMITTED_AND_VERIFIED'
        receipt['elapsed_seconds'] = round(time.monotonic()-started, 3)
        durable_json(receipt_path, receipt)
        print(receipt_path)
        print(json.dumps(dict(state=receipt['execution_state'], updates=receipt['updates'],
                              statistics=receipt['correction_statistics']), indent=2))
        return receipt_path
    except Exception as error:
        previous = receipt['execution_state']
        receipt['failure'] = dict(type=type(error).__name__, guard=str(error) if isinstance(error, GuardFailure) else 'Raw diagnostics suppressed',
            previous_state=previous, occurred_at=datetime.now(timezone.utc))
        # If commit acknowledgement failed, do not claim rollback or retry writes.
        receipt['execution_state'] = ('POST_COMMIT_VERIFICATION_FAILED' if previous == 'COMMITTED' else
            'COMMIT_OUTCOME_REQUIRES_READ_ONLY_CHECK' if previous == 'VERIFIED_PENDING_COMMIT' else 'ABORTED_NO_COMMIT')
        durable_json(receipt_path, receipt)
        print(receipt_path)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        run(args.apply)
    except Exception as error:
        detail = str(error) if isinstance(error, GuardFailure) else type(error).__name__
        raise SystemExit('Repair stopped: '+detail+'. Inspect receipt; do not retry writes without checking state.') from None
