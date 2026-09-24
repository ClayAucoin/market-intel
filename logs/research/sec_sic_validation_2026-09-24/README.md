# Second bounded SEC SIC validation — 2026-09-24

**Result:** two actual within-CIK SIC changes were verified; former issuers ATVI and TWTR remain retrievable and classifiable at issuer level. The inclusive latest-observation rule passes offline boundary/replay checks. SEC SIC is technically viable as a versioned issuer-observation source, but broad point-in-time security classification is **not yet validated**. Dated security/issuer identity and filing-scope completeness remain gates. Recommend only the next bounded validation stage described below.

## Frozen baseline, scope and selection

Used the saved corrected snapshot (14,742 membership-qualified historical events; 191 exact signals), its provenance report, canonical first SIC pilot and committed sector-readiness audit. No database connection, event rebuild, signal re-evaluation/performance study or refresh was performed. The live database may evolve under its existing scheduler; all event measurements here refer to the accepted frozen snapshot. Current/undated analysis_universe_members.sector labels were not used. Classification throughout is **SEC SIC, not GICS**; no SIC-to-GICS mapping is made.

Examined **31 stable securities / 30 CIKs**, including the original 15 securities. Added transition candidates XYZ, KKR, BX, TPL, ROP, DHR, FTV, MMM, HON, AXON, IBM, WBD; then LHX, JCI, EMR and ETN. Selection targeted company-name changes/reorganizations and varied businesses, not returns or signal outcomes. First/last locally catalogued annual filings screened candidates; intermediate annual/quarterly requests narrowed only detected changes. Same-code endpoints do not prove no intervening transition or reversal.

All **37 committed pilot header fixtures** were reused and hash-verified, without repeated requests. Added **75 headers and two submissions responses**, separately cached here. Total verified header observations: **112**. Canonical first-pilot artifacts remain untouched; their 395 old-event lookup results are historical evidence, not silently relabeled as this study’s corrected event sample.

## Verified transitions

Local security/company bindings are corroborated by saved financial-fact/company/filing joins and matching SEC CIK/name. They are not independently proven effective-dated security relationships. HON/JCI tickers below are display labels: no dated ticker rows support their historical use in this snapshot. Each transition is within one verified issuer CIK, not a switch from parent to spinoff or between CIKs.

### HON: 3714 → 3724

Security_id **256**, company_id **260**, CIK **0000773840**, issuer **HONEYWELL INTERNATIONAL INC**.

- Last verified old SIC: **3714 — MOTOR VEHICLE PARTS & ACCESSORIES**; 10-Q, accession **0001628280-19-004415**, filed 2019-04-18, accepted **2019-04-18T08:30:42-04:00**. [SEC filing header](https://www.sec.gov/Archives/edgar/data/773840/000162828019004415/0001628280-19-004415-index-headers.html).
- First verified new SIC: **3724 — AIRCRAFT ENGINES & ENGINE PARTS**; 10-Q, accession **0000773840-19-000013**, filed 2019-07-18, accepted **2019-07-18T08:29:25-04:00**. [SEC filing header](https://www.sec.gov/Archives/edgar/data/773840/000077384019000013/0000773840-19-000013-index-headers.html).
- The effective administrative change date is **unknown**. Evidence bounds a change between these observed filings; neither a unique transition nor uninterrupted old/new classification throughout the gap is established. New SIC is usable in this observation history only from the first verified new acceptance onward. Unexamined earlier 8-K/other-form evidence could narrow that boundary; it must be verified before use.

### JCI: 7380 → 3585

Security_id **197**, company_id **201**, CIK **0000833444**, issuer **Johnson Controls International plc**.

- Last verified old SIC: **7380 — SERVICES-MISCELLANEOUS BUSINESS SERVICES**; 10-K, accession **0000833444-21-000046**, filed 2021-11-15, accepted **2021-11-15T10:23:32-05:00**. [SEC filing header](https://www.sec.gov/Archives/edgar/data/833444/000083344421000046/0000833444-21-000046-index-headers.html).
- First verified new SIC: **3585 — AIR COND & WARM AIR HEATING EQUIP & COMM & INDL REFRIG EQUIP**; 10-Q, accession **0000833444-22-000005**, filed 2022-02-02, accepted **2022-02-02T10:48:59-05:00**. [SEC filing header](https://www.sec.gov/Archives/edgar/data/833444/000083344422000005/0000833444-22-000005-index-headers.html).
- The effective administrative change date is **unknown**. Evidence bounds a change between these observed filings; neither a unique transition nor uninterrupted old/new classification throughout the gap is established. New SIC is usable in this observation history only from the first verified new acceptance onward. Unexamined earlier 8-K/other-form evidence could narrow that boundary; it must be verified before use.

## Point-in-time lookup behavior

The isolated research rule is: select the latest verified observation for the resolved CIK with **acceptance <= decision cutoff**. Actual event cutoffs are entry-date **09:30 America/New_York**, matching the corrected historical entry-open convention. Explicit header Eastern wall times are normalized through the corrected source-specific parser. Retrieval timestamps (September 24, 2026) are stored separately and never determine historical availability.

The first pilot intentionally used strict `<`; this study tests the user-requested inclusive `<=` boundary in separate code. Neither the pilot nor production methodology was changed. Exact-acceptance, one-microsecond-before/after and weekend/Monday probes are labeled synthetic; actual event probes use saved event dates. A synthetic Monday clock does not certify an exchange session or holiday calendar.

| Issuer | Last actual event before new evidence | SIC | First actual event at/after new evidence | SIC |
|---|---|---:|---|---:|
| HON | 2019-04-18T09:30:00-04:00 | 3714 | 2019-07-18T09:30:00-04:00 | 3724 |
| JCI | 2021-11-16T09:30:00-05:00 | 7380 | 2022-02-03T09:30:00-05:00 | 3585 |

Immediately before each first-new acceptance the old observation wins; at and after it the new observation wins. The new code remains the latest observed code across the following weekend and Monday probe. Honeywell’s first-new filing was pre-open, so the July 18, 2019 event can use it; JCI’s was after open, and the February 3, 2022 event uses it. Repeated same-SIC filings refresh observation age; conflicting codes at the same latest instant return AMBIGUOUS, including timestamps written with equivalent different offsets. Missing prior evidence returns UNKNOWN. A long gap remains CLASSIFIED-as-last-observed with explicit age and continuity_proven=false, not proof of continuous classification.

## Observation density and lookup coverage

Across **803 sampled corrected events**, issuer-level lookups yielded **795 CLASSIFIED, 8 UNKNOWN, zero AMBIGUOUS**. These are conditional on the local security/CIK associations, not 795 independently validated security classifications. Unknowns have no sampled observation before the event: LHX two (2018-02-01, 2018-05-04); JCI three (2018-02-05, 2018-05-04, 2018-08-03); EMR three (2018-02-08, 2018-05-03, 2018-08-09). They are sampling gaps, not evidence SEC lacks those filings.

**519/795 classified lookups carry an observation older than 365 days.** The threshold is a descriptive count, not a new rejection policy. Sparse endpoint samples are deliberately unsuitable for broad completeness claims.

| Dense window (filing dates) | Verified / catalogued 10-K & 10-Q | Gap median / max days | Events with prior evidence | Event observation age median / max days |
|---|---:|---:|---:|---:|
| HON 2018-01-01 to 2022-01-01 exclusive | 16/16 | 90.97 / 120.22 | 16/16 | 0.042 / 3.836 |
| JCI 2020-01-01 to 2024-01-01 exclusive | 16/16 | 91.01 / 133.93 | 16/16 | 0.972 / 2.979 |

Both windows independently reconcile with locally cached submissions catalogues: 16 regular filings each, no missing accession. This establishes completeness for **that catalogue and selected forms**, not for every SEC filing or original historical retrieval vintage. Honeywell’s catalogue also contains 64 8-Ks in its window; JCI’s contains 44. These other-form headers were not fetched. The 91-day typical regular-filing spacing and 120–134-day maximum gaps bound observation frequency, not effective classification dates.

Full-sample density follows. Gaps are between unique acceptance instants; event ages are measured at actual event cutoffs. GOOG/GOOGL share issuer observations but retain separate security IDs. All days are elapsed calendar days.

| Display labels (security IDs) | CIK | Obs. | Gap median / max | Events: classified / unknown | Age median / max |
|---|---|---:|---:|---:|---:|
| JPM (11) | 0000019617 | 3 | 1540.98 / 1556.00 | 35 / 0 | 728.71 / 1461.72 |
| EMR (199) | 0000032604 | 2 | 2548.05 / 2548.05 | 32 / 3 | 1041.26 / 2451.74 |
| GE (33) | 0000040545 | 3 | 1532.27 / 1542.01 | 35 / 0 | 728.13 / 1456.13 |
| IBM (63) | 0000051143 | 2 | 2918.95 / 2918.95 | 35 / 0 | 1246.64 / 2795.64 |
| MMM (188) | 0000066740 | 2 | 2916.96 / 2916.96 | 35 / 0 | 1265.64 / 2812.64 |
| LHX (325) | 0000202058 | 2 | 2725.87 / 2725.87 | 30 / 2 | 1312.21 / 2621.69 |
| DHR (109) | 0000313616 | 2 | 2925.92 / 2925.92 | 35 / 0 | 1247.58 / 2799.58 |
| AAPL (2) | 0000320193 | 3 | 1550.44 / 1554.50 | 35 / 0 | 726.06 / 1463.64 |
| ATVI (10411) | 0000718877 | 3 | 989.99 / 1005.03 | 0 / 0 | — / — |
| HON (256) | 0000773840 | 21 | 91.01 / 370.98 | 35 / 0 | 3.78 / 257.83 |
| MSFT (4) | 0000789019 | 3 | 1550.48 / 1555.00 | 35 / 0 | 728.72 / 1464.72 |
| JCI (197) | 0000833444 | 20 | 91.14 / 366.00 | 31 / 3 | 2.93 / 260.90 |
| GEN (686) | 0000849399 | 4 | 915.95 / 1463.00 | 33 / 0 | 479.65 / 1385.73 |
| ROP (390) | 0000882835 | 2 | 2923.05 / 2923.05 | 35 / 0 | 1258.68 / 2809.72 |
| FE (503) | 0001031296 | 3 | 1494.47 / 1520.94 | 34 / 0 | 691.22 / 1457.69 |
| AXON (324) | 0001069183 | 2 | 2917.20 / 2917.20 | 13 / 0 | 2258.69 / 2805.74 |
| EXC (344) | 0001109357 | 3 | 1504.10 / 1550.17 | 33 / 0 | 724.82 / 1480.03 |
| FLT (10433) | 0001175454 | 3 | 1015.03 / 1096.02 | 19 / 0 | 455.72 / 1005.69 |
| META (7) | 0001326801 | 3 | 1550.02 / 1553.93 | 35 / 0 | 727.69 / 1463.53 |
| BX (91) | 0001393818 | 2 | 2920.00 / 2920.00 | 12 / 0 | 2303.19 / 2810.73 |
| KKR (165) | 0001404912 | 2 | 2926.00 / 2926.00 | 9 / 0 | 2447.70 / 2816.70 |
| TWTR (10462) | 0001418091 | 3 | 806.97 / 812.01 | 0 / 0 | — / — |
| WBD (250) | 0001437107 | 2 | 2921.09 / 2921.09 | 18 / 0 | 2031.24 / 2808.76 |
| XYZ (339) | 0001512673 | 2 | 2920.99 / 2920.99 | 5 / 0 | 160.68 / 2809.72 |
| ETN (99) | 0001551182 | 2 | 2920.11 / 2920.11 | 35 / 0 | 1252.82 / 2806.86 |
| GOOG,GOOGL (3,7468) | 0001652044 | 3 | 1544.49 / 1548.02 | 70 / 0 | 728.53 / 1464.53 |
| FTV (663) | 0001659166 | 2 | 2919.84 / 2919.84 | 33 / 0 | 1339.49 / 2800.49 |
| TPL (542) | 0001811074 | 2 | 1819.00 / 1819.00 | 7 / 0 | 1455.71 / 1714.71 |
| CEG (179) | 0001868275 | 3 | 773.47 / 816.90 | 18 / 0 | 319.34 / 728.82 |
| GEHC (440) | 0001932393 | 3 | 550.00 / 554.00 | 13 / 0 | 189.13 / 463.13 |

## Former issuers: distinct outcomes

ATVI and TWTR each have **zero events and zero local filings** in the frozen baseline. Their public submissions and historical filing headers nevertheless retrieved successfully after their current submissions ticker arrays became empty. Therefore “no events,” “no local evidence” and “SEC unavailable” are demonstrably different outcomes. Retrieval uses CIK/accession, not a currently traded symbol. This study does not reconstruct missing events or infer trading/delisting dates from ticker-array emptiness.

| Former issuer | Stable ID / CIK | Verified SIC observations (acceptance date: code) | Status |
|---|---|---|---|
| ATVI | 10411 / 0000718877 | 2018-02-27: 7372; 2020-10-29: 7372; 2023-07-31: 7372 | Public issuer identity resolved; SIC classified; dated security binding still unproven |
| TWTR | 10462 / 0001418091 | 2018-02-23: 7370; 2020-05-05: 7370; 2022-07-26: 7370 | Public issuer identity resolved; SIC classified; dated security binding still unproven |

All six former-issuer accession/form/acceptance/source/hash records are in results.json. ATVI: 0001047469-18-001114 (10-K), 0001628280-20-015105 (10-Q), 0001628280-23-026269 (10-Q). TWTR: 0001564590-18-003046 (10-K), 0001418091-20-000089 (10-Q), 0001418091-22-000147 (10-Q). There were no unretrievable former-issuer responses in this study. Historical issuer SIC can be looked up at hypothetical cutoffs; there are no actual baseline events for these two securities to classify.

## Identity findings and unresolved cases

- **GEN/NLOK/SYMC (686, CIK 0000849399):** cached headers independently corroborate changing issuer names under the same CIK. Saved dated NLOK/GEN ticker intervals are retained; SYMC’s open-start interval is not treated as proven for arbitrary earlier dates. The historical NLOK case remains supported by the saved ticker interval.
- **META/FB (7, CIK 0001326801), LHX/HRS (325, CIK 0000202058):** headers corroborate issuer-name continuity/change; saved ticker intervals are used only where they have an explicit start. Neither an undated current ticker nor a header former-name date independently proves a historical ticker boundary.
- **XYZ (339, CIK 0001512673):** headers identify Square, Inc. and Block, Inc. under the same CIK. No dated ticker rows exist here, so XYZ is display-only; no historical SQ/XYZ effective date is invented.
- **GOOG (7468) / GOOGL (3):** distinct security IDs share CIK 0001652044 and the same three issuer observations. Do not merge the two security histories or claim the header alone proves their historical share-class mapping.
- **GE (33) / GEHC (440), EXC (344) / CEG (179):** distinct CIKs and named filers are verified; parents’ observations are never carried into children. Spinoff lineage/effective ownership is not established merely by these headers.
- **FLT (10433):** fact-based CIK 0001175454 and FLEETCOR header name corroborate the issuer, but dated ticker/issuer intervals remain absent. No consolidation with another security or later ticker was performed.
- **TPL (542):** only its local CIK 0001811074 corporation evidence from 2021 onward was sampled. A predecessor trust/new-CIK continuity mapping was not inferred.
- **Ordinary issuers (AAPL/MSFT/JPM/FE and others):** accession/CIK/name checks succeed. Matching current company/fact joins still do not independently prove a dated security relationship.

Across the sample, **732/803 events lack an explicitly started local ticker interval**. No independently proved dated security→issuer binding was established for any of the 31 securities; the new source evidence verifies the issuer, while binding it to a local security remains corroborated rather than legally/historically certified. This limitation is separate from the eight missing-prior-observation UNKNOWNs. Header business names are not substitutes for share-class identifiers or effective-dated corporate-action evidence.

## Viability and recommended next bounded stage

Proceed with a **larger but gated research stage**, not universe-wide classification or production integration: ten unique CIKs with two-year dense windows (approximately 80 regular headers), plus at most 40 additional issuer-filing headers around the two observed transition intervals and identity cases, for a hard cap of **120 new requests**, preferably in batches of at most 40. Include these two transitions, both former issuers, a shared-class issuer, a parent/child pair and a ticker-change case. This expands dense validation beyond two issuers, not the production universe.

Before that stage, predefine acceptable issuer-filing forms and independent dated security/CIK evidence. Prioritize 8-K/other issuer filings between the last-old/first-new observations to learn whether regular-only sampling misses an earlier usable code. Do not automatically treat insider Form 4 subject-company metadata as equivalent to issuer-filer evidence. Preserve UNKNOWN and conflicts, and report age rather than inventing a stale-observation certainty rule. No sector-group thresholds or investment signal changes are recommended.

Remaining limits: two transitions are not a statistical estimate of transition frequency; equal endpoints can hide changes/reversals; observations do not reveal the true effective-change date; all-form completeness and historical issuer/security bindings are unproven; current SEC responses are retrieved now rather than contemporaneously archived copies. Filing acceptance supplies the proposed availability clock, while retrieval is a separate provenance clock. Existing financial-lineage, price-vintage, exceptional/unresolved timestamp and ticker limitations from the baseline reports remain unchanged.

## Requests, files and validation

Hard cap consumed: **80 request attempts**. Ledger records **77 HTTP 200 responses (75 new headers + 2 submissions)**, one HTTP 503, and two connection failures (one initial sandbox failure, one later connection failure). Successful evidence was cached before resumptions; no successful URL was fetched twice. The 503 was retried once in a later bounded batch. Failed attempts remain in the cap. No 401/403/429 occurred. The number of failed connection attempts that reached SEC cannot be established; 78 attempts returned HTTP responses.

Used project SEC identity, shared pacing/cooldown helpers and three-attempt-per-URL limit; batches stop on errors/access denial, with bounded response sizes/timeouts. No further requests after the cap. No commercial data source was used. New evidence is confined to this research directory, outside production caches.

New source: src/backtesting/sic_validation_study.py. New tests: tests/test_sic_validation_study.py. Artifacts here: README.md; results.json (all 803 lookups, 112 observations, transition probes, identity and density evidence); local_inventory.json and supplemental_inventory.json; density_catalog_crosscheck.json; plan_01.json through plan_04.json; requests.json; 75 header/*.json; two submissions/*.json; validation.json; ignored offline_tests.log. No existing source, test, pilot fixture or production cache was changed.

**38 focused offline tests passed** (nine new plus pilot, timestamp, readiness and provenance checks), including all saved header hashes, all 803 event lookups and all transition probes. Both new Python files compile. git diff --check passes. Synthetic tests cover no prior evidence, wrong issuer, inclusive boundary/no backdating, repeated codes, long gaps, equivalent-offset ambiguity, transition bounds, density and request guards. All 37 original pilot fixtures and its 395 saved lookups also pass unchanged.

No database access/writes, migration, event rebuilding, production SEC/price refresh, live paper trading/orchestrator, notification, signal change, membership/split/horizon change, cutover alteration, commit or push occurred. The 80 bounded research attempts are the only external operation.
