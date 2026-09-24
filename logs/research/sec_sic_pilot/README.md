# SEC SIC historical-classification pilot — 2026-09-23

## Decision

Continue this approach in stages, but **do not yet scale downloads to the whole universe or use these results as validated historical sector labels**. Filing headers provide reproducible, issuer-specific SIC evidence. Resolve acceptance-time normalization and dated security/issuer mapping first, then validate former issuers and complete intervening observations. This is SEC SIC research, not GICS, and no SIC-to-GICS conversion is proposed.

## Artifacts and reproduction

- `pilot_2026-09-23_052233.json`: canonical detailed snapshot; 15 security inventories, 395 event lookups, 37 parsed observations, mapping evidence, source URLs, acceptance/filing/observation times and hashes.
- `pilot_2026-09-23_051959.json`: initial 40-date retrieval snapshot; preserves the original retrieval accounting.
- `headers/*.json`: 37 cached public SEC filing-header responses with retrieval timestamps and SHA-256 hashes. No request headers or credentials are stored.
- Code: `src/backtesting/sec_sic_pilot.py`; tests: `tests/test_sec_sic_pilot.py`.

Offline evidence replay and parser/lookup tests: `.venv/bin/python -m unittest discover -s tests -p test_sec_sic_pilot.py`. Replay verifies the cached hashes, parsed observations and all 395 saved lookups without contacting SEC or the database.

Database refresh of the fixed pilot inventory, using cached evidence only: `PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=15000' .venv/bin/python -m src.backtesting.sec_sic_pilot`. This creates a new isolated report snapshot. `--fetch` permits missing header retrieval only; the pilot caps requests at 40, response size at 256 KiB and checks a 90-second elapsed bound between requests. An in-flight request may extend that elapsed bound. Access denial/rate limiting stops retrieval. Existing SEC identity, shared pacing/cooldown and atomic JSON caching are reused; the existing JSON-only HTTP wrapper cannot parse HTML, so a small header adapter is isolated here.

This run made **37 SEC requests**, with no failures. The subsequent all-event measurement reused the cache and made **zero requests**. Database transactions were read-only; no schema, production data, signal, sector-confidence or backtest calculation changed.

## Prior findings and isolated artifact design

Used the saved `../sector_readiness_2026-09-22_220915.md` and JSON rather than rerunning the audit. Its research universe has 14,741 events, 502 event-bearing securities and 664 historical members. Existing sector values are not point-in-time. This pilot does not populate or read those values for classification.

The proposed pilot persistence is JSON only, with three logical records: security inventory keyed by stable `security_id` (including available issuer/ticker history); observation keyed by CIK/accession (SIC, description, historical acceptance, source URL, retrieval time, hash); event lookup keyed by existing event ID (decision time, identity evidence, selected observation and qualifications). No migration is necessary. A later database design would keep issuer observations separate from effective-dated security-to-issuer relationships and preserve source/ingestion time separately from historical availability.

## Selection and measured coverage

Selection was fixed for identity/business/data diversity, not returns or signal performance. For each event-bearing security, retrieve headers for the first, middle and last event; additionally include the known GEN/NLOK event on 2020-08-07. These 40 security-event dates require 37 unique filings because GOOG and GOOGL share an issuer. All events below satisfy existing historical S&P membership at entry. Exact-signal counts use the unchanged thresholds: revenue acceleration >=20, margin change >0, pre-entry 20d excess return >0. No performance returns were measured or used to choose the sample.

| Security (stable ID) | Diversity reason | Events / exact signal | Sampled dates | Observed SIC |
|---|---|---:|---:|---|
| AAPL (2) | Ordinary issuer | 35 / 2 | 3 | 3571 |
| MSFT (4) | Ordinary issuer, different business | 35 / 0 | 3 | 7372 |
| JPM (11) | Bank | 35 / 0 | 3 | 6021 |
| FE (503) | Utility | 34 / 0 | 3 | 4911 |
| GEN (686) | SYMC/NLOK/GEN identity | 33 / 1 | 4 | 7372 |
| META (7) | FB/META change | 35 / 0 | 3 | 7370 |
| GOOG (7468) | Class C | 35 / 1 | 3 | 7370 |
| GOOGL (3) | Class A, same CIK as GOOG | 35 / 1 | 3 | 7370 |
| GE (33) | Restructuring/spinoff parent | 35 / 0 | 3 | 3600 |
| GEHC (440) | Separate spinoff security | 13 / 0 | 3 | 3844 |
| EXC (344) | Spinoff parent | 33 / 1 | 3 | 4931 |
| CEG (179) | Separate spinoff security | 18 / 2 | 3 | 4911 |
| FLT (10433) | Historical name/ticker; missing-sector case | 19 / 1 | 3 | 7389 |
| ATVI (10411) | Acquired former constituent | 0 / 0 | 0 | UNKNOWN/not tested |
| TWTR (10462) | Delisted former constituent | 0 / 0 | 0 | UNKNOWN/not tested |

- 15 selected securities, 14 current mapped CIKs; 13 event-bearing securities and 12 observed issuers.
- 395 existing events, 9 exact-signal matches, spanning 2018-02-01 through 2026-08-10. Two of the 40 sampled event dates are exact-signal matches.
- **40/40 sampled dates have exactly one latest supported SIC**, no SIC conflicts or unknown issuer-SIC lookups. Observation ages are 0–3 whole days.
- Applying the same strictly-prior lookup to all existing dates gives **395/395 one supported sampled classification**, zero ambiguous/unknown SIC lookups. This is conditional issuer-SIC coverage, NOT independently certified historical security classification.
- **260/395** use evidence older than 365 days; maximum age **1,480 days**. The other filings between samples were not fetched. “Latest supported” means latest among this pilot's evidence, not proven latest in all SEC filings. Do not interpret this 100% lookup rate as full-history completeness.
- **0/395** have a proven effective-dated issuer relationship in the existing mapping table. All 395 use a unique issuer corroborated by the event-period revenue fact and its linked timely filing. This is useful existing database evidence, not independent validation of that historical mapping.
- **350/395** lack a ticker relationship with an explicit start date covering the event. Current ticker is a display label only. Open-start SYMC/FB records are preserved but not assumed proven for arbitrarily early dates.
- ATVI and TWTR have **zero existing filings and zero events** in this snapshot. They are included in the mapping inventory, not fabricated as event observations. Historical SEC retrieval for these former issuers remains untested; this is a genuine sample limitation.

## Evidence, identity exceptions and availability

Lookup uses entry-date **09:30 America/New_York** as the pilot decision cutoff and accepts only observations strictly before it. It never uses the later retrieval date as historical availability, never backdates later SIC evidence and never substitutes current submissions SIC. Headers must match both accession and the appropriate CIK's filer block, avoiding accidental selection of a co-filer's SIC. Conflicting latest codes are AMBIGUOUS; missing prior evidence is UNKNOWN. The tests exercise both outcomes even though neither occurred in the measured issuer-SIC lookups.

For GEN security 686, the 2020-08-07 event retains the dated ticker **NLOK**, CIK **0000849399** and accession **0000849399-20-000007**. The header supports SIC **7372, SERVICES-PREPACKAGED SOFTWARE**, accepted **2020-08-06 16:37:22 EDT**, before the decision cutoff. The stable security ID is unchanged. The inventory also preserves SYMC and GEN intervals without inventing a start date for SYMC.

GOOG/GOOGL retain separate security IDs while sharing CIK 0001652044 and filing observations. GE/GEHC and EXC/CEG remain separate securities and issuers; no parent's older SIC is assigned to a child before its own evidence. FLT's events map through existing historical facts to CIK 0001175454, but the repository has no ticker or issuer interval for that security; no FLT-to-new-ticker consolidation was attempted. That requires explicit identity review before scaling.

### Material timestamp discrepancy

**All 37 header acceptance instants differ from database acceptance instants.** The database is later by four hours in 27 cases and five hours in 10. Both values are retained rather than silently reconciled.

Concrete independently cached example, GEN accession `0000849399-26-000031`:

- Historical header: `2026-08-07 16:03:52 America/New_York` = `20:03:52Z`.
- Existing submissions cache: `2026-08-07T20:03:52.000Z`.
- Database: `2026-08-08 00:03:52+00:00`.

`src/sec/import_universe_filings.py::parse_acceptance_datetime` discards the suffix and interprets the first 19 characters as Eastern time. That behavior explains this example's extra four hours. This pilot is not a full timestamp-import audit and does not claim to establish every row's import path. All 40 sampled requested filings are before their selected decision cutoff under both timestamps, but selecting candidate filings from shifted database times can omit eligible same-day evidence elsewhere. Historical entry dates may also depend on those stored times. Investigate separately before trusted research expansion; **no timestamps or event dates were repaired here**.

## What this does and does not establish

Filing headers reproducibly support SIC observations known before the chosen decision times. No observed issuer changes SIC across the sparse samples, including GE's restructuring dates. Thus this pilot does **not empirically validate a real SIC transition**, nor establish SIC's economic sensitivity to a restructuring. SIC is an issuer-level administrative classification, not GICS or an assurance of diversified modern industry groupings.

A defensible future research history can treat each accepted filing observation as evidence available from that instant onward, never infer a change at an earlier corporate-action date, and use the latest supported observation at decision time. It must explicitly state its filing scope and observation gaps. This pilot retrieved selected regular annual/quarterly filings, not every filing form or every intervening quarter. A change discovered later cannot be retroactively assigned to earlier events.

Material prerequisites: timestamp normalization review, dated issuer identity or reviewed evidence-backed mappings, complete relevant observation coverage, and testing former issuers plus at least one actual classification transition. Missing ticker display history alone is a reporting limitation when stable identity is independently sound; missing issuer history is more serious. Sparse carried-forward observations are acceptable for feasibility measurement only, not claims of fully validated point-in-time sector coverage. Prior audit limitations in signal input provenance and outcome methodology remain unresolved and are not repaired by SIC coverage.

## Recommended next work and scale estimate

1. Separate bounded investigation of timestamp normalization using cached submissions and these headers. Agree on any corrective action and affected research scope before changing trusted import behavior or historical data.
2. Resolve dated security/CIK identity for this sample, especially FLT and corporate actions; obtain limited former-issuer evidence for ATVI/TWTR, which have no local filings. Keep separate share classes and spinoffs separate.
3. Complete the relevant filing history for these 12 observed issuers, plus the two former issuers, and deliberately test an actual documented SIC change. Re-measure unknown/conflict/staleness counts and compare filing-scope choices before selecting a full methodology.
4. Only after review, design isolated effective-dated observation/mapping tables or durable research artifacts, offline import/replay, versioned sources, coverage gates and conflict review. No changes to `analysis_universe_members.sector` or production sector confidence.
5. Expand in resumable batches to 502 event-bearing securities first, then inventory all 664 members. Deduplicate by CIK/accession. At most one requested regular filing per event suggests roughly 14,741 candidate requests before deduplication, not a measured full download requirement; prior observations and all-form coverage could change it. At the existing 0.25-second pacing floor that order of magnitude is about one hour of pacing alone, excluding latency, retries and manual review. Do not initiate as an ordinary test.

Estimated engineering scope: several focused work stages—timestamp review, identity review, complete pilot, then batch importer/coverage reporting—not merely a larger invocation of this pilot. Calendar duration cannot be estimated reliably until former-issuer and transition cases are tested. Nothing measured warrants abandoning SIC as a free research classification source. If coarse SIC categories cannot answer the intended diversification question, or ambiguous identity cannot be resolved with available evidence, retain UNKNOWN/exclude transparently rather than force classifications or mislabel SIC as GICS.

## Validation and safety

Focused offline tests cover issuer/accession validation, missing/conflicting fields, strict pre-decision availability, latest-observation selection, no backdating, conflicting latest codes, issuer isolation, disabled/exhausted retrieval and complete saved-evidence replay. **12 tests passed**; `py_compile` passed for both added Python files; `git diff --check` passed (the additions remain untracked until user review). No full-universe imports, event rebuilds, production jobs, paper trading, notifications, migrations or commits were run. Only isolated pilot code/tests/report artifacts were added.
