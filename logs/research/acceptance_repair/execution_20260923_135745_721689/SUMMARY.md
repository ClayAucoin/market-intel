# Historical SEC acceptance repair — committed and verified

The approved repair completed successfully on **2026-09-23**. Transaction **864672** updated exactly **29,837** `public.filings.acceptance_datetime` values. Execution began at **13:57:50.072783 UTC**; commit was acknowledged at **13:57:52.311140 UTC**. A separate **read-only** post-commit transaction began at **13:57:52.329660 UTC** and passed all checks. The complete application run, including source verification, backup and verification, took 8.940 seconds.

## Pinned operation and scope

Manifest: `../manifest.json.gz`.

SHA-256: `f8bdc0b837287a2cd3d22a97115de268d1550863d72428b38a407c8ff9afed74`.

The manifest was not regenerated or broadened. Its sidecar, source-audit hash, all 1,139 local cache-file hashes, source normalization, category counts and unique filing/accession identities were revalidated before application. A fresh standalone preflight is saved at `../preflight_20260923_135055.json`.

Command actually executed:

```sh
PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=15000' .venv/bin/python -m src.backtesting.apply_acceptance_repair --apply
```

**Do not rerun the application.** The old-value guard intentionally rejects already-corrected rows. The older manifest `--verify-db` command likewise checks pre-repair old values, so its failure after this repair is expected; the authoritative post-repair evidence is this execution's receipt.

The runner enabled read-write only for the single application transaction. It locked filings against concurrent writers and held SHARE locks on protected tables, with a 5-second lock timeout and 15-second statement timeout. After locking, it repeated the old-value, identity, cutover, count and full protected-state checks. One parameterized UPDATE joined the approved rows by filing ID, company ID, CIK, accession, old timestamp and filing date; only `acceptance_datetime` was assigned. RETURNING IDs had to equal the exact 29,837 approved IDs. Pre-commit verification passed before the connection context committed. Any failed in-transaction guard would have rolled back the whole update. Ambiguous commit outcomes are recorded rather than automatically retried.

## Before/after verification

| Population | Before | After | Result |
|---|---:|---:|---|
| Total filings | 31,097 | 31,097 | Unchanged |
| Approved safe rows with old erroneous timestamps | 29,837 | **0** | All corrected |
| Approved safe rows with proposed UTC timestamps | 0 | **29,837** | Exact match |
| Already correct, excluded | 984 | 984 | All unchanged |
| Exceptional offsets, excluded | 71 | 71 | All unchanged |
| Missing/unresolved sources, excluded | 205 | 205 | All unchanged |

All **1,260 excluded filings** retain their exact old timestamps. Every filing's identity, accession, company/CIK, form and filing date was checked against the manifest. A SHA-256 fingerprint of **all filing fields except acceptance_datetime** is identical before, inside the transaction after UPDATE, and after commit. This also protects report_date, created_at, document metadata and URLs. No financial-fact `filed_date` or other fact value changed.

Source-comparable rows now consist of **30,821 correct** and **71 exceptional**, plus **205 unresolved**. The remaining exceptional rows are CIEN (24) and TTWO (47), still awaiting separate review. They were not inferred or repaired.

## Actual timestamp/date corrections

- **19,829** stored instants moved four hours earlier to their source UTC instant.
- **10,008** moved five hours earlier.
- **16,706 UTC calendar dates changed** within the approved safe subset.
- **3,578 calendar candidate-entry dates differ** under the existing timing function. No actual event entry dates were updated or historical research rerun.

The earlier audit's 16,766 UTC-date changes and 3,582 candidate changes included exceptional rows. The smaller executed counts correctly exclude those rows.

## Protected tables and prospective paper account

Complete-row SHA-256 fingerprints (ordered by stable row ID) and counts match before/in-transaction-after/read-only-post-commit for every protected table:

| Table | Rows unchanged |
|---|---:|
| financial_facts | 173,028 |
| backtest_events | 14,824 |
| companies | 8,071 |
| index_membership_history | 667 |
| paper_accounts | 1 |
| paper_signals | 0 |
| paper_positions | 0 |

The historical membership-qualified event subset remains **14,741**. Both all-table content and membership-qualified counts are unchanged; no event rebuilding occurred.

Paper account **cash remains $10,000**. All account fields remain unchanged. Immutable prospective cutover remains **2026-09-20 10:32:26.133136 UTC**. No signals, positions, commitments or trades were created/backfilled. The experimental signal code and thresholds were not modified.

## Backup and durable evidence

- [receipt.json](receipt.json): operation pin, runner hash, transaction ID, timestamps, counts, correction statistics, before/after protected-table fingerprints, cutover/cash and backup identity.
- [receipt.json.sha256](receipt.json.sha256): immutable receipt checksum.
- [filings_before.jsonl.gz](filings_before.jsonl.gz): complete pre-repair filing rows, 31,097 rows, mode **0600** in a **0700** execution directory; gzip read-back matched every original row and manifest before-image before any update. SHA-256 is in the receipt. This is a **table-scoped backup**, not a full database dump. Filing column metadata is also saved in the receipt; the database schema was not changed.
- [validation.json](validation.json): receipt/backup/code integrity checks and regression results.
- [regression_tests.txt](regression_tests.txt): full offline test output.

The backup plus pinned manifest supports a separately approved inverse repair of acceptance timestamps, matching exact after-images before restoring old timestamps; no rollback operation was run or enabled. No other column needs restoration because full protected-state verification passed.

An earlier read-only preparation backup is retained at `../execution_20260923_135646_830619/`. A failed sandbox connection is recorded at `../execution_20260923_135613_911626/`; that invocation aborted before database access/writes. Approved local read-only preparation and application succeeded. No in-transaction guard or post-commit verification failed.

## Code changes and testing

Created:

- `src/backtesting/apply_acceptance_repair.py` — pinned one-transaction runner; default is read-only preparation, explicit --apply required.
- `tests/test_apply_acceptance_repair.py` — eight offline tests for pin rejection, exact before/after/excluded populations, identity/date drift, second-run rejection, SQL update population/count guards, rollback behavior and post-commit failure reporting.
- Fresh preflight, execution receipts/backups, checksum, test log, validation JSON and this report under `logs/research/acceptance_repair/`.

Modified only the repair README to link this completed execution. All prior parser/audit/pilot source changes and evidence were preserved; no commit was made.

**212 focused offline tests passed after commit**, including timestamp/SEC validators and writers, manifest safeguards, research audit fixtures, all 37 SIC header hashes and 395 saved lookups, production freshness and prospective paper-trading safeguards. Tests mock live DB/network/notifications; no live paper run or daily orchestrator was executed. Both new Python files compiled; git diff --check passed. No test failures.

## Stopping point

Repair and post-commit verification are complete. **Backtest events are unchanged and still reflect old timing; their rebuild remains separately authorized work.** The 71 exceptional and 205 unresolved filings remain open anomalies. No historical research rerun, SEC/price refresh, SIC expansion, live paper trading, daily orchestration, notification, service change or commit occurred. Stop here pending separate instructions.
