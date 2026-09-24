# SEC acceptance timestamp correction — ready for historical repair review

> **Execution update:** The approved 29,837-row repair committed and passed post-commit verification on 2026-09-23. See [execution summary](execution_20260923_135745_721689/SUMMARY.md) and [receipt](execution_20260923_135745_721689/receipt.json). The original pre-repair proposal below is retained for provenance; its pending-approval and not-yet-executed statements describe that earlier stage.

2026-09-23. Parser implementation complete. **No historical database repair executed.** No commit, event rebuild, refresh, live trading/orchestration, notification or SIC expansion.

## Implementation

`src/sec/acceptance_time.py` provides two source-specific functions:

- `parse_submissions_acceptance`: full ISO timestamp with explicit Z or numeric offset (`±HH`, `±HHMM`, `±HH:MM`), normalized to aware UTC. Preserves fractional seconds through microsecond precision. Missing None/empty remains missing. Rejects naive clocks, invalid suffixes/offsets, and precision beyond six fractional digits rather than silently truncating it.
- `parse_header_acceptance`: compact `YYYYMMDDHHMMSS` interpreted as America/New_York and converted to UTC. Both DST folds are round-tripped; ambiguous fall-back and nonexistent spring-forward clocks raise ValueError. These require separate evidence, not a guessed fold.

Before: the universe importer discarded offset/fractions and attached Eastern to a UTC clock. After: its existing `parse_acceptance_datetime` wrapper calls the submissions parser. The older filing repository also parses source strings before sending them to TIMESTAMPTZ, removing session-timezone dependence for naive strings. Both writers reject invalid nonempty values before opening a database connection.

Both submissions metadata validators now use the same explicit-ISO semantics. Their existing missing-metadata and failure/recovery policies remain in place. Rejecting malformed/naive inputs is an intended tightening of timestamp validation. No other production policy changes: target selection, stored-metadata reuse, signal rules, portfolio behavior and cutover are unchanged. Existing incorrect timestamps are **not** automatically repaired by the parser change, and production reuse can still retain them until repair. An explicitly invoked future import that writes a source timestamp uses the corrected UTC instant.

The SIC pilot uses the separate header parser, then renders its UTC result back in Eastern for the existing report schema. All saved evidence files remain unchanged and replay exactly. The historical audit now owns a clearly named frozen `legacy_parse_acceptance_datetime` solely to reproduce the old defect; it is not used by either production writer. Its existing tests continue to test that frozen historical behavior. Production freshness fixture timestamps now explicitly encode their previously intended Eastern offset; assertions and policies were not relaxed.

GEN accession `0000849399-26-000031`: submissions `2026-08-07T20:03:52.000Z` and header `20260807160352` both normalize to **2026-08-07 20:03:52Z**, not the stored next-day **2026-08-08 00:03:52Z**.

## Reviewed proposal and reconciliation

Source audit: `../acceptance_timezone_2026-09-23_131057.json.gz`; conclusions and research effects: `../acceptance_timezone_completion_2026-09-23.md`. Neither audit nor expensive event/price replay was rerun.

| Manifest category | Rows | Proposed DB changes |
|---|---:|---:|
| Safely correctable from explicit evidence | 29,837 | 29,837 |
| Already correct | 984 | 0 |
| Exceptional offset requiring review | 71 | 0 |
| Missing/unresolved evidence | 205 | 0 |
| Total | 31,097 | 29,837 |

Counts and offset distribution **exactly reconcile** with the audit: 19,829 +4-hour, 10,008 +5-hour, 39 +8-hour, 32 +10-hour, 984 zero-offset and 205 unmatched rows. Source evidence is available for 30,892 rows. The +8/+10-hour rows are CIEN (24) and TTWO (47); source-normalized instants are included for review but their `proposed_timestamp` is null. The unresolved 205 also have null proposed timestamps. No corrections are inferred for them.

Each proposal retains filing ID, company ID, CIK, accession, display ticker, form/filing date, stored instant, original source text, source-normalized UTC, proposed instant, database-minus-source seconds, source path and SHA-256. Ticker labels are not identity keys. Classification requires exact reproduction of the frozen old parser **and** agreement of explicit source instants, not just a four/five-hour delta.

The generator independently checked every cited timestamp/accession/filing date against **1,139 local submissions cache files**, with filename/envelope CIK checks and hashes. It only reads cited sources, not all historical financial facts/prices. Missing, conflicting or changed cited evidence aborts generation. The approved category counts and audit offset distribution are enforced; population drift stops the process.

Files:

- `manifest.json.gz`: full before/after proposal for all 31,097 audited rows.
- `manifest.json.gz.sha256`: **f8bdc0b837287a2cd3d22a97115de268d1550863d72428b38a407c8ff9afed74**.
- `preflight_20260923_132450.json`: canonical live read-only preflight, 13:24:50 UTC.
- `preflight_20260923_132417.json`: initial preflight, retained; recorded only total event count.

Canonical preflight: transaction_read_only=on; 31,097 live filings; zero changed/missing IDs; zero extra IDs; all identities, old timestamps and filing dates agree; immutable cutover matches **2026-09-20 10:32:26.133136 UTC**. The table has 14,824 total event rows, of which **14,741 satisfy the historical membership filter used by the audit**. This distinction is not event-count drift and no events were changed.

## Reproducible commands (no database-writing mode)

```sh
# Offline generation; exclusive create refuses to overwrite the reviewed manifest.
.venv/bin/python -m src.backtesting.acceptance_repair_manifest

# Repeat this read-only preflight before any separately approved application.
PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=15000' .venv/bin/python -m src.backtesting.acceptance_repair_manifest --verify-db
```

The tool has **no apply option and no UPDATE/INSERT/DELETE statements**. A successful preflight validates a snapshot; it does not reserve rows against later concurrent changes or authorize mutation.

## Proposed historical repair process — separate approval required

Approve only the 29,837 safe rows identified by the manifest hash above. Application tooling/transaction remains a separate step; no executable apply command is claimed here.

1. Preserve this manifest, its source files/hashes and old research artifacts. Create an independently restorable, access-controlled database backup using the established operational method, without exposing credentials. Verify restore/rollback readiness. The manifest itself provides the exact timestamp before-images but is not a full database backup.
2. Implement a narrowly scoped repair runner that pins the approved manifest SHA-256 and revalidates its source hashes, identities, categories, counts, source-normalized instants and all live preconditions. No network/refresh step. Reject missing/changed evidence, extra/missing database rows, changed old values or changed cutover; return to review instead of silently adjusting scope.
3. Begin one bounded transaction with lock and statement timeouts. Serialize against filing writers with a short table lock, and lock/read the account cutover for the transaction; do not change services/timers. Recheck every relevant identity/value and cutover **inside** the transaction. If locking exceeds the bound, abort for a quieter window.
4. Stage only safe manifest rows. UPDATE **only `filings.acceptance_datetime`**, joining on filing ID, company ID, CIK and accession, with exact old-timestamp preconditions. Use the source-normalized timestamp from the reviewed manifest. Do not touch filing_date, report_date, financial facts, events, accounts, signals or positions. Require exactly 29,837 affected rows; any mismatch rolls back the entire transaction.
5. Before commit, verify every safe row equals its intended UTC instant, all 1,260 excluded rows remain byte/instant-equivalent for the protected fields, and cutover remains identical. Expected comparison afterward: **30,821 correct**, **71 exceptional**, **205 unresolved**; no remaining +4/+5-hour rows in this fixed snapshot. Verify protected event/paper tables have not been modified by the repair. Preserve a durable after-image/row-count report and transaction completion status.
6. Commit only after all checks succeed. A rerun must never shift rows again; existing-new values should produce an explicit already-applied outcome or stop, not a second conversion. An approved rollback would restore before-images only where the current value still equals this repair's after-image, with identical identity/count guards; never overwrite subsequent changes.
7. Recheck with focused read-only queries. Leave the 71 exceptional and 205 unresolved rows pending review. Leave all backtest events as-is; **they remain based on old timing until a separately authorized rebuild**. Never create retrospective paper signals/trades or alter cutover. Do not resume SIC expansion as part of this repair.

A full post-repair source comparison should preserve the exclusions above. Resolving exceptional write provenance or missing source evidence is separate work. Full corrected event/signal counts and performance require the later rebuild; the known 16 changed entries/four lost sample signals are documented in the completed audit, not recomputed here.

## Files changed in this implementation

New code/tests:

- `src/sec/acceptance_time.py`
- `src/backtesting/acceptance_repair_manifest.py`
- `tests/test_sec_acceptance_time.py`
- `tests/test_acceptance_repair_manifest.py`

Modified existing code/tests (including previously uncommitted audit/pilot code):

- `src/sec/import_universe_filings.py`
- `src/sec/filing_repository.py`
- `src/sec/json_cache.py`
- `src/sec/sec_submissions.py`
- `src/backtesting/sec_sic_pilot.py` — only source-specific timestamp parsing, same saved rendering.
- `src/backtesting/audit_acceptance_timezone.py` — freeze the legacy parser for reproducibility.
- `tests/test_audit_acceptance_timezone.py` — reference that frozen parser.
- `tests/test_sec_production_freshness.py` — explicit Eastern fixture offsets.

New persistent artifacts: this README, the manifest, its SHA-256 file and the two preflight JSON files under `logs/research/acceptance_repair/`. Prior SIC/audit reports and cached evidence are untouched.

## Validation and operational limits

**204 focused offline tests passed**, covering submissions Z/positive/negative offsets, daylight/standard time, microseconds, DST folds/gaps, malformed/naive inputs, GEN regression, both writer parameters and rejection before DB connection, manifest classification/source identity/hash/count safeguards, preflight drift/cutover detection, production freshness, prospective paper rules, readiness/signal audits, all 37 pilot header hashes and all 395 saved lookups. Mocked production/paper tests execute no live trading/orchestrator jobs or notifications.

```sh
.venv/bin/python -m unittest tests.test_sec_acceptance_time tests.test_acceptance_repair_manifest tests.test_audit_acceptance_timezone tests.test_audit_acceptance_signal_impact tests.test_audit_sector_readiness tests.test_sec_sic_pilot tests.test_sec_production_freshness tests.test_prospective_paper_trading
```

All 12 changed/new Python files passed py_compile; git diff --check passed. The initial sandbox preflight connection failed with suppressed OperationalError; approved read-only local execution succeeded. No test failures. No external requests, SEC/price refreshes, database mutations/migrations, expensive audits, event rebuilds, live paper trading/orchestration, notifications, service changes, SIC expansion or commits occurred.

**Stopping point:** parser fix and reviewed manifest are complete. Approval of the safe-row repair process is required before implementing/executing the database-writing application step. The 71 exceptional rows, 205 unresolved rows, and later event rebuild remain excluded.
