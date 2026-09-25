# Bounded SEC acceptance-source discrepancy investigation

**Finding:** all 22 Stage 3 ATVI/TWTR discrepancies are genuine differences between saved SEC source representations. The raw submissions JSON contains a `Z` value whose clock fields exactly equal the compact filing-header Eastern clock. Project extraction did not introduce the difference. The source-specific parser correctly honors the explicit representation; that does not make the represented instant correct. Do not globally reinterpret `Z`, reopen the approved safe repair, or change production code from this finding.

**A related current-issuer finding matters:** five independently checked, already-excluded CIEN/TTWO filings show the same pattern in the original audit cache. New SEC submissions values agree with these headers wherever present. The old audit classified those rows as exceptional +8/+10-hour differences, not safe repairs. One corroborated TTWO filing changes a saved event’s calendar candidate date. No event rebuild, price-session check, momentum calculation, database access, repair, SIC expansion, commit or push occurred.

**Scope and evidence.** Read the accepted Stage 3 README/results/validation and processing code; the original timestamp audit/completion and repair proposal/execution reports; source parsers, caching/import paths; and corrected-baseline/provenance reports. The working tree was clean at the start of this task. Examined 22 former-issuer pairs, 103 existing current-issuer control pairs, seven targeted new headers (five excluded rows and two safe controls), all 71 excluded manifest records by saved/new source comparison, and compact saved event links. The 205 unresolved rows were inventoried from the manifest, not repaired or broadly fetched. The original audit’s 37 independent header checks were reviewed as prior evidence, not rerun as a whole historical audit.

**Requests:** 10 attempts, nine HTTP 200 successes (seven headers and two raw submissions responses), one sandbox connection failure. The 20-attempt ceiling includes that failure. The initial eight-response plan was extended by one header only after a single candidate-date discrepancy appeared. Every attempt was persisted before the call; successful responses were reused; no production cache was written. All new responses and their exact-byte SHA-256 values are in this directory. No further retrieval is needed for this report.

**The exact 22 discrepancies.** Difference is `parsed header UTC minus parsed submissions UTC`. `EST/+5h` means 18,000 seconds and Eastern UTC offset −05:00; `EDT/+4h` means 14,400 seconds and offset −04:00. Every row is exactly consistent with the Eastern offset at its acceptance date: nine EST and thirteen EDT, zero exceptions. Filing dates are preserved independently; Twitter’s February 19, 2020 filing was accepted on February 18, and no date was synthesized from a UTC timestamp.

| Issuer / CIK | Accession | Form | Filing date | Exact submissions value | Exact compact header | Parsed submissions UTC | Parsed header UTC | DST / delta |
|---|---|---|---|---|---|---|---|---|
| ATVI / 0000718877 | 0001104659-21-012239 | 8-K | 2021-02-04 | `2021-02-04T16:12:05.000Z` | `20210204161205` | 2021-02-04T16:12:05+00:00 | 2021-02-04T21:12:05+00:00 | EST / +5h |
| ATVI / 0000718877 | 0001628280-21-002828 | 10-K | 2021-02-23 | `2021-02-23T16:19:41.000Z` | `20210223161941` | 2021-02-23T16:19:41+00:00 | 2021-02-23T21:19:41+00:00 | EST / +5h |
| ATVI / 0000718877 | 0001308179-21-000286 | DEF 14A | 2021-04-30 | `2021-04-30T17:28:32.000Z` | `20210430172832` | 2021-04-30T17:28:32+00:00 | 2021-04-30T21:28:32+00:00 | EDT / +4h |
| ATVI / 0000718877 | 0001628280-21-008889 | 10-Q | 2021-05-04 | `2021-05-04T16:34:25.000Z` | `20210504163425` | 2021-05-04T16:34:25+00:00 | 2021-05-04T20:34:25+00:00 | EDT / +4h |
| ATVI / 0000718877 | 0001628280-21-015351 | 10-Q | 2021-08-03 | `2021-08-03T16:40:04.000Z` | `20210803164004` | 2021-08-03T16:40:04+00:00 | 2021-08-03T20:40:04+00:00 | EDT / +4h |
| ATVI / 0000718877 | 0001628280-21-021200 | 10-Q | 2021-11-02 | `2021-11-02T16:33:40.000Z` | `20211102163340` | 2021-11-02T16:33:40+00:00 | 2021-11-02T20:33:40+00:00 | EDT / +4h |
| ATVI / 0000718877 | 0001104659-22-004729 | 8-K | 2022-01-18 | `2022-01-18T09:28:00.000Z` | `20220118092800` | 2022-01-18T09:28:00+00:00 | 2022-01-18T14:28:00+00:00 | EST / +5h |
| ATVI / 0000718877 | 0001628280-22-003992 | 10-K | 2022-02-25 | `2022-02-25T16:21:05.000Z` | `20220225162105` | 2022-02-25T16:21:05+00:00 | 2022-02-25T21:21:05+00:00 | EST / +5h |
| ATVI / 0000718877 | 0001628280-22-011987 | 10-Q | 2022-05-03 | `2022-05-03T16:08:50.000Z` | `20220503160850` | 2022-05-03T16:08:50+00:00 | 2022-05-03T20:08:50+00:00 | EDT / +4h |
| ATVI / 0000718877 | 0001628280-22-019955 | 10-Q | 2022-08-01 | `2022-08-01T16:24:44.000Z` | `20220801162444` | 2022-08-01T16:24:44+00:00 | 2022-08-01T20:24:44+00:00 | EDT / +4h |
| ATVI / 0000718877 | 0001628280-22-028658 | 10-Q | 2022-11-07 | `2022-11-07T16:28:12.000Z` | `20221107162812` | 2022-11-07T16:28:12+00:00 | 2022-11-07T21:28:12+00:00 | EST / +5h |
| TWTR / 0001418091 | 0001418091-20-000019 | 8-K | 2020-02-06 | `2020-02-06T07:01:00.000Z` | `20200206070100` | 2020-02-06T07:01:00+00:00 | 2020-02-06T12:01:00+00:00 | EST / +5h |
| TWTR / 0001418091 | 0001418091-20-000037 | 10-K | 2020-02-19 | `2020-02-18T17:53:51.000Z` | `20200218175351` | 2020-02-18T17:53:51+00:00 | 2020-02-18T22:53:51+00:00 | EST / +5h |
| TWTR / 0001418091 | 0001140361-20-008934 | DEF 14A | 2020-04-15 | `2020-04-15T16:17:33.000Z` | `20200415161733` | 2020-04-15T16:17:33+00:00 | 2020-04-15T20:17:33+00:00 | EDT / +4h |
| TWTR / 0001418091 | 0001418091-20-000089 | 10-Q | 2020-05-05 | `2020-05-05T16:21:46.000Z` | `20200505162146` | 2020-05-05T16:21:46+00:00 | 2020-05-05T20:21:46+00:00 | EDT / +4h |
| TWTR / 0001418091 | 0001418091-20-000158 | 10-Q | 2020-08-03 | `2020-08-03T16:30:17.000Z` | `20200803163017` | 2020-08-03T16:30:17+00:00 | 2020-08-03T20:30:17+00:00 | EDT / +4h |
| TWTR / 0001418091 | 0001418091-20-000202 | 10-Q | 2020-10-30 | `2020-10-30T16:17:59.000Z` | `20201030161759` | 2020-10-30T16:17:59+00:00 | 2020-10-30T20:17:59+00:00 | EDT / +4h |
| TWTR / 0001418091 | 0001193125-21-016213 | 8-K | 2021-01-25 | `2021-01-25T16:00:55.000Z` | `20210125160055` | 2021-01-25T16:00:55+00:00 | 2021-01-25T21:00:55+00:00 | EST / +5h |
| TWTR / 0001418091 | 0001418091-21-000031 | 10-K | 2021-02-17 | `2021-02-17T16:52:20.000Z` | `20210217165220` | 2021-02-17T16:52:20+00:00 | 2021-02-17T21:52:20+00:00 | EST / +5h |
| TWTR / 0001418091 | 0001418091-21-000085 | 10-Q | 2021-04-30 | `2021-04-30T16:16:53.000Z` | `20210430161653` | 2021-04-30T16:16:53+00:00 | 2021-04-30T20:16:53+00:00 | EDT / +4h |
| TWTR / 0001418091 | 0001418091-21-000155 | 10-Q | 2021-07-27 | `2021-07-27T16:44:05.000Z` | `20210727164405` | 2021-07-27T16:44:05+00:00 | 2021-07-27T20:44:05+00:00 | EDT / +4h |
| TWTR / 0001418091 | 0001418091-21-000209 | 10-Q | 2021-10-27 | `2021-10-27T17:00:25.000Z` | `20211027170025` | 2021-10-27T17:00:25+00:00 | 2021-10-27T21:00:25+00:00 | EDT / +4h |

Each machine-readable row additionally records numeric seconds/hours, Eastern offset, DST boolean, exact wall-clock equality, source paths/URLs, raw source hashes and repair category. Both original representations are retained unchanged. Original raw submissions are the committed Stage 2 `submissions/CIK0000718877.json` and `CIK0001418091.json` wrappers; their `raw_json` hashes validate. Their arrays reproduce the Stage 3 catalogue strings exactly. All 22 verified source rows are in the main response’s `filings.recent`, despite being historical filings.

**Code-path trace and source semantics.**

- `sic_validation_study.fetch`: collects response bytes, decodes UTF-8, hashes the original bytes and stores the unchanged string in `raw_json`; `json.loads` is used for CIK validation, not timestamp conversion. No timezone relabeling is performed while saving either submissions or headers.
- `sic_stage3.prepare`: reads the raw submissions JSON and copies each `acceptanceDateTime` array element directly into compact catalogue rows. This was checked against the retained raw responses for all 22 cases. `catalog_discrepancy` merely compares parsed instants. Neither path writes back to source evidence.
- `parse_submissions_acceptance`: parses explicit ISO Z/offset and normalizes the supplied instant to UTC. That contract is working as written; interpreting `16:19:41Z` as `21:19:41Z` would be a source correction, not ordinary ISO parsing. A valid suffix is insufficient evidence that a supplier encoded the correct instant.
- `parse_header_acceptance`: interprets the offset-free compact EDGAR clock as America/New_York, validates DST folds/gaps and converts to UTC. The compact field itself contains no timezone suffix; the Eastern interpretation is the established source contract, corroborated here by 103 agreeing current-issuer controls and the fresh matching CIEN/TTWO submissions. It is not a claim that the compact text literally spells out Eastern.
- `sec_http.get_sec_json` → `sec_submissions.download_json` → `json_cache.atomic_json`: decodes JSON, validates it and reserializes values without rewriting acceptance strings. `columnar_to_records` copies values. Validation checks explicit syntax, not cross-source timestamp accuracy. Existing stored-metadata fallback renders an explicit Eastern offset and is not the origin of these saved Z strings.
- `import_universe_filings.parse_acceptance_datetime/save_filing` and `filing_repository.save_filings` use the submissions parser when writing timestamps. They do not independently corroborate headers. Thus a source-mislabeled Z can yield a wrong historical availability instant even with the corrected parser. The previous importer defect—discarding a genuine UTC suffix and relabeling its clock Eastern—remains a distinct, established bug.

For ATVI/TWTR the raw HTTP-body fixtures directly establish that the project received the inconsistent strings. For the older CIEN/TTWO audit caches, the exact manifest-pinned serialized JSON is recoverable at Git revision f8ff747e0edc3435d0376ea9119483531e26e784. All 71 stored source strings match those original cache objects. Those caches do not retain their original HTTP response bodies, so byte-level transport attribution for that older vintage is weaker. The inspected caching paths do not perform the transformation, and no project-created source change was found. The new responses are saved verbatim, so their present values are independently auditable. We cannot determine the SEC’s internal cause or when that source representation changed from these records.

**Current-issuer controls and period patterns.** All 103 overlapping Stage 3 current-issuer pairs agree exactly under the unchanged source-specific rules:

| Issuer | Existing header/submissions pairs | Exact agreements | Filing years |
|---|---:|---:|---|
| AAPL | 11 | 11 | 2021–2022 |
| HON | 22 | 22 | 2018–2019 |
| JCI | 14 | 14 | 2021–2022 |
| META | 12 | 12 | 2021–2022 |
| GOOGL | 11 | 11 | 2021–2022 |
| GE | 11 | 11 | 2023–2024 |
| GEHC | 11 | 11 | 2023–2024 |
| FLT | 11 | 11 | 2020–2021 |

These controls comprise 58 main-response records and 45 historical-shard records, spanning 2018–2024. Current issuers agree in the same 2020–2022 years in which the former-issuer sample disagrees. The targeted exceptional headers extend the inconsistent original-cache pattern to current issuers and 2015–2026. Therefore it is neither uniquely a former-issuer problem, a single filing-year problem, nor simply “old historical shards are wrong.” The observed association is with particular issuer/payload vintages: ATVI/TWTR main responses retained the anomalous representation; older CIEN/TTWO main caches did too, while their older safe-control shard records and the newer main responses agree with headers. This is a bounded purposive sample, not a prevalence estimate or a universal per-endpoint rule.

**Repair-manifest intersection.** The original pinned manifest hash remains `f8bdc0b837287a2cd3d22a97115de268d1550863d72428b38a407c8ff9afed74`.

| Original repair category | Entire original population | The 22 ATVI/TWTR accessions |
|---|---:|---:|
| Safely repaired | 29,837 | 0 |
| Already correct, excluded | 984 | 0 |
| Exceptional, excluded | 71 | 0 |
| Unresolved, excluded | 205 | 0 |
| Absent from manifest | — | 22 |

There are also zero manifest rows for either former CIK, and the saved corrected baseline contains zero ATVI/TWTR filing rows, events or financial-provenance rows. This demonstrates absence from the examined saved population, not absence from a live database that was not queried. Stage 3 used header times, so its SIC conclusions remain unchanged.

The 103 current controls intersect 63 safely repaired rows; the other 40 accessions are absent from the manifest. Both targeted near-boundary safe controls also agree: CIEN `0000936395-20-000036` and TTWO `0001047469-14-008670`. Thus **65 independently header-checked safe rows show no contradiction**. No safely repaired row is identified as wrong by this investigation. This does not independently certify all 29,837 rows: the original safe criterion reproduced the old parser relative to source strings, and could not detect every theoretically possible mislabeled source. There is no evidence here warranting a blanket rollback, reinterpretation or reopening of the approved repair.

**What the original exceptions now show.** The audit already contained the same source representation in CIEN’s 24 exceptional rows (2020-12-18 through 2026-09-03) and TTWO’s 47 (2015-02-06 through 2026-08-07). It recorded database-minus-ISO differences of eight/ten hours and correctly excluded them because one invocation of the known old parser did not reproduce the database value. It did not have independent CIEN/TTWO headers, so it did not diagnose this source pattern then; repeated conversion was only a hypothesis. Its 37 original header checks all agreed and included neither former issuer nor CIEN/TTWO.

| New independent header | Original category | Old cache → header UTC delta | Saved DB → header UTC delta |
|---|---|---:|---:|
| CIEN 0000936395-20-000042 | exceptional_offset | +5h | +5h |
| CIEN 0001628280-26-060361 | exceptional_offset | +4h | +4h |
| CIEN 0000936395-20-000036 | safely_correctable | +0h | +4h |
| TTWO 0001047469-15-000639 | exceptional_offset | +5h | +5h |
| TTWO 0001628280-26-054870 | exceptional_offset | +4h | +4h |
| TTWO 0001047469-14-008670 | safely_correctable | +0h | +4h |
| TTWO 0001628280-25-026694 | exceptional_offset | +4h | +4h |

All five sampled exceptional headers corroborate old cache wall-clock text mislabeled as Z. Each saved database instant is another four/five hours later than the header instant, explaining the observed eight/ten-hour database-to-old-source gap as two separate discrepancies around the header reference. This arithmetic does **not** establish the historical write sequence. The two safe controls had genuine source UTC, and their repaired (rather than old stored) timestamps agree exactly with headers.

The two fresh main submissions responses contain 70 of the 71 exceptional accessions, all shifted four/five hours later than their original manifest source strings; these shifts exactly match the relevant Eastern offset. CIEN’s earliest exception is no longer in its main response; its header was independently retrieved. Five of the 71 now have header corroboration; the other 66 rely on the new submissions response only. For all 71 references, the old source clock equals the reference Eastern clock and the saved post-repair timestamp remains four/five hours later. This is strong reason to revisit the **already-excluded 71**, with source-vintage and write-provenance checks, not permission to update them. No excluded row changed here.

All 205 unresolved manifest rows have empty source-evidence lists (132 DELL, 73 others). None intersects the 22 former cases or the selected current controls. Missing evidence alone cannot diagnose a mislabeled timezone. This finding does not explain those 205; their existing targeted evidence-recovery need remains, with no justification for blanket offset inference or wider repair.

**Demonstrated versus possible impact.**

- **Demonstrated, former cases:** inconsistent source representations and potentially four/five-hour-early parsed availability if imported literally. Zero intersection with the saved repair or historical event population; no demonstrated event/signal effect from those 22.
- **Demonstrated, safe repair:** no contradiction in 65 independently checked safe rows. The repair remains unchanged and no new defective safe row was found.
- **Demonstrated, existing exceptions:** five sampled saved filing timestamps disagree with independently verified headers by four/five hours. The 66 other exceptional references have newer-source evidence, but no independently retrieved header in this task. These were explicitly unresolved production-data exceptions already, not timestamps changed by the safe repair.
- **Demonstrated timing-rule consequence:** TTWO accession `0001628280-25-026694`, filed 2025-05-20, header `20250520063202` = **2025-05-20 10:32:02Z / 06:32:02 EDT**; new raw submissions agrees. Original audit source was `2025-05-20T06:32:02.000Z`; saved post-repair DB timestamp was **14:32:02Z / 10:32:02 EDT**. Under unchanged `get_candidate_entry_date`, the saved timestamp yields **May 21**, while the header yields **May 20**. Fact **547980**, stable security **358**, period **2025-03-31**, links to saved event **398505**, which enters May 21 and is **not** an exact signal.
- **Not established:** whether May 20 is the next eligible session in the saved vendor-price series, the corrected actual entry price/date, changed momentum/returns, or whether this currently non-signal event would join the exact-signal cohort. No prices were read and no historical event was recomputed. A calendar candidate mismatch is not automatically proof of the final session result.
- The 71 excluded rows have 37 current-revenue links to membership-qualified events in the saved corrected baseline. One is an existing exact signal; its candidate date is unchanged. Only the TTWO event above changes candidate date. These are saved-link checks, not a full audit of every comparator dependency or a guarantee that the 191-signal cohort would remain unchanged after future repairs.

The accepted baseline remains 14,742 events and 191 exact signals as saved. Its earlier deterministic replay established consistency with the captured inputs, not independent truth of every excluded source timestamp. No currently saved exact-signal result is newly demonstrated wrong here. There is a specifically identified candidate-date concern and independently corroborated incorrect saved timestamps among the pre-existing exceptions. The current live production database was not checked, so whether later scheduled jobs changed those rows is unknown.

**Recommended next action.** Leave `parse_submissions_acceptance`, production importers, caches, database and the safe repair untouched. Keep both raw representations and their vintages; never solve this by interpreting all Z strings as Eastern. Separately authorize a narrow read-only review of the 71 existing exceptions, starting with the single TTWO event: verify the relevant saved price-session availability and source/entry dependencies before claiming a changed actual event or signal. Obtain independent headers for any excluded row proposed for a future repair, and preserve before/after source evidence. Any database access, repair or event recomputation needs separate scope/approval. The 205 unresolved cases need evidence recovery on their own merits; Stage 4 SIC expansion is not part of this recommendation. A later ingestion-quality design may flag cross-source disagreements, but no such policy or code fix is introduced here.

**Artifacts and offline reproduction.**

- `results.json`: every 22-case raw/parsed comparison, 103 controls, seven new header probes, all 71 exception comparisons and 37 compact event links.
- `inputs.json`: frozen compact source comparisons and saved baseline/manifest links; it contains no vendor prices or large database snapshot.
- `header/*.json`, `submissions/*.json`: seven and two exact new SEC response bodies with source URLs, retrieval clocks and SHA-256 values.
- `plan_initial.json`, `plan_followup.json`, `plan.json`, `requests.json`: bounded request rationale and all-attempt ledger.
- `code_paths.json`: reviewed function locations and code hashes; `validation.json`: final tests and integrity metadata.
- Source: `src/backtesting/investigate_acceptance_sources.py`; tests: `tests/test_investigate_acceptance_sources.py`.

Offline replay: `.venv/bin/python -m src.backtesting.investigate_acceptance_sources --analyze`. It uses frozen inputs and existing/new public header fixtures; no requests, live database, original preflight snapshot or price snapshot is needed. The raw-source regression test additionally checks the two committed Stage 2 submissions wrappers. `--capture` was a one-time read of saved Stage 3 inputs/results, the pinned repair manifest/audit, the local corrected preflight, selected existing submissions caches, and the exact historical Git cache objects. It refuses to overwrite frozen inputs. Those capture dependencies are fingerprinted; they are needed to independently re-extract the compact event/source links, not to replay the comparison. Source-path/hash references do not imply a production cache write.

**Validation and safety.** Focused offline test/check results are recorded in validation.json. Production timestamp source files, importers, caches and existing research artifacts were not edited. No database access, historical event computation/rebuild, price read/refresh, paper trading, daily orchestration, service change, investment/SIC methodology change, Stage 4 work, commit or push occurred. The nine successful bounded SEC reads are the only external operation. The initial sandbox connection failure was logged and counted. All uncertainty above is retained rather than converted into a repair decision.
