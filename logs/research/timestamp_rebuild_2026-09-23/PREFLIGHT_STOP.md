# Historical timestamp rebuild — stopped before mutation

Snapshot: **2026-09-24 02:33:50 UTC** (2026-09-23 local evening). No rebuild was executed by this task. The database no longer matches the stated post-repair/pre-rebuild starting state. A research-baseline decision is required before proceeding.

## Unexpected intervening changes

| Measure | Successful repair / saved audit | Current preflight |
|---|---:|---:|
| Filing rows | 31,097 | **31,098** |
| Financial facts | 173,028 | **173,033** |
| Total backtest rows | 14,824 | **14,825** |
| Historical membership-qualified events | 14,741 | **14,742** |
| Exact experimental signals | 194 | **191** |
| Paper cash | $10,000 | $10,000 |
| Paper signals / positions | 0 / 0 | 0 / 0 |

The first strict repair-state preflight failed on filing count, before any rebuild. A subsequent bounded read-only snapshot measured the drift without modifying the builder or database.

- The extra filing is **GIS**, company 612, CIK 0000040704, accession **0001628280-26-063201**, 10-Q, filing date 2026-09-23, report date 2026-08-30. Accepted 2026-09-23 15:44:38Z; stored creation time 22:12:53.960847Z.
- Financial facts have a net increase of five and a different full-table fingerprint. Three newly created GIS facts relevant to the builder (revenue, operating income, diluted EPS) appear in the saved input snapshot with creation times around 22:03:03Z. This does **not** prove that only five inserts occurred or that no older fields were updated: the repair receipt contains a table fingerprint, not full financial-fact before-images. All saved dependencies from the original 194-event audit still match their recorded financial values/identities/dates.
- All 14,741 original historical event keys remain represented, but **none retains its original event ID**. Current event creation times include 2026-09-23 22:21:43Z. This establishes intervening event replacement; the actor/process was not determined here.
- The additional historical event is **ADBE**, security 149, period_end 2026-08-28, entry 2026-09-23. It does not qualify for the exact signal.
- SEC cache files also had pre-existing changes when the task began. They were not refreshed or edited by this task. Current price-data vintage has not been compared with the original historical price vintage, which was not fully archived by the earlier audit.

## What remains protected and unchanged

The entire original 31,097-row filing manifest still matches the expected **post-repair** identities, accessions, filing dates and timestamps:

- 29,837 repaired timestamps remain at their proposed UTC instants.
- 984 already-correct, 71 exceptional and 205 unresolved timestamps are unchanged.
- No original manifest filing is missing or changed; the count difference is one additional filing.

Full-table row fingerprints for companies, historical index membership, paper accounts, paper signals and paper positions match the successful repair receipt. Account cash is **$10,000**, with zero signals/positions. Immutable cutover remains **2026-09-20 10:32:26.133136 UTC**.

These checks are read-only, repeatable-read, with a 15-second statement timeout. No paper, filing, financial or event data was modified by this task.

## Preserved current event snapshot

[before_20260924_023350.json.gz](before_20260924_023350.json.gz) contains every current event column, display ticker, stable `(security_id, period_end)` key, entry date, financial/momentum/outcome fields, train/test classification, historical membership and exact-signal flags. There are **zero duplicate stable keys**.

It also preserves current filing metadata, relevant historical-universe financial histories, ticker history, protected-table fingerprints, source-report hashes and event/fact drift against the saved sector audit. The data is sufficient to compare a **future authorized rebuild against this current state**, without relying on event IDs. It cannot recover all fields of the already-replaced original 14,741-event dataset.

[Snapshot summary and SHA-256](before_20260924_023350.json.summary.json).

## Observed changes against saved historical evidence — not results of a rebuild run here

The earlier timestamp audit preserves entry dates/current-revenue fact IDs for all 14,741 historical events. Those fact IDs still resolve in the current input snapshot. Matching through them to `(security_id, period_end)` gives all old keys present, one new historical key, and the following **observed** entry-date differences:

| Current minus saved entry date | Events |
|---|---:|
| 0 days | 12,818 |
| -1 day | 1,458 |
| -2 days | 4 |
| -3 days | 435 |
| -4 days | 26 |
| Changed total | **1,923** |

No matched entry crosses the fixed 2023-12-31/2024-01-01 train/test boundary. No matched old historical key loses membership qualification at its current entry. The old all-event key reconstruction uses current identity attached to the same saved fact IDs; the old exact-signal audit separately retains explicit security IDs and period ends. This distinction is preserved in the evidence.

Full old financial metrics/momentum/outcomes are saved only for the 194 audited signals, not for the entire 14,741-event population. Accordingly, a complete original-versus-current metric/outcome comparison and pure timestamp attribution cannot be claimed from these artifacts alone.

### Exact-signal cohort

The prior saved cohort has **194** signals: 146 train / 48 test. The observed current cohort has **191**: 142 train / 49 test. **190 retained, four removed, one newly present.** These are the unchanged thresholds: revenue acceleration >=20, operating margin change >0, pre-entry 20-day excess versus SPY >0.

Across the original 194 saved rows, **16 entries, 16 momentum values and 16 excess_30d values changed**. Revenue acceleration and operating-margin change changed in **zero** of those original rows. No saved input dependency value/identity/date changed for that cohort.

The four predicted removals are confirmed in the existing live data:

| Security | period_end | Old → current entry | Old → current pre_excess_20d | Current qualification |
|---|---|---|---:|---|
| REGN | 2021-03-31 | 2021-05-07 → 2021-05-06 | 2.11 → -2.12 | Fails momentum |
| REGN | 2021-06-30 | 2021-08-06 → 2021-08-05 | 2.27 → -1.88 | Fails momentum |
| SPG | 2021-06-30 | 2021-08-05 → 2021-08-04 | 1.27 → -0.41 | Fails momentum |
| TSN | 2021-07-03 | 2021-08-10 → 2021-08-09 | 5.39 → -4.90 | Fails momentum |

The newly present signal is **FTV**, period_end **2026-04-03**, current entry **2026-04-30** versus saved entry **2026-05-01**. Current revenue acceleration **63.96**, operating-margin change **2.08**, pre_excess_20d **2.28**, excess_30d **-11.60**. It was not in the old 194 cohort. Its old non-signal metric/momentum row was not archived, so the exact original failing threshold and exclusive causal attribution are **not established** here. Do not invent those values from the current database.

### Saved-audit versus observed-current 30-calendar-day statistics

These use the existing `time_split_statistics.get_stats` / distribution helpers and completed-only denominators. Saved sector-readiness values, rather than a rerun of that audit, supply the original observations. N here counts signals, while completed N is the denominator for returns/win rates.

| Metric | Old train | Current train | Old test | Current test |
|---|---:|---:|---:|---:|
| Signal N | 146 | 142 | 48 | 49 |
| Completed N | 146 | 142 | 47 | 48 |
| Mean excess, pp (unrounded) | 1.427877 | 1.432394 | 4.818936 | 4.088333 |
| Standard rounded average, pp | 1.43 | 1.43 | 4.82 | 4.09 |
| Median excess, pp | 1.37 | 1.07 | 3.06 | 2.28 |
| Excess >0 win rate, % | 55.48 | 54.23 | 59.57 | 58.33 |
| Sum excess, pp | 208.47 | 203.40 | 226.49 | 196.24 |
| Standard trimmed average, pp | 1.00 | 0.99 | 3.62 | 3.14 |

These differences are material to sample composition and the magnitude of test performance, although both observed means remain positive. They do not establish a new validated causal comparison: other input/state changes intervened, and existing derived-lineage, ticker/price-vintage, current-sector-label and small/concentrated-sample limitations remain. The 30-calendar-day horizon, split, signal thresholds and paper 45-calendar-day hold were not changed.

## Evidence and reproduction

- `before_20260924_023350.json.gz` — full current event/provenance snapshot.
- `before_20260924_023350.json.summary.json` — aggregate diagnostics and snapshot hash.
- `observed_intervening_changes.json` — new filing, inferred all-event timing differences, removed/new cohort rows, event ID replacement evidence.
- `observed_cohort_field_changes.json` — all original-cohort field changes and historical split crossings.
- `prior_saved_signal_statistics.json` — existing summary helpers applied offline to the saved old cohort.

New tooling: `src/backtesting/timestamp_rebuild_preflight.py` (read-only capture only) and `tests/test_timestamp_rebuild_preflight.py`. It does not invoke or modify the builder. Reproduction, if needed later:

```sh
PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=15000' .venv/bin/python -m src.backtesting.timestamp_rebuild_preflight
```

Four focused tests passed (stable keys, addition/removal/timestamp drift, excluded-row expectations, membership/completed-only statistics). Both Python files compiled; git diff --check passed. Initial sandbox database attempts failed with OperationalError; approved local read-only execution succeeded. The strict repair-state guard failure was real and is the reason no rebuild began. No test failed.

## Required decision / stopping point

**Do not yet accept an agent-rebuilt historical baseline: this task has not rebuilt anything.** The original complete event state was replaced before it could be preserved here. Restoring or fabricating that state is not authorized and was not attempted.

Choose one:

1. Authorize using the preserved **current 14,742-event / 191-signal state** as the before snapshot for the requested controlled rebuild, while comparing the saved original 194-signal audit separately and explicitly acknowledging the incomplete all-event old-metric baseline.
2. Stop until an original full 14,741-event snapshot/backup is located and the intervening updates are accounted for. Do not restore database values or disable services as an inferred next action.

No database writes, event rebuild, SEC/price refresh, historical research rerun, SIC expansion, live paper trading, daily orchestration, notifications, migrations, service changes or commits occurred. Only the saved evidence was compared offline and bounded read-only snapshots were captured.
