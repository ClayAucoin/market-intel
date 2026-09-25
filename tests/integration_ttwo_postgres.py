"""Explicit opt-in real PostgreSQL test; creates its own disposable cluster.

Run from repository root with --run. Never connects using production settings.
Only the correction's connection factory and artifact root are redirected;
snapshot, SQL, locks, transactions, calculations and receipts run unchanged.
"""
import argparse
from contextlib import redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from src.backtesting import ttwo_acceptance_correction as tool

ARTIFACTS = Path('logs/research/ttwo_acceptance_pg_integration_2026-09-25')
BIN = Path('/usr/lib/postgresql/18/bin')
FIXTURES = tool.ROOT / 'inputs.json'


def business(state):
    result = copy.deepcopy(state)
    for rows in result.values():
        for row in rows:
            row.pop('row_version', None)
    return result


def install(conn, schema, fixture):
    """Production column types/constraints; synthetic required identity fields."""
    with conn.cursor() as cur:
        cur.execute('CREATE TABLE paper_accounts (id bigint PRIMARY KEY)')
        for table in tool.TABLES:
            columns = [sql.SQL('{} {}{}').format(
                sql.Identifier(r['column_name']), sql.SQL(r['data_type']),
                sql.SQL(' NOT NULL' if r['not_null'] else ''))
                for r in schema['columns'] if r['table_name'] == table]
            cur.execute(sql.SQL('CREATE TABLE {} ({})').format(sql.Identifier(table), sql.SQL(',').join(columns)))
        # PK/unique before FK. No external production objects are referenced.
        for kind in ('p', 'u', 'c', 'f'):
            for con in schema['constraints']:
                if con['kind'] == kind:
                    cur.execute(sql.SQL('ALTER TABLE {} ADD {}').format(sql.Identifier(con['table_name']), sql.SQL(con['definition'])))
        for trigger in schema['user_triggers']:
            cur.execute(trigger['function_definition'])
            cur.execute(trigger['definition'])
        def insert(table, rows):
            for original in rows:
                row = {k: v for k, v in original.items() if k != 'row_version'}
                cur.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
                    sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, row)),
                    sql.SQL(',').join(sql.Placeholder() for _ in row)), list(row.values()))
        insert('companies', [dict(fixture['company'][0], company_name='Public issuer fixture')])
        insert('securities', [dict(fixture['security'][0], company_id=362, is_primary=True)])
        for table, key in [('filings', 'filings'), ('financial_facts', 'facts'),
                           ('backtest_events', 'events'), ('index_membership_history', 'membership')]:
            insert(table, fixture[key])
        insert('daily_prices', [dict(p, id=i) for i, p in enumerate(fixture['prices'], 1)])


def run():
    original_root, original_factory = tool.ROOT, tool.get_connection
    fixture = tool.read(FIXTURES)['state']
    schema = tool.read(ARTIFACTS / 'schema.json')
    result = dict(correction_code_sha256=tool.file_hash(tool.CODE[0]),
                  production_manifest_sha256=tool.file_hash(original_root/'manifest.json'),
                  fixtures_sha256=tool.file_hash(FIXTURES),
                  schema_sha256=tool.file_hash(ARTIFACTS/'schema.json'),
                  tests=[], production_connections=0, production_writes=0)
    before_files = {p: tool.file_hash(p) for p in original_root.rglob('*') if p.is_file()}
    with tempfile.TemporaryDirectory(prefix='ttwo-pg-integration-') as tmp:
        root = Path(tmp)
        cluster, socket_dir = root/'cluster', root/'socket'
        socket_dir.mkdir(mode=0o700)
        env = dict(os.environ, LC_ALL='C')
        # The server listens only inside our private directory. No TCP listener.
        subprocess.run([str(BIN/'initdb'), '-D', str(cluster), '-U', 'ttwo_fixture',
                        '--auth=trust', '--encoding=UTF8', '--no-locale'],
                       check=True, capture_output=True, env=env)
        started = False
        system_id = None
        try:
            subprocess.run([str(BIN/'pg_ctl'), '-D', str(cluster), '-l', str(root/'server.log'),
                            '-o', f"-k {socket_dir} -p 55439 -c listen_addresses='' -c fsync=on",
                            '-w', 'start'], check=True, capture_output=True, env=env)
            started = True
            def connect():
                nonlocal system_id
                # Explicit local parameters override every production/libpq default.
                conn = psycopg.connect(host=str(socket_dir), port=55439, dbname='postgres',
                                       user='ttwo_fixture', password='', connect_timeout=5,
                                       options='-c default_transaction_read_only=off', autocommit=True)
                with conn.cursor() as c:
                    c.execute("SELECT current_setting('data_directory'),current_setting('listen_addresses'),current_database(),system_identifier::text FROM pg_control_system()")
                    data_dir, listen, database, identity = c.fetchone()
                    assert Path(data_dir).resolve() == cluster.resolve()
                    assert listen == '' and database == 'postgres'
                    if system_id is None:
                        system_id = identity
                    assert identity == system_id
                conn.autocommit = False
                return conn
            with connect() as conn:
                install(conn, schema, fixture)
                with conn.cursor() as c:
                    c.execute('SHOW server_version')
                    result['postgresql_version'] = c.fetchone()[0]
            result['isolation'] = dict(new_cluster=True, private_unix_socket=True,
                                       tcp_disabled=True, data_directory_verified_each_connection=True)
            tool.get_connection = connect
            def snapshot():
                with connect() as conn:
                    tool.configure(conn)
                    return tool.snapshot(conn)
            def whole_tables():
                with connect() as conn:
                    tool.configure(conn)
                    with conn.cursor(row_factory=dict_row) as c:
                        contents = {}
                        for table in tool.TABLES:
                            c.execute(sql.SQL('SELECT t.*,xmin::text AS row_version FROM {} t ORDER BY id').format(sql.Identifier(table)))
                            contents[table] = tool.normalized(c.fetchall())
                        return contents
            def package(name):
                tool.ROOT = root/name
                with redirect_stdout(io.StringIO()):
                    tool.capture()
                    tool.prepare()
                return tool.file_hash(tool.ROOT/'manifest.json')
            def execute(mode, pin, receipt=None):
                old = set(tool.ROOT.rglob('receipt.json'))
                with redirect_stdout(io.StringIO()):
                    tool.execute(mode, pin, receipt)
                paths = set(tool.ROOT.rglob('receipt.json')) - old
                assert len(paths) == 1
                path = paths.pop()
                data = tool.read(path)
                assert data['status'] == 'COMMITTED_VERIFIED'
                return path, data
            pin = package('apply_rollback')
            before = snapshot()
            assert business(before) == business(fixture), 'Fixture reload changed business representations'
            tables_before = whole_tables()
            receipt_path, receipt = execute('apply', pin)
            after = snapshot()
            m = tool.read(tool.ROOT/'manifest.json')
            tool.verify_after(before, after, m)
            tables_after = whole_tables()
            changed = {}
            for table in tool.TABLES:
                old_rows = {r['id']: r for r in tables_before[table]}
                new_rows = {r['id']: r for r in tables_after[table]}
                assert old_rows.keys() == new_rows.keys()
                ids = [i for i in old_rows if old_rows[i] != new_rows[i]]
                if ids:
                    changed[table] = ids
            assert changed == {'backtest_events': [tool.EVENT_ID], 'filings': [108402]}
            assert before['filings'][0]['row_version'] != after['filings'][0]['row_version']
            assert before['events'][0]['row_version'] != after['events'][0]['row_version']
            result['tests'].append(dict(name='real_apply_and_postverification', passed=True,
                                        changed_records=changed, status=receipt['status']))
            _, rollback = execute('rollback', pin, receipt_path)
            restored = snapshot()
            assert business(restored) == business(before)
            assert restored['events'][0]['id'] == tool.EVENT_ID
            result['tests'].append(dict(name='real_rollback_business_fields_identity', passed=True,
                                        status=rollback['status'],mvcc_versions_expected_to_change=True))

            # Force PostgreSQL itself to reject the second UPDATE, after the
            # filing UPDATE ran. NOT VALID doesn't evade enforcement on new rows.
            with connect() as conn:
                conn.execute("ALTER TABLE backtest_events ADD CONSTRAINT integration_reject_alternative CHECK (entry_date <> DATE '2025-05-20')")
            pin = package('failure')
            before = snapshot()
            try:
                execute('apply', pin)
                raise AssertionError('Expected PostgreSQL CHECK violation')
            except tool.GuardFailure:
                assert snapshot() == before
                receipt = tool.read(next(tool.ROOT.rglob('receipt.json')))
                assert receipt['status'] == 'FAILED_OR_COMMIT_STATE_UNCERTAIN'
            # pg_ctl log confirms the actual SQLSTATE-equivalent server error.
            assert 'integration_reject_alternative' in (root/'server.log').read_text()
            result['tests'].append(dict(name='real_second_update_error_rolls_back_filing',passed=True,
                                        injected_error='PostgreSQL CHECK constraint on event entry_date',
                                        unchanged_rows_and_xmin=True))
            with connect() as conn:
                conn.execute('ALTER TABLE backtest_events DROP CONSTRAINT integration_reject_alternative')

            pin = package('locking')
            before = snapshot()
            with connect() as blocker:
                blocker.execute('UPDATE financial_facts SET value=value WHERE id=547980')
                start = time.monotonic()
                try:
                    execute('apply', pin)
                    raise AssertionError('Expected correction lock timeout')
                except tool.GuardFailure:
                    elapsed = time.monotonic()-start
                    assert 2.5 <= elapsed < 10
                    assert snapshot() == before
                blocker.rollback()
            result['tests'].append(dict(name='real_competing_writer_causes_correction_lock_timeout',
                                        passed=True, elapsed_seconds=round(elapsed,3),no_partial_correction=True))

            # Reverse direction: hold the tool's actual lock set; another backend
            # must be unable to update or delete/reinsert target/dependency rows.
            with connect() as holder:
                tool.configure(holder, write=True)
                tool.revalidate(tool.snapshot(holder), before)
                for query in ('UPDATE filings SET acceptance_datetime=acceptance_datetime WHERE id=108402',
                              'DELETE FROM backtest_events WHERE id=413248',
                              "INSERT INTO daily_prices (id,symbol,trade_date) VALUES (999999,'TTWO','2025-05-19')"):
                    with connect() as writer:
                        writer.execute("SET LOCAL lock_timeout='300ms'")
                        try:
                            writer.execute(query)
                            raise AssertionError('Writer bypassed correction locks')
                        except psycopg.errors.LockNotAvailable:
                            writer.rollback()
                holder.rollback()
            assert snapshot() == before
            result['tests'].append(dict(name='real_lock_set_excludes_update_delete_insert',
                                        passed=True, competing_backends=3,no_partial_correction=True))
            result['passed'] = True
        except Exception as error:
            result.update(passed=False, failure_type=type(error).__name__,
                          failure=str(error) if isinstance(error,(tool.GuardFailure,AssertionError)) else 'Local integration failure; inspect runner')
            raise
        finally:
            tool.ROOT, tool.get_connection = original_root, original_factory
            if started:
                subprocess.run([str(BIN/'pg_ctl'), '-D', str(cluster), '-m', 'fast', '-w', 'stop'],
                               check=True, capture_output=True, env=env)
            result['disposable_cluster_stopped'] = started
            assert all(tool.file_hash(p) == h for p,h in before_files.items()), 'Production package changed during integration'
            result['production_package_unchanged'] = True
            result['test_manifests_receipts'] = 'Separate ephemeral test roots, deleted with cluster; no database dump retained'
            ARTIFACTS.mkdir(exist_ok=True)
            label = 'results.json' if result.get('passed') else 'failure_'+result['correction_code_sha256'][:12]+'.json'
            (ARTIFACTS/label).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', required=True)
    parser.parse_args()
    run()
