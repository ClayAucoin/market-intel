"""One pinned filing/event correction. Default is database read-only dry-run.

Capture/prepare/replay never write the database. Apply and rollback require an
explicit manifest hash and independent operator authorization.
"""
import argparse
from contextlib import ExitStack
from datetime import date, datetime, timezone
from decimal import Decimal
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from psycopg import IsolationLevel, sql
from psycopg.rows import dict_row
from src.database import get_connection
from src.backtesting.apply_acceptance_repair import durable_json

ROOT = Path('logs/research/ttwo_acceptance_correction_2026-09-25')
ACCESSION = '0001628280-25-026694'
OLD = '2025-05-20 14:32:02+00:00'
NEW = '2025-05-20 10:32:02+00:00'
EVENT_ID = 413248
PERIOD = '2025-03-31'
HEADER = Path('logs/research/sec_acceptance_source_discrepancy_2026-09-24/header/0000946581_0001628280-25-026694.json')
SOURCE = Path('logs/research/sec_acceptance_source_discrepancy_2026-09-24/submissions/CIK0000946581.json')
CODE = (
    'src/backtesting/ttwo_acceptance_correction.py',
    'src/backtesting/build_backtest_events.py', 'src/backtesting/backtester.py',
    'src/backtesting/investigate_event_provenance.py',
    'src/backtesting/investigate_acceptance_sources.py',
    'src/backtesting/apply_acceptance_repair.py',
    'src/analysis/event_timing.py', 'src/analysis/market_context.py',
    'src/analysis/experimental_signal.py', 'src/sec/acceptance_time.py',
)
# Table locks, not advisory locks: also exclude phantom inserts and rebuilds.
# Sorted single lock statement; short timeout aborts if any writer is active.
TABLES = tuple(sorted(('filings', 'backtest_events', 'financial_facts',
    'daily_prices', 'index_membership_history', 'securities', 'companies',
    'filing_exhibits', 'paper_signals', 'paper_positions')))
FINANCIAL = ('revenue_yoy', 'revenue_acceleration', 'eps_yoy',
             'gross_margin_change', 'operating_margin_change')


class GuardFailure(Exception):
    pass


def require(ok, message):
    if not ok:
        raise GuardFailure(message)


def normalized(value):
    return json.loads(json.dumps(value, default=str))


def digest(value):
    return hashlib.sha256(json.dumps(normalized(value), sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def configure(conn, write=False):
    conn.read_only = not write
    # Writers lock first, then read under READ COMMITTED to see writers that
    # committed before the lock was acquired. Locks hold inputs stable thereafter.
    conn.isolation_level = IsolationLevel.READ_COMMITTED if write else IsolationLevel.REPEATABLE_READ
    with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout='15s'")
        cur.execute("SET LOCAL lock_timeout='3s'")
        cur.execute("SET LOCAL idle_in_transaction_session_timeout='60s'")
        cur.execute("SET LOCAL timezone='UTC'")
        cur.execute("SET LOCAL datestyle='ISO, YMD'")
        if write:
            cur.execute(sql.SQL('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE').format(
                sql.SQL(',').join(sql.Identifier('public', t) for t in TABLES)))


def snapshot(conn):
    """Bounded target/comparator snapshot; never scans another security's facts."""
    with conn.cursor(row_factory=dict_row) as cur:
        def rows(query, params=()):
            cur.execute(query, params)
            return normalized(cur.fetchall())
        state = {}
        state['filings'] = rows('SELECT f.*,xmin::text AS row_version FROM filings f WHERE id=108402 OR accession_number=%s ORDER BY id', (ACCESSION,))
        state['events'] = rows('SELECT e.*,xmin::text AS row_version FROM backtest_events e WHERE id=ANY(%s) OR (security_id=358 AND period_end=%s) ORDER BY id', ([398505, EVENT_ID], PERIOD))
        state['linked_facts'] = rows('SELECT f.*,xmin::text AS row_version FROM financial_facts f WHERE accession_number=%s ORDER BY id', (ACCESSION,))
        state['facts'] = rows("SELECT f.*,xmin::text AS row_version FROM financial_facts f WHERE security_id=358 AND period_end<=%s AND metric IN ('revenue','diluted_eps','gross_profit','operating_income') ORDER BY metric,period_end,id", (PERIOD,))
        # This finite superset supplies >61 prior closes and every requested exit.
        # Completeness is checked by calculate(), not by assuming missing = zero.
        state['prices'] = rows("SELECT symbol,trade_date,adjusted_open,adjusted_close,xmin::text AS row_version FROM daily_prices WHERE UPPER(symbol) IN ('TTWO','SPY') AND trade_date BETWEEN '2024-12-01' AND '2025-11-30' ORDER BY symbol,trade_date")
        state['membership'] = rows("SELECT i.*,xmin::text AS row_version FROM index_membership_history i WHERE security_id=358 AND index_name='S&P 500' ORDER BY id")
        state['security'] = rows('SELECT id,ticker,xmin::text AS row_version FROM securities WHERE id=358')
        state['company'] = rows('SELECT id,cik,ticker,xmin::text AS row_version FROM companies WHERE id=362')
        state['exhibits'] = rows('SELECT id,filing_id,xmin::text AS row_version FROM filing_exhibits WHERE filing_id=108402 ORDER BY id')
        state['signals'] = rows('SELECT id,security_id,backtest_event_id,period_end,signal_date,xmin::text AS row_version FROM paper_signals WHERE backtest_event_id=ANY(%s) OR (security_id=358 AND period_end=%s) ORDER BY id', ([398505, EVENT_ID], PERIOD))
        state['positions'] = rows('SELECT id,signal_id,xmin::text AS row_version FROM paper_positions WHERE signal_id=ANY(%s) ORDER BY id', ([s['id'] for s in state['signals']],))
        state['foreign_keys'] = rows("SELECT conrelid::regclass::text AS relation,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE contype='f' AND confrelid IN ('filings'::regclass,'financial_facts'::regclass,'backtest_events'::regclass,'paper_signals'::regclass) ORDER BY 1,2")
    return state


def check_target(state):
    require(len(state['filings']) == len(state['events']) == 1, 'Target missing, duplicated or replaced')
    f, e = state['filings'][0], state['events'][0]
    require((f['id'], f['company_id'], f['accession_number'], f['form'], f['filing_date']) ==
            (108402, 362, ACCESSION, '10-K', '2025-05-20'), 'Filing identity drift')
    require((e['id'], e['security_id'], e['period_end']) == (EVENT_ID, 358, PERIOD), 'Replacement event ID: stop; never retarget')
    require({r['id'] for r in state['linked_facts']} == {547980, 548242}, 'Accession dependency set changed')
    require(all(r['security_id'] == 358 and r['company_id'] == 362 and r['period_end'] == PERIOD for r in state['linked_facts']), 'Fact identity drift')
    require(len(state['security']) == len(state['company']) == 1 and state['security'][0]['ticker'] == 'TTWO' and str(state['company'][0]['cik']).zfill(10) == '0000946581', 'Issuer/security identity drift')
    require(not state['signals'] and not state['positions'] and not state['exhibits'], 'New downstream references require review')
    require(state['foreign_keys'] == [
        dict(relation='filing_exhibits', definition='FOREIGN KEY (filing_id) REFERENCES filings(id) ON DELETE CASCADE'),
        dict(relation='paper_positions', definition='FOREIGN KEY (signal_id) REFERENCES paper_signals(id) ON DELETE RESTRICT'),
        dict(relation='paper_signals', definition='FOREIGN KEY (backtest_event_id) REFERENCES backtest_events(id) ON DELETE SET NULL'),
    ], 'Unreviewed dependency schema')


def calculate(state, stamp):
    """Exactly one event through existing pure helpers; no builder loop or save."""
    from src.backtesting import build_backtest_events as b, backtester as bt
    from src.analysis import event_timing as et, market_context as mc
    from src.analysis.experimental_signal import qualifies_experimental_signal
    from src.backtesting.investigate_event_provenance import PriceIndex
    check_target(state)
    histories = {}
    for original in state['facts']:
        f = dict(original)
        for key in ('period_start', 'period_end', 'filed_date'):
            if f.get(key):
                f[key] = date.fromisoformat(f[key])
        f['value'] = Decimal(f['value'])
        histories.setdefault(f['metric'], []).append(f)
    for history in histories.values():
        require(len({r['period_end'] for r in history}) == len(history), 'Ambiguous fact order')
    revenue = next((r for r in histories.get('revenue', []) if r['id'] == 547980), None)
    require(revenue is not None and b.is_current_reporting_event(revenue), 'Current revenue dependency missing')
    prices = PriceIndex([(p['symbol'], date.fromisoformat(p['trade_date']),
                         Decimal(p['adjusted_open']) if p['adjusted_open'] is not None else None,
                         Decimal(p['adjusted_close']) if p['adjusted_close'] is not None else None)
                        for p in state['prices']])
    with ExitStack() as stack:
        for module in (b, bt, et, mc):
            stack.enter_context(patch.object(module, 'get_connection', side_effect=GuardFailure('Offline DB call forbidden')))
        stack.enter_context(patch('psycopg.connect', side_effect=GuardFailure('Offline DB call forbidden')))
        stack.enter_context(patch('requests.sessions.Session.request', side_effect=GuardFailure('Network forbidden')))
        for module, name, fn in ((et, 'get_next_trading_date', prices.next_date),
                                (bt, 'get_price_on_date', prices.on), (bt, 'get_price_on_or_after', prices.after),
                                (mc, 'get_prior_prices', prices.prior), (mc, 'get_entry_price_record', prices.entry)):
            stack.enter_context(patch.object(module, name, fn))
        entry = et.get_event_entry_date('TTWO', dict(acceptance_datetime=datetime.fromisoformat(stamp), filed_date=date(2025, 5, 20)))
        require(entry is not None, 'No entry session')
        require(any(r['effective_from'] and date.fromisoformat(r['effective_from']) <= entry and
                    (r['effective_to'] is None or entry <= date.fromisoformat(r['effective_to'])) for r in state['membership']), 'Membership missing')
        for symbol in ('TTWO', 'SPY'):
            require(len(prices.prior(symbol, entry, 61)) == 61, 'Insufficient prior sessions')
        stock = bt.backtest_from_entry_date('TTWO', entry)
        spy = bt.backtest_from_entry_date('SPY', entry)
        require(stock is not None and spy is not None, 'Missing adjusted entry open')
        require(all(stock['horizons'][h] and spy['horizons'][h] for h in b.HORIZONS), 'Missing exit dependency')
        eps = b.get_period_record(histories.get('diluted_eps', []), revenue['period_end'])
        row = dict(security_id=358, period_end=revenue['period_end'], entry_date=entry, entry_price=stock['entry_price'],
                   revenue_yoy=b.get_yoy_growth(histories['revenue'], revenue),
                   revenue_acceleration=b.get_growth_acceleration(histories['revenue'], revenue),
                   eps_yoy=b.get_yoy_growth(histories.get('diluted_eps', []), eps) if eps else None,
                   gross_margin_change=b.get_margin_change(histories.get('gross_profit', []), histories['revenue'], revenue['period_end']),
                   operating_margin_change=b.get_margin_change(histories.get('operating_income', []), histories['revenue'], revenue['period_end']))
        row.update(mc.calculate_market_context('TTWO', entry, benchmark='SPY'))
        for h in b.HORIZONS:
            result = b.get_horizon_result(stock, spy, h)
            row.update({f'exit_date_{h}': result['exit_date'], f'return_{h}': result['return'],
                        f'spy_return_{h}': result['benchmark_return'], f'excess_{h}': result['excess_return']})
        return normalized(dict(fields=row, exact_signal=qualifies_experimental_signal(row), stock=stock, benchmark=spy))


def verify_baseline(state, baseline):
    actual = state['events'][0]
    differences = {}
    for key, value in baseline['fields'].items():
        old = actual[key]
        if value == old:
            continue
        try:
            equal = value is not None and old is not None and Decimal(str(value)) == Decimal(str(old))
        except Exception:
            equal = False
        if not equal:
            differences[key] = [old, value]
    require(len(baseline['fields']) == 31 and not differences, 'Baseline reproduction failed: ' + ','.join(differences))


def capture():
    require(not (ROOT / 'inputs.json').exists(), 'Capture already frozen')
    with get_connection() as conn:
        configure(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT current_timestamp AS captured_at,current_setting('transaction_read_only') AS read_only")
            meta = normalized(cur.fetchone())
        require(meta['read_only'] == 'on', 'Read-only transaction required')
        state = snapshot(conn)
    check_target(state)
    require(state['filings'][0]['acceptance_datetime'] == OLD, 'Reviewed old acceptance changed')
    baseline = calculate(state, OLD)
    verify_baseline(state, baseline)
    ROOT.mkdir(parents=True, exist_ok=True)
    durable_json(ROOT / 'inputs.json', dict(metadata=meta, state=state))
    print('Captured target and dependencies; all 31 baseline fields reproduced.')


def prepare():
    require(not (ROOT / 'manifest.json').exists(), 'Manifest already frozen')
    inputs = read(ROOT / 'inputs.json')
    state = inputs['state']
    require(state['filings'][0]['acceptance_datetime'] == OLD, 'Unexpected old timestamp')
    baseline, alternative = calculate(state, OLD), calculate(state, NEW)
    verify_baseline(state, baseline)
    require(all(baseline['fields'][k] == alternative['fields'][k] for k in FINANCIAL), 'Financial metrics changed')
    from src.sec.acceptance_time import parse_header_acceptance, parse_submissions_acceptance
    header, source = read(HEADER), read(SOURCE)
    require(hashlib.sha256(header['raw_header'].encode()).hexdigest() == header['sha256'], 'Header hash mismatch')
    require(hashlib.sha256(source['raw_json'].encode()).hexdigest() == source['sha256'], 'Submissions hash mismatch')
    from src.backtesting.investigate_acceptance_sources import header_fields, row_for
    h = header_fields(header['raw_header'], '0000946581', ACCESSION)
    s = row_for(json.loads(source['raw_json']), ACCESSION)
    require(parse_header_acceptance(h['raw_acceptance']) == parse_submissions_acceptance(s['acceptanceDateTime']) == datetime.fromisoformat(NEW), 'Independent source disagreement')
    comparison = dict(baseline=baseline, alternative=alternative,
                      changed_fields={k: dict(old=baseline['fields'][k], new=v) for k, v in alternative['fields'].items() if baseline['fields'][k] != v})
    durable_json(ROOT / 'comparison.json', comparison)
    durable_json(ROOT / 'before_images.json', dict(filing=state['filings'][0], event=state['events'][0]))
    manifest = dict(version=1, accession=ACCESSION, filing_id=108402, company_id=362,
                    event_id=EVENT_ID, security_id=358, period_end=PERIOD, old=OLD, new=NEW,
                    state_sha256=digest(state), files={str(p): file_hash(p) for p in
                    (ROOT/'inputs.json', ROOT/'comparison.json', ROOT/'before_images.json', HEADER, SOURCE)},
                    code_sha256={p: file_hash(p) for p in CODE},
                    event_changes={k: v['new'] for k, v in comparison['changed_fields'].items()})
    durable_json(ROOT / 'manifest.json', manifest)
    (ROOT / 'manifest.sha256').write_text(file_hash(ROOT / 'manifest.json') + '\n')
    print('Prepared pinned manifest; no database writes.')


def load_package(pin=None):
    actual = file_hash(ROOT / 'manifest.json')
    require(actual == (ROOT / 'manifest.sha256').read_text().strip(), 'Manifest sidecar mismatch')
    if pin is not None:
        require(actual == pin, 'Explicit manifest pin mismatch')
    m = read(ROOT / 'manifest.json')
    require((m['version'], m['accession'], m['filing_id'], m['company_id'], m['event_id'], m['security_id'], m['period_end'], m['old'], m['new']) ==
            (1, ACCESSION, 108402, 362, EVENT_ID, 358, PERIOD, OLD, NEW), 'Manifest scope mismatch')
    for path, expected in {**m['files'], **m['code_sha256']}.items():
        require(file_hash(path) == expected, 'Pinned file/code changed: ' + path)
    state = read(ROOT / 'inputs.json')['state']
    require(digest(state) == m['state_sha256'], 'Input state hash mismatch')
    baseline, alternative = calculate(state, OLD), calculate(state, NEW)
    verify_baseline(state, baseline)
    require(read(ROOT/'comparison.json')['baseline'] == baseline and read(ROOT/'comparison.json')['alternative'] == alternative, 'Offline comparison changed')
    changes = {k: v for k, v in alternative['fields'].items() if v != baseline['fields'][k]}
    require(changes == m['event_changes'] and not set(changes).intersection(FINANCIAL), 'Replacement fields changed')
    require(read(ROOT/'before_images.json') == dict(filing=state['filings'][0], event=state['events'][0]), 'Before-images mismatch')
    return m, state


def revalidate(current, expected):
    check_target(current)
    require(current == expected, 'Reviewed rows/dependencies changed; abort without retargeting')


def mutate(conn, manifest, expected, reverse=False):
    """Called only after locks/revalidation. No commit; enclosing context owns it."""
    changes = manifest['event_changes']
    values = {k: expected['events'][0][k] for k in changes} if reverse else changes
    with conn.cursor() as cur:
        cur.execute('UPDATE filings SET acceptance_datetime=%s WHERE id=108402 AND company_id=362 AND accession_number=%s AND acceptance_datetime=%s',
                    (OLD if reverse else NEW, ACCESSION, NEW if reverse else OLD))
        require(cur.rowcount == 1, 'Filing update count mismatch')
        assignments = [sql.SQL('{}=%s').format(sql.Identifier(k)) for k in sorted(values)]
        # Rollback restores the old event timestamp; apply records transaction time.
        assignments.append(sql.SQL('updated_at=%s') if reverse else sql.SQL('updated_at=CURRENT_TIMESTAMP'))
        params = [values[k] for k in sorted(values)]
        if reverse:
            params.append(expected['events'][0]['updated_at'])
        params += [EVENT_ID, 358, PERIOD]
        cur.execute(sql.SQL('UPDATE backtest_events SET {} WHERE id=%s AND security_id=%s AND period_end=%s').format(sql.SQL(',').join(assignments)), params)
        require(cur.rowcount == 1, 'Event update count mismatch')


def verify_after(before, after, manifest, reverse=False, original=None):
    expected = copy.deepcopy(original if reverse else before)
    if not reverse:
        expected['filings'][0]['acceptance_datetime'] = NEW
        expected['events'][0].update(manifest['event_changes'])
        expected['events'][0]['updated_at'] = after['events'][0]['updated_at']
    # Updated rows acquire new MVCC versions; all other versions must be unchanged.
    for key in ('filings', 'events'):
        expected[key][0]['row_version'] = after[key][0]['row_version']
    require(after == expected, 'Post-update verification failed')


def execute(mode, pin, receipt_path=None):
    m, original = load_package(pin)
    require(pin is not None, 'Explicit --manifest-sha256 required for writes')
    require(mode in ('apply', 'rollback'), 'Invalid write mode')
    if mode == 'rollback':
        require(receipt_path is not None, 'Apply receipt required')
        receipt = read(receipt_path)
        require(receipt['mode'] == 'apply' and receipt['status'] == 'COMMITTED_VERIFIED' and receipt['manifest_sha256'] == pin, 'Invalid apply receipt')
        expected = receipt['after']
        require(digest(expected) == receipt['after_sha256'], 'Receipt hash mismatch')
        verify_after(original, expected, m)
    else:
        expected = original
    directory = ROOT / 'executions' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / 'receipt.json'
    receipt = dict(mode=mode, manifest_sha256=pin, status='PREPARED', before=expected)
    durable_json(path, receipt)
    # An exception at COMMIT may be indeterminate: never claim rollback succeeded.
    try:
        with get_connection() as conn:
            configure(conn, write=True)
            revalidate(snapshot(conn), expected)
            mutate(conn, m, original, reverse=mode == 'rollback')
            after = snapshot(conn)
            verify_after(expected, after, m, reverse=mode == 'rollback', original=original)
            receipt.update(status='VERIFIED_PENDING_COMMIT', after=after, after_sha256=digest(after))
            durable_json(path, receipt)
        receipt['status'] = 'COMMITTED'
        durable_json(path, receipt)
        with get_connection() as conn:
            configure(conn)
            revalidate(snapshot(conn), after)
        receipt['status'] = 'COMMITTED_VERIFIED'
        durable_json(path, receipt)
    except Exception:
        receipt['status'] = 'FAILED_OR_COMMIT_STATE_UNCERTAIN'
        durable_json(path, receipt)
        raise GuardFailure('Operation failed; reconcile receipt/current state before any retry') from None
    print(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    for name in ('capture', 'prepare', 'offline', 'apply', 'rollback'):
        group.add_argument('--' + name, action='store_true')
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.capture:
        capture()
    elif args.prepare:
        prepare()
    elif args.apply or args.rollback:
        execute('apply' if args.apply else 'rollback', args.manifest_sha256, args.receipt)
    else:
        _, state = load_package(args.manifest_sha256)
        if not args.offline:
            with get_connection() as conn:
                configure(conn)
                revalidate(snapshot(conn), state)
        print('OFFLINE_VERIFIED' if args.offline else 'DRY_RUN_READY; no database writes')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never expose connection details or SQL parameter dumps.
        print(str(error) if isinstance(error, GuardFailure) else type(error).__name__)
        raise SystemExit(1)
