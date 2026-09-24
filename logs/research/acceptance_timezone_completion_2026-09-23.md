# SEC timestamp audit — completion and signal-impact supplement

Date: 2026-09-23. Offline evidence only; database transactions read-only.

This report completes the existing [detailed timestamp investigation](acceptance_timezone_2026-09-23.md), which was already present and uncommitted when this task resumed. That report and all SIC pilot files were preserved unchanged. Its statement that momentum was not recomputed is superseded by the bounded 16-event counterfactual below. No parser or production change was made.

## Root cause and source semantics

`src/sec/import_universe_filings.py::parse_acceptance_datetime` slices the first 19 characters, parses a naive ISO clock, and attaches America/New_York. It discards explicit Z/offset information and fractional seconds. PostgreSQL stores the resulting incorrect instant correctly. For cached UTC submissions, this is a second, erroneous timezone conversion: +4 hours in daylight-saving time, +5 in standard time. It exactly reproduces 29,837 differing rows.

All 1,693,880 timestamp records encountered in 1,181 local submissions JSON files are explicit **Z/UTC**, including main recent and historical shard payloads. Repetitions across caches are included in that count. All 37 independent saved compact filing-header timestamps agree with submissions when interpreted as **Eastern wall time**, using the date's DST/standard offset. This supports distinct source parsing rules; it does not establish semantics for every possible unseen SEC format. No external documentation or SEC requests were fetched.

- Explicit ISO Z or numeric offset: preserve the supplied instant and normalize to UTC. Existing parser instead relabels the clock; matching Eastern offset strings only happen to work.
- Naive ISO: timezone is unspecified. The importer and `analysis.event_timing.normalize_acceptance_datetime` assume Eastern; no naive submissions values were observed in local caches. A future fix should require a source contract or quarantine them.
- Compact header `YYYYMMDDHHMMSS`: no offset encoded; saved header evidence establishes Eastern interpretation. The SIC pilot handles this separately. Ambiguous/nonexistent DST wall times need a policy rather than silent guessing.
- Companyfacts `filed`, submissions `filingDate`/`reportDate`, and financial period boundaries are dates, not instants. Do not derive them from UTC acceptance dates.
- Pilot `observed_at`, report start/end/snapshot time, database insertion/update time and cache filesystem times represent retrieval/processing, **not historical SEC availability**. Pilot historical lookup uses header acceptance, not retrieval time. A cache downloaded later is preserved source evidence, not proof that the entire current payload existed unchanged at the historical date.

## Writers and consumers

The repository has two timestamp writers:

1. `src/sec/import_universe_filings.py::save_filing`: INSERT plus ON CONFLICT UPDATE. Both historical `import_issuer_filings` and production `import_production_issuer_filings` reach this writer. Its parser is the defective path.
2. `src/sec/filing_importer.py::parse_recent_filings` → `src/sec/filing_repository.py::save_filings`: passes recent submissions strings directly to TIMESTAMPTZ, INSERT with ON CONFLICT DO NOTHING. Z/offset strings preserve the instant; naive strings depend on database session timezone.

No header/index reader writes this column. Companyfacts and other financial sources do not supply it. No other repository writer was found. The earlier catalog audit recorded TIMESTAMPTZ, no timestamp default, and no user trigger/rule writer; arbitrary historical external SQL cannot be reconstructed. Internal production fallback metadata uses an explicit Eastern offset, derived from the stored instant, and does not independently validate it. Production reuse can retain erroneous stored values. `json_cache.validate_columns` and the submissions completeness check also only validate the 19-character prefix.

Direct consumers: `analysis/event_timing.py`, historical `backtester.py` and `build_backtest_events.py`, `paper_trading/paper_execution.py`, `paper_trading/paper_trading_engine.py`, `sec/production_requirements.py`, document/exhibit ordering in `sec/filing_document.py` and `sec/import_recent_exhibits.py`, and the readiness/SIC research audits. Timing changes propagate into event membership, prices, returns, momentum, aggregate research scores and candidate selection.

## Reproduced database scope

The fresh snapshot at **2026-09-23 13:10:57 UTC** exactly matches the earlier snapshot's filing details, 194-event details and aggregate counts. All **31,097** filings have acceptance values; **30,892** are cache-comparable; **205** lack unambiguous cached evidence. **29,908** differ, across **497 companies**.

| Database minus cached instant | Rows |
|---|---:|
| 0 hours | 984 |
| +4 hours | 19,829 |
| +5 hours | 10,008 |
| +8 hours | 39 |
| +10 hours | 32 |
| Unmatched | 205 |

Affected filing-date range: **2009-04-15–2026-09-22**. Forms: 22,587 10-Q; 7,181 10-K; 115 10-Q/A; 23 10-K/A; one 10-QT; one 20-F. Per-company/per-accession evidence is in the compressed JSON. **16,766 UTC dates change** and **3,582 calendar candidate-entry dates change**. There are **zero matched filingDate disagreements**. Inspected Companyfacts/financial repository paths retain source date-only `filed`; no adjacent timezone conversion was found. This is not a complete audit of every financial filed_date.

The 71 +8/+10-hour rows belong to **CIEN (24)** and **TTWO (47)**. Their source values are also explicit UTC. One invocation of today's parser does not reproduce these larger shifts; repeated erroneous conversion is a hypothesis, not established write provenance. The 205 unmatched rows include 132 DELL rows. Never repair either group through blanket offset subtraction.

## Historical and exact-signal impact

The entry function converts the instant to Eastern, chooses the same calendar date before 09:30 and the following calendar date otherwise, then looks up the next observed price session within seven days. Across 14,741 stored membership-qualified events, 14,712 current-revenue links are comparable: zero change availability at the original decision clock, but **1,925 calendar entry candidates change**. Actual trading-session changes for the whole event universe were not replayed.

For the committed readiness audit's **194 exact-signal events**, the original acceptance audit was reproduced with zero baseline entry-date mismatches:

- **Zero demonstrated financial-input availability changes**, both at original decision times and at replayed corrected entry times.
- Revenue dependencies covered for **193/194**; operating-margin dependencies for **194/194**. MA event **379033**, fact **15564**, accession **0001141391-19-000013**, remains unverified. Thus one event is partially unresolved, not conclusively unaffected.
- Derived-lineage limitations remain: 85 revenue and 25 margin cases. Correct timestamps do not prove unavailable lineage.
- **16 entries move one session earlier**: 14 train, two test. None crosses the existing 2023-12-31/2024-01-01 split, and all 16 retain historical S&P membership at corrected entry. No current-membership substitution was used.
- The existing growth/margin functions select inputs by financial period, not acceptance timestamp. A timestamp-only correction leaves their reconstructed numeric values unchanged. Observed availability flags also remain unchanged; this is not an endorsement of their broader as-of methodology or derived lineage, and no new input-selection methodology was introduced.

The new supplement uses the existing `get_trailing_return` and exact-signal predicate to replay 21 prior closes for the stock and SPY at both dates. All 16 original momentum values reproduce exactly; all 32 stock/SPY windows align in dates. **Four events lose qualification solely because corrected-entry excess return is no longer >0.** They are REGN twice, SPG and TSN, all training events.

| Event ID | Security label | Original → corrected entry | Original → corrected excess (pp) | Still qualifies? |
|---|---|---|---:|---|
| 376687 | GPN | 2019-05-03 → 2019-05-02 | 3.08 → 1.76 | Yes |
| 373584 | CNP | 2019-08-08 → 2019-08-07 | 0.29 → 2.37 | Yes |
| 377989 | J | 2020-02-05 → 2020-02-04 | 3.77 → 2.04 | Yes |
| 376728 | GRMN | 2020-10-29 → 2020-10-28 | 5.32 → 2.03 | Yes |
| 381964 | REGN | 2021-05-07 → 2021-05-06 | 2.11 → -2.12 | **No** |
| 373591 | CNP | 2021-05-07 → 2021-05-06 | 2.37 → 1.69 | Yes |
| 374653 | DOV | 2021-07-21 → 2021-07-20 | 8.41 → 3.88 | Yes |
| 376731 | GRMN | 2021-07-29 → 2021-07-28 | 4.77 → 2.69 | Yes |
| 382699 | SPG | 2021-08-05 → 2021-08-04 | 1.27 → -0.41 | **No** |
| 381965 | REGN | 2021-08-06 → 2021-08-05 | 2.27 → -1.88 | **No** |
| 374980 | ECL | 2021-08-06 → 2021-08-05 | 1.46 → 2.07 | Yes |
| 383683 | TSN | 2021-08-10 → 2021-08-09 | 5.39 → -4.90 | **No** |
| 381967 | REGN | 2022-02-08 → 2022-02-07 | 7.13 → 8.21 | Yes |
| 382199 | ROP | 2022-05-05 → 2022-05-04 | 2.28 → 2.59 | Yes |
| 370770 | ADI | 2025-05-23 → 2025-05-22 | 1.89 → 12.50 | Yes |
| 377168 | HPE | 2026-06-03 → 2026-06-02 | 89.79 → 59.25 | Yes |

Under the existing builder's price-symbol mapping and unchanged financial features, **190 of the original 194 remain threshold-qualified**. This is a fixed-cohort sensitivity result, not the size of the fully corrected signal universe: events outside the original sample might newly qualify. No event rebuild, forward-return recalculation or performance claim was made.

**Identity caveat:** 15 of the 16 changed entries lack a dated ticker-history row; J has one. The counterfactual deliberately reproduces the current builder's stored price-symbol lookup to isolate timestamp impact, and does not assert that current ticker labels prove historical identity. Stable security IDs and the available history remain in evidence. Resolving missing history is separate from this timestamp correction.

## Prospective trading, freshness and SIC validity

Read-only measurements show cutover **2026-09-20 10:32:26.133136 UTC**, zero paper signals, zero positions and zero cutover crossings among comparable filings. There are no recorded commitments/trades to revise. Unmatched rows are not proven by source timestamps. Preserve cutover and never manufacture retrospective paper trades.

Future exposure remains: wrong acceptance times affect future/pre-cutover rejection, first eligible session, freshness requirements and today's stored-entry candidate selection. `stored_valid` tests metadata presence/awareness, not SEC timestamp agreement; refreshing production alone can reuse bad timestamps. A SEC freshness PASS does not certify timestamp correctness. No live production decision, paper execution, service or orchestrator was run.

The **SIC pilot remains valid as saved header/SIC feasibility evidence**: all 37 raw hashes and parsed observations verify; the existing offline tests replay all 395 lookups. The supplemental comparison finds **zero source-selection changes at the original 40 sampled decision clocks among cache-comparable filings**. This does not certify unmatched filing eligibility or corrected-entry coverage for all 395 events. Header instants are already correctly interpreted, but event-dependent coverage, issuer mapping, sparse observation limitations and corrected decision clocks must be reviewed before expansion. Preserve the pilot; do not treat it as validated full-history sector labels or commit/expand it yet.

## Recommended separately approved correction

1. Parse full submissions ISO values, respecting Z and numeric offsets and preserving fractions; normalize to UTC. Reject malformed suffixes and unresolved naive input. Keep explicitly Eastern header parsing separate; test DST folds/gaps. Apply consistent semantics to both writers and validators, including production reuse/fallback checks.
2. Build a dry-run correction manifest keyed by CIK/accession and row ID, with old/new values, source path/hash and classification. Repair from authoritative instants, never by subtracting four/five hours. Review the 71 exceptional and 205 unmatched rows separately; obtain only specifically approved extra evidence if necessary.
3. Preserve database backups and research snapshots. Following explicit approval, use bounded transactional updates with old-value preconditions, expected row counts, rollback evidence and after-verification. Do not alter filing dates, fact values, immutable cutover or paper records as collateral changes.
4. **Backtest events require rebuilding/recomputation after approved repair.** At least 16 sample entries and four signal memberships change; previously skipped or currently nonqualifying events also need consideration. Authorize the expensive rebuild separately, preserve validated thresholds, formulas, historical identity/membership and train/test boundaries, then rerun research comparisons.
5. Validate prospective freshness/cutover/no-catch-up behavior offline before an authorized live validation. Timestamp repair alone does not resolve the existing derived-fact lineage and ticker-history uncertainties.

## Artifacts, reproduction and validation

New this turn:

- `src/backtesting/audit_acceptance_signal_impact.py` — bounded read-only supplement; hard bound of 20 changed entries and expected 194-event input, 15-second SQL statement timeout.
- `tests/test_audit_acceptance_signal_impact.py` — three offline tests.
- `logs/research/acceptance_timezone_2026-09-23_131057.json.gz` — fresh full read-only scope snapshot.
- `logs/research/acceptance_signal_impact_2026-09-23_131228.json` — price windows, corrected qualification, historical membership/ticker evidence, header hashes and input-artifact SHA-256 hashes.
- This completion report: `logs/research/acceptance_timezone_completion_2026-09-23.md`.

All files that were already uncommitted at the start remain intact, including the main timestamp audit code/tests, both older timestamp snapshots/report, and all SIC pilot files. No tracked production files changed.

Reproduction (local database only):

```sh
PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=15000' .venv/bin/python -m src.backtesting.audit_acceptance_timezone
PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=15000' .venv/bin/python -m src.backtesting.audit_acceptance_signal_impact
.venv/bin/python -m unittest tests.test_audit_acceptance_signal_impact tests.test_audit_acceptance_timezone tests.test_audit_sector_readiness tests.test_sec_sic_pilot
```

**32 tests passed**, including all 37 cached header replays and 395 saved SIC lookups. Python compilation passed for both timestamp audit scripts and test files; `git diff --check` passed (new files are untracked). Fresh and prior scope summaries, all filing details and exact-event details compare equal. Both initial sandbox database attempts failed with suppressed OperationalError; approved local read-only reruns succeeded. Some source-discovery searches used nonexistent paths and were corrected; no validation test failed.

No external requests, SEC/price refreshes, database updates/migrations, event rebuilds, full-universe price replay, paper trading, orchestration, notifications, service changes or commits were performed. Remaining decisions: approval and exceptional-row evidence for parser/data repair; separate approval for rebuild; separate research decisions on lineage and identity gaps. Full corrected-universe signal count/performance remains unknown.
