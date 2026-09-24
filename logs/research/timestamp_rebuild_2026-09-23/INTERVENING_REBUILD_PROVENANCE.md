# Intervening historical-event rebuild: provenance investigation

The rebuild **definitely occurred**, through the existing scheduled daily systemd job on September 23, 2026. No rebuild or database write was performed by this investigation. A read-only, in-memory replay of the unchanged builder exactly reproduces all 14,742 current historical events across all 31 builder-written fields. Another rebuild is unnecessary for these inputs. Recommend accepting the saved current snapshot as the corrected-current-input historical baseline, subject to the existing provenance limitations below.

## Chronology and attribution

All times below are UTC; Chicago was CDT (UTC−5).

| Time, September 23 | Evidence/event |
|---|---|
| 13:57:52.311140 | Timestamp repair committed, transaction 864672; receipt verifies 31,097 filings, 173,028 facts and 14,824 events. |
| 22:00:03.955308 | systemd starts market-intel-daily.service, corresponding to the weekday 17:00 America/Chicago timer. |
| 22:00:04.328127–22:19:57.218194 | Scheduled production SEC refresh, run df2f9fba28cc47a5890cb798c40f2977; one filing persisted. |
| 22:03:03.056795–22:03:03.218571 | Five GIS facts created. |
| 22:12:53.960847 | GIS filing metadata created. Financial import precedes filing import in this pipeline. |
| 22:19:57.434795 | Scheduled incremental price refresh begins. |
| 22:21:43.093106 | Orchestrator launches historical event builder. |
| 22:21:43.330249 | Builder logs clearing 14,741 historical events. |
| 23:50:46.189708 | Post-transaction builder summary reports 14,742 saved events. |
| 23:50:46.209521 | Scheduled paper stage starts; no paper state change. |
| 23:50:47.546343 | systemd service finishes successfully. |

Service command: `/home/clay/projects/market-intel/.venv/bin/python -m src.run_daily_market_intel`. Its child command was `/home/clay/projects/market-intel/.venv/bin/python -m src.backtesting.build_backtest_events historical_sp500`. Journal PIDs: orchestrator 2584813, SEC refresh 2584818, builder 2609509. Direct service/project/journal evidence attributes this operation to the scheduled process; no manual or Codex command is needed to explain it. Shell history was unnecessary and was not inspected.

The builder cleared and recreated the historical population in one outer transaction, with per-security savepoints. All 14,742 current historical IDs are contiguous, 385246–399987; sequence last_value is 399987. All have created_at `2026-09-23 22:21:43.265306+00:00`, the transaction-start timestamp, **not** their individual insertion or commit time. The 502 xmin groups reflect event-bearing security subtransactions, not separate rebuilds. None of the old historical event IDs survives. The 83 rows outside the historical clear explain 14,825 total rows.

The earliest reliable evidence of the completed new population is the post-commit summary around 23:50:46 UTC. The saved preflight directly records all new counts at September 24 02:33:50 UTC. Our read-only repeatable-read snapshot at 02:51:28.833116 UTC matches that preflight's protected-table fingerprints. The exact commit instant is not separately logged.

## The new filing and five facts

General Mills Inc, GIS, company_id **612**, security_id **608**, CIK **0000040704**. Filing id **503172**, accession **0001628280-26-063201**, form **10-Q**, report period **2026-08-30**, filing date **2026-09-23**, accepted **2026-09-23 15:44:38Z** (11:44:38 EDT). It arrived through the scheduled SEC production refresh.

All five new facts belong to that company/security/accession, FY2027 Q1, period **2026-06-01 through 2026-08-30**, filed September 23, and are non-derived:

| Fact ID | Metric | SEC concept | Value/unit |
|---|---|---|---:|
| 3333748 | revenue | RevenueFromContractWithCustomerExcludingAssessedTax | 4,389,500,000 USD |
| 3333820 | net_income | NetIncomeLoss | 397,000,000 USD |
| 3333890 | diluted_eps | EarningsPerShareDiluted | 0.74 USD/shares |
| 3333962 | operating_income | OperatingIncomeLoss | 633,600,000 USD |
| 3333981 | operating_cash_flow | NetCashProvidedByUsedInOperatingActivities | 297,800,000 USD |

These are exactly the five rows whose created_at follows the repair commit; their created_at and updated_at match. Each matches exactly one cached SEC companyfacts record by concept, unit, accession, dates and value. Source records and cache SHA-256 are saved in local_source_confirmation.json. Net facts increased 173,028→173,033. This does not independently prove that the scheduled upserts changed no older fact values; a complete old fact-row snapshot is unavailable.

## The additional event

**ADBE**, security_id **149**, company_id **153**, CIK **0000796343**; current event **385482**, period_end **2026-08-28**, entry **2026-09-23**. No old historical stable keys disappeared; this is the sole added key.

Its revenue fact **3149184**, Revenues **6,760,000,000 USD**, already existed on September 22. Source filing **503171**, accession **0000796343-26-000156**, 10-Q filed September 22, was accepted at corrected **2026-09-22 16:04:02Z**. Both its old erroneous acceptance (20:04:02Z) and corrected acceptance produce September 23 entry under the existing methodology.

The scheduled price refresh added September 23 ADBE prices at 22:19:59.295943Z and SPY prices at 22:21:43.073501Z. These enabled the event. It is not caused by the GIS facts or an ADBE entry-date change, and is not an exact signal (acceleration 0.20, operating-margin change −1.47). GIS's new facts imply September 24 entry, for which prices were not yet available, so they do not add a GIS event.

## FTV and exact-signal reconciliation

FTV security **663**, company **667**, CIK **0001659166**, period_end **2026-04-03**, existed as old non-signal event **376253**, entry **2026-05-01**. Current event **390995** enters **2026-04-30**. Both link to revenue fact **481386** (1,069,400,000 USD), accession **0001659166-26-000013**, filing **94814**.

Correcting April 30 acceptance from **15:38:15Z** (11:38 EDT) to **11:38:15Z** (07:38 EDT) moves entry from May 1 to April 30. With the existing calculations and current inputs, the old-date 20-day excess return is **−2.72**, versus **+2.28** on the corrected entry. Current revenue acceleration is **63.96** and operating-margin change **2.08**. The timing shift alone is sufficient to explain qualification.

The old negative momentum is a **reconstruction**, not an archived original FTV field: the saved audit retained its timing link but not its full non-signal row. FTV's companyfacts cache and builder code are byte-identical to Git HEAD; the daily price importer only appended dates after its latest stored date, and logged one new FTV price. This supports timestamp correction as the cause, unrelated to the new GIS facts; historical vendor-price vintages remain a limitation.

The saved comparison reconciles **194→191 exact signals: 190 retained, four removed (REGN twice, SPG, TSN), one added (FTV)**. Current train/test counts are **142/49**. Stable membership-qualified event keys increased **14,741→14,742**. Among retained old event keys, entry-date shifts in calendar days are: unchanged 12,818; −1 day 1,458; −2 days 4; −3 days 435; −4 days 26. Detailed earlier comparison artifacts remain alongside this report.

## Deterministic verification and protected state

The new standalone investigation tool captures read-only inputs, then runs unchanged `build_security_events` for all 664 historical securities against in-memory leaf read adapters. The original save function's SQL parameters are captured by a fake cursor; it cannot write to PostgreSQL. Unexpected SQL, duplicate event keys, ambiguous input ordering, live DB connections and HTTP requests are rejected during replay. Captured inputs include 1,269,607 price rows and 121,277 relevant facts; replay took 2.685 seconds.

Result: **14,742 expected / 14,742 actual; zero missing, extra or differing events**, across all **31 builder-written fields**, including 30/90/180-day outcomes. Skip counts exactly match the scheduled log: 2,316 comparative, 18,817 timing, 2,032 membership, zero price. Builder journal errors/tracebacks: zero. This establishes consistency with corrected current timestamps, current facts/prices, existing historical membership and unchanged builder methodology, without a destructive rebuild.

All **29,837** repaired timestamps still match the pinned manifest's corrected values. All **1,260 excluded** entries remain unchanged: 984 already correct, 71 exceptional, 205 unresolved. No original manifest filing is missing. Total filings **31,098** (the original 31,097 plus GIS). Pinned manifest SHA-256: `f8bdc0b837287a2cd3d22a97115de268d1550863d72428b38a407c8ff9afed74`.

Paper account matches the repair receipt: **$10,000 cash, zero signals, zero positions**, immutable cutover **2026-09-20 10:32:26.133136Z**. Current companies, facts, events, paper tables and membership fingerprints match the saved preflight. No protected state changed during this investigation.

## Recommendation, limits and saved evidence

Accept the captured 14,742-event snapshot as the new **corrected-current-input baseline**. No additional rebuild is needed for the captured inputs. It is not a timestamp-only counterfactual: the scheduled job also refreshed SEC data and appended prices. Deterministic agreement verifies implementation consistency, not complete historical point-in-time provenance. Existing exceptional/unresolved timestamps, derived-fact lineage, historical ticker coverage and vendor-price-vintage limitations remain. Complete original non-signal metrics are not recoverable from the old timing-link evidence alone.

The existing weekday 17:00 Chicago timer remains configured and can replace the live historical dataset again. It was not modified; the saved snapshot is the reproducible baseline.

New code: `src/backtesting/investigate_event_provenance.py`; `tests/test_investigate_event_provenance.py`. No production code or methodology changed. Evidence created in this directory:

- `provenance_inputs.json.gz`: reproducible captured input snapshot.
- `deterministic_replay.json.gz`: expected events, comparisons, replay inputs/code hashes and FTV reconstruction.
- `provenance_summary.json`: counts, new facts, filing checks and event metadata.
- `provenance_verification.json`: protected-state verification, systemd configuration, chronology source hashes and FTV/ADBE rows.
- `journal_provenance.json`: filtered service/count/lifecycle evidence and journal stream hash.
- `local_source_confirmation.json`: cached SEC fact matches and source/code hashes.
- `provenance_tests.log`: offline regression results.
- This report.

Primary existing sources: successful repair receipt under `../acceptance_repair/execution_20260923_135745_721689/`; preflight `before_20260924_023350.json.gz`; saved sector-readiness audit; timestamp audit; `../../daily_market_intel_2026-09-23_17-00-04.log`; `../../sec-production/df2f9fba28cc47a5890cb798c40f2977.json`.

Validation: both new Python files compiled; **219 focused tests passed**, covering investigation adapters/capture, preflight, timestamp parsers/repair, SEC freshness, SIC cached replay, sector audit and paper regressions. Paper-run text in the test log is mocked test output, not a live paper run. No database writes, destructive rebuilds, external requests, SEC/price refreshes, live paper/orchestrator runs, notifications, migrations, service changes or commits were performed by this investigation. The scheduled job's earlier actions were observed through existing evidence only.
