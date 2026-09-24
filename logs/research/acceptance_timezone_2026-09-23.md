# SEC acceptance timestamp investigation — 2026-09-23

## Conclusion

The universe filing importer systematically misinterprets explicit UTC SEC submissions timestamps as Eastern wall-clock time. The bug is established from cached source values, the current parser, database rows and independent pilot headers. **29,837 rows exactly reproduce a single erroneous conversion; another 71 rows have larger unexplained shifts.** Do not apply a blanket four/five-hour subtraction.

No parser, production behavior, historical data, event, signal definition or schema was changed. No external requests were made. The 37 pilot requests were not repeated. This audit is not approval to migrate data or rebuild events.

## Reproduction and evidence

- Audit code: `src/backtesting/audit_acceptance_timezone.py`.
- Tests: `tests/test_audit_acceptance_timezone.py`.
- Canonical detailed evidence: `acceptance_timezone_2026-09-23_123358.json.gz` (losslessly compressed JSON).
- Initial measurement: `acceptance_timezone_2026-09-23_122141.json.gz`; retained for provenance. The canonical version additionally checks availability at corrected entry dates.
- Prior dependency inventory: `sector_readiness_2026-09-22_220915.json`; not regenerated. Event identity, dates, exact-signal values and saved fact dependencies were checked against the current database before reuse.
- Independent headers: `sec_sic_pilot/headers/` and `sec_sic_pilot/pilot_2026-09-23_052233.json`.

Command: `PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=15000' .venv/bin/python -m src.backtesting.audit_acceptance_timezone`. It uses a read-only repeatable-read transaction and writes only a new audit artifact. It scans local cache files only: bound 2,000 files / 700 MB, filing-row bound 300,000, statement timeout 15 seconds. This run read 1,181 cache files, about 448 MB. Do not invoke a SEC importer to reproduce these measurements. The initial sandbox connection failed with a safely suppressed OperationalError; the explicitly approved read-only local connection succeeded.

Canonical snapshot: **2026-09-23 12:33:58.255463 UTC**. Session timezone **Etc/UTC**. Catalog inspection also confirmed `filings.acceptance_datetime` is `timestamp with time zone`, with no default; `filing_date` and `report_date` are DATE. There are no user triggers or rules on `filings` providing another write path.

## Every repository writer and source

| Path | Input | Behavior |
|---|---|---|
| `src/sec/import_universe_filings.py::save_filing` | SEC submissions recent/history records | Calls `parse_acceptance_datetime`; INSERT and ON CONFLICT UPDATE both write the parsed acceptance value. |
| Same module, historical `import_issuer_filings` branch | Cached recent/history through `get_submission_records` | Calls `save_filing` for matched target accessions; an import can overwrite previously correct acceptance values. |
| Same module, production `import_production_issuer_filings` branch | Production submissions loader/recovered history | Calls `save_filing` for uncovered validated records. Already-populated stored metadata is reused, not source-checked or repaired. |
| `src/sec/filing_importer.py::parse_recent_filings` → `src/sec/filing_repository.py::save_filings` | `sec_client.get_company` recent submissions | Passes the timestamp string directly to PostgreSQL TIMESTAMPTZ. Explicit Z/offset strings retain their instant; naive values would depend on session TimeZone. INSERT only, ON CONFLICT DO NOTHING. |

Repository search found no other INSERT/UPDATE/COPY writer of this column, and no timestamp migration in the current migrations. Creation code declares the column but supplies no timestamp default. Ad-hoc SQL or historical external maintenance cannot be reconstructed from current source alone.

`production_requirements.select_requirements` creates an internal fallback representation using `stored_timestamp.astimezone(EASTERN).isoformat()`. That is an explicit Eastern offset, not UTC. The current production importer skips already-covered accessions, so this fallback is not evidence of a repeated timestamp write. It also cannot establish that stored values were correct in the first place.

Filing/index/header timestamps are **not a current production source feeding this column**. The SIC pilot parses the original header's compact `YYYYMMDDHHMMSS` wall-clock value as America/New_York into isolated report observations. Filing document/exhibit readers consume stored filing metadata but do not write acceptance times. Companyfacts provide date-only `filed` values, not this timestamp.

## Format semantics and parser behavior

The 1,693,880 timestamp records encountered in local submissions cache files (including repetitions across cache files, not unique database rows) are all **explicit Z** timestamps. No timezone-naive or explicit nonzero-offset submissions values were encountered in those files. All 37 independent historical header instants agree with their corresponding explicit-UTC cached submissions instants.

| Format | Correct interpretation | Current universe parser |
|---|---|---|
| `2026-08-07T20:03:52.000Z` | Explicit UTC | Truncates at 19 characters; labels 20:03:52 as Eastern, storing 00:03:52Z next day. |
| ISO with `+00:00` | Explicit UTC | Same erroneous relabeling. |
| ISO with `-04:00` / `-05:00` | Explicit fixed-offset instant | Ignores suffix; happens to agree when clock/offset match Eastern on that date, but loses explicit offset disambiguation. |
| Other explicit offsets | Respect supplied offset | Incorrectly discards the offset. |
| Naive ISO timestamp | Source contract required | Assumes Eastern, regardless of provenance. No such submissions value was observed locally. |
| Compact header timestamp | Eastern wall clock in the saved header evidence | Not accepted by this ISO parser; the separate pilot parser handles it. |

The parser also drops fractional seconds and ignores malformed suffixes after the first 19 characters. `json_cache.validate_columns` and the production submissions loader's completeness check likewise validate only that prefix; they do not establish timezone correctness.

This is timezone **relabeling**, not an unavoidable TIMESTAMPTZ conversion. PostgreSQL correctly stores the wrong instant supplied to it. The dominant error is +4 hours in DST and +5 in standard time. Near DST transitions, applying Eastern rules to the UTC-looking clock rather than the original instant makes “subtract the local offset” an unsafe general repair. Naive ambiguous fall-back times and nonexistent spring-forward times need explicit policy/evidence, not an arbitrary fold assignment.

Concrete GEN example: accession `0000849399-26-000031`, header **16:03:52 EDT**, cached submissions **20:03:52.000Z**, database **00:03:52Z on August 8**. The header and cache identify the same August 7 instant; the parser exactly explains the extra four hours.

## Measured database scope

All **31,097** filing rows have acceptance times. **30,892** can be compared to unambiguous explicit cached evidence; **205** cannot. No conflicting cached instants were found for matched CIK/accession pairs. Matching uses company CIK and accession, not just ticker or accession prefix.

| Database minus cached-source instant | Rows |
|---|---:|
| 0 hours | 984 |
| +4 hours | 19,829 |
| +5 hours | 10,008 |
| +8 hours | 39 |
| +10 hours | 32 |
| Not comparable | 205 |

- **29,908** differing rows across **497 companies**.
- Affected filing dates: **2009-04-15 through 2026-09-22**.
- Forms: 10-Q **22,587**; 10-K **7,181**; 10-Q/A **115**; 10-K/A **23**; 10-QT **1**; 20-F **1**.
- **16,766** corrections change the UTC calendar date.
- **3,582** change the calendar candidate-entry date returned by the existing timing function. This is not necessarily a change of observed trading session.
- **0 filing-date disagreements** between matched database rows and cached `filingDate` values. No filing_date correction is justified by these measurements.
- The 205 unmatched rows include 132 DELL rows; the detailed artifact identifies all cases. None has a filing date on/after 2026-09-19, but a date alone is not independent acceptance-time evidence.

### Exceptional +8/+10-hour rows

CIEN: **24 rows** (13 at +8, 11 at +10), filing dates 2020-12-18–2026-09-03. TTWO: **47 rows** (26 at +8, 21 at +10), 2015-02-06–2026-08-07. A single invocation of the current parser on the saved cache does **not** reproduce these rows. Their offsets resemble two erroneous relabelings, but no second write path or historical repair operation was established. There is no local evidence that these SEC records use a different timestamp format: they are explicit Z too. Their exact write-history root cause remains **unresolved**, and they require separate review before a migration. No external headers were requested to resolve them.

## Historical research and availability impact

`event_timing.get_candidate_entry_date` converts acceptance to Eastern, uses same-day entry before 09:30 and next-calendar-day otherwise. The next observed symbol price within seven days chooses the actual entry. `build_backtest_events.get_entry_date` uses that path for each current-reporting revenue fact, then checks historical membership, computes stock/SPY forward outcomes and pre-entry momentum. Moving an acceptance time earlier can change all these derived results and occasionally train/test or membership inclusion.

The fundamental growth/margin calculations use stored metric histories without a comprehensive as-of filter on every dependency. The readiness audit's fact-availability checks diagnose this limitation; they are not production gates that the historical builder already enforces. Correcting a timestamp does not fix missing derived-fact lineage or validate all historical inputs.

Across the existing **14,741 historical events**, there is one joined current-revenue fact per event. **14,712** are cache-comparable; **29** are not. Among comparable links:

- **0** change current-revenue timestamp availability at the original entry-day 09:30 Eastern decision time.
- **1,925** change the calendar candidate-entry date. Actual price-session replay for the whole universe was deliberately not performed; weekends/holidays can collapse different candidates to the same session.

The audit does not claim an all-dependency as-of test for all 14,741 events. That expensive broader work was outside this bounded investigation; full dependency checks are confined to the saved exact-signal sample.

### Exact 194-signal sample

Unchanged thresholds: revenue acceleration >=20%, operating-margin improvement >0, pre-entry 20d SPY excess >0. Training remains through 2023-12-31, testing from 2024-01-01. All 194 stored events match the saved audit's identity, entry date and signal fields. Their current entry dates are reproduced exactly by the existing timing/price-date lookup (zero baseline mismatches).

At the **original decision times**:

- **0 observed events** change any compared dependency's timestamp availability.
- Revenue dependencies are fully cache-comparable for **193/194** events; operating-margin dependencies for **194/194**.
- The one unverified revenue dependency is MA event **379033**, entry **2019-05-01**, fact **15564**, accession **0001141391-19-000013**. Its timestamp is retained, not guessed. Thus this is **zero demonstrated changes, one partially unverified event**, not a proof of zero changes across every input of all 194.
- No component changes late/missing/direct-availability classification among the compared evidence. Existing derived-lineage limitations remain: revenue 85 events; operating margin 25.

After source-normalizing the current revenue acceptance and replaying **only the existing price-date entry selection**, **16/194** enter one session earlier: **14 train, 2 test**. The component late/direct-availability flags still do not change at those corrected decision dates, subject to the same MA gap. No momentum or returns were recomputed. Earlier entries can change the >0 momentum qualification, so the final corrected exact-signal cohort and its performance are **not established** by this audit.

| Security | Stored entry → corrected entry |
|---|---|
| GPN | 2019-05-03 → 2019-05-02 |
| CNP | 2019-08-08 → 2019-08-07 |
| J | 2020-02-05 → 2020-02-04 |
| GRMN | 2020-10-29 → 2020-10-28 |
| REGN | 2021-05-07 → 2021-05-06 |
| CNP | 2021-05-07 → 2021-05-06 |
| DOV | 2021-07-21 → 2021-07-20 |
| GRMN | 2021-07-29 → 2021-07-28 |
| SPG | 2021-08-05 → 2021-08-04 |
| REGN | 2021-08-06 → 2021-08-05 |
| ECL | 2021-08-06 → 2021-08-05 |
| TSN | 2021-08-10 → 2021-08-09 |
| REGN | 2022-02-08 → 2022-02-07 |
| ROP | 2022-05-05 → 2022-05-04 |
| ADI | 2025-05-23 → 2025-05-22 |
| HPE | 2026-06-03 → 2026-06-02 |

None of these 16 crosses the train/test boundary. The older audit's calendar-day horizon and historical ticker limitations are preserved, not silently corrected.

## Prospective paper trading and production

Measured account: cutover **2026-09-20 10:32:26.133136 UTC**, cash **$10,000**, **0 signals, 0 positions**. No pending commitments can exist with zero signals. **Zero compared filing rows cross that cutover after normalization**. There are no recorded trades or commitments to revise. The already-completed paper no-op is not shown invalid by this audit; this is not a rerun of the production decision at its historical clock time.

Risk nevertheless exists going forward. `paper_execution.freshness_reason` uses acceptance for the cutover/future-time gate and first-session candidate. `paper_trading_engine` selects events for today's stored entry date, then computes observed-session checks from the same possibly shifted timestamp. A delayed candidate can therefore admit a commitment on a later session than the correctly timed first eligible session, or defer/exclude valid evidence. A pre-cutover filing could in principle appear post-cutover; none was measured among compared rows here. Corrections must not manufacture retroactive commitments or change the immutable cutover.

SEC production freshness is also affected. `production_requirements.potentially_current` uses acceptance to exclude pre-cutover/future filings, calculate candidate windows and eliminate stale sessions. A shifted timestamp can alter what metadata is considered mandatory. `stored_valid` only checks issuer/date/aware-time presence, not agreement with SEC evidence; `import_production_issuer_filings` reuses such metadata. The report's PASS asserts successful refresh and resolution of the selected requirements, **not timezone correctness**. Re-running the existing refresh is not a repair strategy.

Other consumers include `analysis.event_timing` timing reports, historical `backtester`, and filing-document/recent-exhibit selection ordered by acceptance. Incorrect times can affect sort order when corrected and uncorrected rows mix or near boundaries. Scoring/sector confidence can change indirectly after research events and performance are corrected. Current pipeline timestamp-dependent decisions should not be treated as fully validated until the correction is approved and tested; no services or schedules were touched here.

## Date-only fields and related parsing

SEC submissions `filingDate`/`reportDate` and Companyfacts `filed`/period start/end are date-only fields. The inspected import paths parse ISO dates or pass them to PostgreSQL DATE; they should not be converted through UTC or replaced by `acceptance_datetime.date()`. Filing date can legitimately differ from acceptance UTC date. Financial repository preserves the source `filed` date; derived financial calculations can propagate/max source filing dates, which is a lineage concern, not evidence of this timezone bug. This investigation did not rescan all Companyfacts payloads to certify every historical filed_date.

## Proposed correction — requires approval, not implemented

1. Add source-aware parsing: ISO submissions values with Z or numeric offsets must preserve the supplied instant, normalize to UTC and retain fractional seconds. Reject malformed suffixes. Treat naive submissions values as unresolved unless a documented source contract and tests establish their timezone; there were none in these caches. Keep compact historical-header parsing as explicitly Eastern, with a policy for ambiguous/nonexistent DST wall times. Do not impose one guessed timezone on all formats.
2. Route both filing writers and completeness validators through consistent semantics. Preserve explicit Eastern fallback metadata correctly. Add UTC, offsets, fractions, summer/winter and DST boundary tests plus a production reuse/source-consistency regression. Do not rely on “tzinfo exists” as provenance validation.
3. Prepare a **dry-run, accession+CIK keyed correction manifest from authoritative cached instants**, including row ID, old/new values, source and integrity hash. Snapshot/backup affected data and old research artifacts. Review the 71 exceptional rows and 205 unmatched rows separately; seek approval for narrowly targeted external evidence only if needed. Never mass-subtract four/five hours, and do not modify dates, cutover or paper records as collateral work.
4. After explicit approval, apply a bounded transactional data repair with old-value preconditions, row-count checks, rollback plan and immutable before/after audit. Verify the parser cannot reintroduce the error. Merely rerunning production refresh would reuse bad values.
5. **Existing backtest events need rebuilding/recomputation after an approved correction**, because at least 16 exact-signal entries demonstrably change. The complete affected universe may include membership/timing-skipped events not present today. Obtain separate authorization for the expensive rebuild, preserve the same validated formulas, and then re-run time-split/signal/readiness comparisons. Do not assert corrected performance or start within-sector validation using stale event timing.
6. Validate prospective timing/cutover/no-catch-up behavior offline against corrected evidence before another authorized live validation. Never backfill paper trades. Only then resume SIC expansion and approve use of historical classifications.

## Validation and files

Added only `src/backtesting/audit_acceptance_timezone.py`, `tests/test_audit_acceptance_timezone.py`, this report and the two compressed machine-readable audit snapshots. Existing uncommitted SIC pilot artifacts were left unchanged. The generated JSONs were losslessly compressed to avoid unnecessary repository bulk; `gzip.open(..., 'rt')` reads them directly.

Tests: **11 new offline timestamp tests passed**, **6 readiness-audit tests passed**, **12 SIC-pilot tests passed**. Both new Python files compiled successfully. No external calls, SEC/price refreshes, migrations, database writes, event rebuilds, paper trading, daily orchestration, notifications or commits occurred. Root cause is proven for the dominant +4/+5-hour population; exact historical write provenance for the 71 larger shifts and source evidence for 205 rows remain open.
