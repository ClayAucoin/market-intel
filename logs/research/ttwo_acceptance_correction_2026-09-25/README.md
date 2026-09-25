# TTWO targeted acceptance correction package — prepared, not applied

Scope: accession `0001628280-25-026694`, filing **108402**, company **362**, stable event key **(358, 2025-03-31)**, reviewed/current event **413248**. This package does not modify shared timestamp policy or the completed 29,837-row repair. No SEC requests, production database writes, job changes or production builder runs occurred during preparation or integration verification. The reviewed package is checkpointed separately; it has not been applied to production.

## Current capture and baseline

Captured **2026-09-25 16:52:38.163107 UTC** in one repeatable-read transaction with database `transaction_read_only=on`. The default read-only dry-run subsequently returned `DRY_RUN_READY`. The target filing still has `2025-05-20 14:32:02+00:00`; event 413248 is still present. No silent retargeting occurred.

The accepted September 24 **02:51:28 UTC** saved baseline is `logs/research/timestamp_rebuild_2026-09-23/provenance_inputs.json.gz`, not merely the earlier “before” snapshot. `baseline_drift.json` records its hash and exact differences. Since that baseline, event 398505 was replaced by 413248 and event creation/update timestamps advanced to September 24 22:24:04.871511 UTC. The two facts' update timestamps advanced, but values and provenance did not change. All event calculation fields and all filing fields agree. These are the same changes already disclosed in the reviewed proposal; no additional reviewed-state drift was found.

The compact 240 KB snapshot includes one filing/event, two accession-linked facts, all **227** prior/current records for this security's four calculation metrics, **498** TTWO/SPY price rows from December 1, 2024 through November 30, 2025, one membership interval, issuer/security identity and downstream-reference/foreign-key inventories. Full prior fact ordering is preserved because nearest-year and previous-quarter selection depend on that ordering. Prices are a finite dependency superset, not a vendor cache copy. Calculations require 61 prior closes for each symbol and all entry/exit records, reject duplicate ordering, and stop on insufficient sessions. The observed missing operating-margin input remains NULL; it is not filled or guessed.

Facts **547980** (revenue) and **548242** (gross profit) retain their values. There are no linked exhibits, paper signals or positions. All current accession-linked facts have this security/period. Other events can use these facts' unchanged values as comparators; no other event's timestamp depends on this filing under the inspected calculation rules.

## Reproduction and hypothetical replacement

**All 31 current event fields reproduced exactly at stored precision** from the fresh captured inputs using existing pure helpers. No production builder loop or save function was called. `comparison.json` preserves full baseline/alternative fields, stock/SPY prices, target/actual exit dates, and exact-signal decisions. All inputs other than acceptance are identical.

Proposed timestamp only: `2025-05-20T14:32:02Z` → **`2025-05-20T10:32:02Z`** (06:32:02 EDT). Existing saved raw header and later submissions independently agree; fixture paths and hashes are in the manifest. Fixtures are referenced without duplication.

| Metric | Current reproduced baseline | Hypothetical replacement |
|---|---:|---:|
| Entry / adjusted open | May 21, 2025 / $228.03 | May 20, 2025 / $233.02 |
| 30-day exit, stock and SPY | June 20 | June 20 |
| 90-day exit, stock and SPY | August 19 | August 18 |
| 180-day exit, stock and SPY | November 17 | November 17 |
| 20-session excess momentum | +0.67% | −1.38% |
| 30-day stock return | 4.53% | 2.30% |
| 30-day SPY return | 1.29% | 0.50% |
| 30-day excess return | 3.24% | 1.80% |
| Exact signal | False | False |

The 30-calendar-day rule remains unchanged: the alternative June 19 target selects the first saved session, June 20. Exact-signal eligibility requires acceleration ≥20%, operating-margin change >0 and excess momentum >0. Acceleration is **13.56%** and operating-margin change **NULL** in both cases; the alternative also fails momentum. Membership holds on both entry dates. This is one-event sensitivity, not a strategy-performance estimate.

### Exact event fields proposed for update

These values were calculated from captured decimal inputs, not copied from earlier rounded reports. The tool changes only these **22** event fields plus its audit `updated_at`; financial metrics, identity and `created_at` remain unchanged.

| Field | Expected old | Proposed new |
|---|---|---|
| entry_date | 2025-05-21 | 2025-05-20 |
| entry_price | 228.03 | 233.02 |
| pre_return_20d | 13.11 | 14.38 |
| pre_return_60d | 12.02 | 10.87 |
| pre_excess_20d | 0.67 | -1.38 |
| pre_excess_60d | 12.45 | 11.42 |
| pre_volatility_20d | 38.40 | 38.83 |
| previous_close | 237.5 | 234.66 |
| entry_open | 228.03 | 233.02 |
| opening_gap_pct | -3.99 | -0.70 |
| spy_opening_gap_pct | -0.74 | -0.30 |
| opening_gap_excess | -3.25 | -0.40 |
| return_30d | 4.53 | 2.30 |
| spy_return_30d | 1.29 | 0.50 |
| excess_30d | 3.24 | 1.80 |
| exit_date_90d | 2025-08-19 | 2025-08-18 |
| return_90d | 0.14 | -0.20 |
| spy_return_90d | 9.05 | 8.79 |
| excess_90d | -8.91 | -8.99 |
| return_180d | 2.43 | 0.24 |
| spy_return_180d | 13.77 | 12.88 |
| excess_180d | -11.34 | -12.64 |

## Guards, application and rollback

Manifest SHA-256: **`fc032a801e529743dd476d2638dc3f52409f5e459f749381e579b5c5e7d7f3e4`**.

`manifest.json` pins input, comparison, before-image, source and calculation/tool code hashes. Apply/rollback also require this explicit externally reviewed hash. Frozen capture/prepare refuse overwrite. `before_images.json` contains full target records; the input snapshot additionally preserves dependency values and PostgreSQL row versions.

Default mode is a **read-only database dry-run**. `--offline` verifies pins and reproduces the comparison without database access. No automatic apply follows a successful dry-run.

Write modes acquire one deterministic, sorted `SHARE ROW EXCLUSIVE` table-lock set on filings, backtest_events, financial_facts, daily_prices, index_membership_history, securities, companies, filing_exhibits, paper_signals and paper_positions. This conservatively blocks writers and delete/reinsert/phantom races across the needed tables; lock footprint is wider than the two changed rows. Ordinary readers remain permitted. Lock timeout is **3 seconds**, statement timeout **15 seconds**, idle-transaction timeout **60 seconds**. A busy scheduled job causes an abort; no timer/service change is made. Write transactions use READ COMMITTED and re-read after acquiring all locks, avoiding an old repeatable-read snapshot taken before lock acquisition. Locks keep inputs stable through commit.

Under locks the tool requires the exact target ID/key, complete target rows, all captured dependency values and row versions, empty reviewed downstream references and the reviewed FK graph. Even a same-value intervening write is rejected via row version. An already-applied state, a replaced event or a dependency change aborts without re-planning. It updates exactly one filing using an expected-old-timestamp predicate and exactly one event using its reviewed ID/key; full before-images were already matched under locks. Both changes commit atomically. A post-update snapshot must match the specified changes, preserve all financial metrics/facts and event identity/creation time, and leave every other captured record unchanged.

Future authorized executions create durable receipts under `executions/`, with before/after state and hashes, pending-commit status and read-only post-commit verification. There is no production execution receipt. Integration test manifests and execution receipts existed only in separate disposable test roots and were removed after their outcomes were summarized. A failed second update or failed verification rolls back the transaction. A lost commit acknowledgment is explicitly marked `FAILED_OR_COMMIT_STATE_UNCERTAIN`, never claimed to be a successful rollback; stop and reconcile before retrying.

Rollback requires a `COMMITTED_VERIFIED` apply receipt for this manifest and exact applied state including row versions. It restores original filing acceptance and changed event fields/updated_at atomically, retaining identity/creation time. Any intervening write, dependency change, reference or rebuild rejects rollback. After a rebuild there is no automatic retarget/restore. Historical before-images cannot safely be forced onto new rows.

## Persistence and limits

The scheduled production filing importer reuses valid stored timing, so it should retain this correction. The non-production upsert path can overwrite timing from submissions; this package does not introduce permanent timestamp precedence or an override registry. Scheduled event rebuilds can replace event IDs again, making this manifest stale; their future calculations should consume the corrected filing if it persists. Approval must be followed by a fresh dry-run; any drift requires separately reviewed regeneration, never editing the pinned manifest to bypass a guard.

Correction/rollback SQL has now passed **real PostgreSQL 18.6 integration tests in a separate disposable cluster**. Actual snapshot, numeric/date/timestamp/MVCC representations, locks, commit, rollback and post-write verification were exercised. No production writes were used. The 32 offline regression tests still cover simulated transaction/error paths separately. Vendor-price and derived-fact historical provenance limitations remain. Snapshot reproduction proves consistency with current inputs, not independent truth of every input.

## Review commands — apply/rollback not executed

Offline verification:

```sh
.venv/bin/python -B -m src.backtesting.ttwo_acceptance_correction --offline
```

Read-only pre-application check:

```sh
.venv/bin/python -B -m src.backtesting.ttwo_acceptance_correction
```

Proposed application, **requires separate approval**:

```sh
.venv/bin/python -B -m src.backtesting.ttwo_acceptance_correction --apply --manifest-sha256 fc032a801e529743dd476d2638dc3f52409f5e459f749381e579b5c5e7d7f3e4
```

Prepared rollback syntax, **requires separate approval** and the actual successful apply receipt:

```sh
.venv/bin/python -B -m src.backtesting.ttwo_acceptance_correction --rollback --manifest-sha256 fc032a801e529743dd476d2638dc3f52409f5e459f749381e579b5c5e7d7f3e4 --receipt <apply-execution-receipt.json>
```

Focused offline tests: **32 passed** (15 package tests plus 17 existing provenance/parser/manifest tests), with network and database connections blocked. **Five real PostgreSQL integration checks also passed**; these did not mock SQL, snapshots, locks or transactions. All three package/test Python files passed compilation; diff/whitespace checks passed. See `validation.json` for exact files and hashes. Transient bytecode and test output are excluded; no production source/cache files changed.

## Real PostgreSQL integration verification

See `../ttwo_acceptance_pg_integration_2026-09-25/README.md`, `results.json` and `schema.json`; runner: `tests/integration_ttwo_postgres.py`. A fresh PostgreSQL 18.6 cluster used a private Unix socket, disabled TCP, and verified its own data directory on every connection. Captured business inputs were loaded using production column types, nullability, primary/unique/foreign/check constraints and the inspected paper-signal trigger. Defaults/sequences were unnecessary because fixture keys were explicit; required identity-only fields were synthetic and an empty paper_accounts stub satisfied its FKs. No full dump was retained.

1. Apply reached COMMITTED_VERIFIED; whole-table comparison identified changes only to filing 108402 and event 413248. Real numeric/date/timestamp/xmin values passed the actual tool verification.
2. Rollback reached COMMITTED_VERIFIED, restoring business fields and event identity/creation time; PostgreSQL MVCC versions appropriately changed.
3. A PostgreSQL CHECK failure on the event update rolled back the preceding filing update; all captured row values and versions remained unchanged.
4. A second connection holding a dependency write caused the correction to abort after its three-second lock timeout, with no partial correction.
5. The tool's actual lock set excluded separate-backend UPDATE, DELETE and INSERT attempts.

No correction-code defects were found; the code hash and **manifest pin are unchanged**, so there is no superseded manifest. The final production read-only dry-run returned DRY_RUN_READY after integration/regression verification. Apply remains a separate approval decision; any later dependency drift/rebuild will invalidate this package.
