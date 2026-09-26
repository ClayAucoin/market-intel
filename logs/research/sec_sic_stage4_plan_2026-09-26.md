# Stage 4 historical SEC SIC research plan

Prepared September 26, 2026 from saved evidence only. This is a proposal for implementation and later execution by Clay, not retrieval authorization or a production classification policy. No research, report replay, network request or database operation was executed to prepare it.

## Recommendation and fixed scope

Study twenty unique issuer CIKs: the ten Stage 3 issuers in their original windows, plus ten proposed issuers arranged as five adverse predecessor/successor cases. Keep each issuer separate, even when a symbol, corporate name or economic business appears to continue. Windows are approximately two years, selected for identity and coverage questions, never returns or signal outcomes. Freeze the roster before retrieval; do not replace difficult cases because evidence is missing or results are inconvenient.

Use complete periodic filing coverage as the mandatory baseline. Evaluate a separate, explicitly reviewed issuer-FILER 8-K/8-K/A layer. Do not carry Stage 3's unrestricted experimental Rule B into the new comparison. SEC SIC is an issuer disclosure classification, **not GICS** and not proof of a security's historical sector.

Maximum **240 new SEC request attempts across the entire stage**, including failures, retries, timeouts, interrupted reservations, submissions catalogues, historical shards, headers, bodies and any requested exhibit. Verified saved responses consume zero new requests and must not be downloaded again. This cap does not promise complete 8-K coverage for all twenty issuers.

## 1. Proposed roster and windows

Dates are inclusive start and exclusive end. For comparability, retain Stage 3's filing-date window membership; accepted-at availability is evaluated separately and never inferred from filing date. Retain boundary observations outside the window as explicitly tagged seed/identity evidence. Symbols below are case labels, not historical joins.

| # | Issuer / CIK | Window | Selection question and missing evidence |
|---|---|---|---|
| 1 | Apple / 0000320193 | 2021-01-01–2023-01-01 | Ordinary control; corroborate security 2's dated issuer/class bridge and window edges. Earlier seed is stale. |
| 2 | Honeywell / 0000773840 | 2018-01-01–2020-01-01 | Existing 3714→3724 SIC transition; distinguish common-stock and debt symbols; review security 256 binding and missing prewindow seed. |
| 3 | Johnson Controls / 0000833444 | 2021-01-01–2023-01-01 | Existing 7380→3585 transition within one CIK; ordinary shares versus debt; security 197 has no reviewed full-window interval. |
| 4 | Facebook/Meta / 0001326801 | 2021-01-01–2023-01-01 | Reuse announced June 9, 2022 FB→META boundary; do not invent an open-start date for security 7. Review class and earlier binding. |
| 5 | Alphabet / 0001652044 | 2021-01-01–2023-01-01 | Two separate securities (3 and 7468), Class A GOOGL and Class C GOOG, one issuer; stale seeds and unreviewed local bridge. |
| 6 | GE / 0000040545 | 2023-01-01–2025-01-01 | Parent during separations; retain security 33 separately from children. Seek dated boundaries and cover confirmation without transferring SIC. |
| 7 | GE HealthCare / 0001932393 | 2023-01-01–2025-01-01 | Child security 440; distinguish distribution, regular-way trading and disclosure availability. January 1 is not automatically an eligible security date. |
| 8 | Activision Blizzard / 0000718877 | 2021-01-01–2023-01-01 | Former issuer, empty current ticker array, security 10411 and no saved baseline events. Reuse known clock disagreements; review identity without inventing events. |
| 9 | Twitter / 0001418091 | 2020-01-01–2022-01-01 | Independent former-issuer control, security 10462, stale seed and known clock disagreements. This unchanged window does not establish later acquisition/delisting boundaries. |
| 10 | FLEETCOR / 0001175454 | 2020-01-01–2022-01-01 | FLT common-stock evidence exists; security 10433 lacks dated history. No inference about later ticker consolidation; improve edge and bridge evidence. |
| 11 | Legacy Dell Inc. / candidate 0000826083 | 2012-01-01–2014-01-01 | Proposed predecessor DELL case around going private; recover issuer/class and termination evidence instead of joining by ticker. |
| 12 | Dell Technologies / 0001571996 | 2017-01-01–2019-01-01 | Tracking-stock/common-stock distinctions and proposed DVMT→DELL transition; test separation from legacy Dell CIK. |
| 13 | Legacy General Motors / candidate 0000040730 | 2008-01-01–2010-01-01 | Proposed bankruptcy-era GM/predecessor identity; investigate symbol and cessation boundaries without treating disappearance as continuity. |
| 14 | General Motors Co. / 0001467858 | 2010-01-01–2012-01-01 | Successor common-stock/IPO evidence and reused GM symbol; distinguish issuer emergence from public security trading. |
| 15 | Legacy Twenty-First Century Fox / candidate 0001308161 | 2018-01-01–2020-01-01 | Proposed legacy FOX/FOXA classes around separation/acquisition; determine which securities ended or changed issuer. |
| 16 | Fox Corporation / candidate 0001754308 | 2018-01-01–2020-01-01 | Proposed successor FOX/FOXA class identities under another CIK; verify announcement, distribution and trading dates separately. |
| 17 | DowDuPont/DuPont / 0001666700 | 2018-01-01–2020-01-01 | DWDP/DD name/symbol and separation questions; distinguish same-CIK changes from child relationships and reverse-split effects on identity. |
| 18 | Dow Inc. / 0001751788 | 2018-01-01–2020-01-01 | Separate child DOW; pre-inception coverage may properly be unknown or inapplicable. Do not import parent SIC or old DOW ticker history. |
| 19 | Kraft Foods Group / candidate 0001572709 | 2014-01-01–2016-01-01 | Proposed KRFT predecessor around combination; establish dated class and cessation evidence. |
| 20 | Kraft Heinz / 0001637459 | 2014-01-01–2016-01-01 | Proposed KHC successor issuer; establish initial public security evidence and distinguish predecessor filings from successor observations. |

The ten new cases are **candidates**, not accepted historical identity relationships. Five CIK/name associations are present in saved public submissions caches (Dell Technologies, GM Co., DuPont, Dow Inc., Kraft Heinz); these current fields do not prove historical identity. The five uncached CIKs above are discovery targets requiring public issuer verification before acceptance. Exact action dates, class descriptions, predecessor/successor relationships and internal security IDs are intentionally unaccepted pending source review. A mistaken candidate CIK triggers roster review, not a silent substitution. Twenty unique roster CIKs are intended; other parties mentioned in a document do not become extra study issuers or authorize extra retrieval.

## 2. Reusable evidence and gaps

Primary reference: [Stage 3 README](sec_sic_stage3_2026-09-24/README.md), with `inputs.json`, `results.json`, `identity_review.json`, `policy_recommendations.json`, `validation.json`, `checkpoint_review.json`, request plans/ledger and header/body fixtures in that directory. Pilot and Stage 2 fixture paths are retained in the Stage 3 observations and replay dependencies.

Stage 3 contains 167 loaded issuer observations, including 125 in-window observations: **80/80 periodic accessions** and 45 additional form observations. It classified 69 saved security events under both A and B, but Alphabet duplicates issuer disclosure dates across classes, and ATVI/TWTR have zero saved events. There are no independently reviewed full-window local security-to-CIK intervals for the eleven securities. These are evidence limits, not reasons to fabricate interval starts. Reuse the 69 compact event keys/cutoffs only as the frozen original sample, separately from new issuer coverage probes; do not recompute events or signals.

Planning integrity checks verified raw hashes for all 167 saved header observations and all 15 Stage 3 gzip primary bodies. No parser replay or report execution occurred. New work must pin the reused artifact bytes and recheck them before use. Saved Stage 3 catalogues are authoritative for its frozen inventory vintage, not proof of contemporaneous archive completeness.

Five current main submissions files no longer match Stage 3 `inputs.json.source_hashes`: AAPL, JCI, META, GE and GEHC. Preserve frozen catalogues and public fixtures; do not overwrite pins or silently regenerate inputs from those caches. If independent extraction auditing is needed, first recover the exact pinned historical blob from saved Git evidence where available. A changed cache may be frozen as a **new inventory vintage**, with its own hash, only after review; failure to recover an old blob is a disclosed extraction-audit limitation, not a reason to refetch verified headers.

New-case catalogue inventory, inspected locally during planning (counts are saved catalogue rows, not verified issuer-FILER observations):

| New issuer | Saved submissions input under `data/cache/sec/submissions/` | Periodic / 8-K-family rows in proposed window |
|---|---|---:|
| Dell Technologies | `CIK0001571996.json` and `CIK0001571996-submissions-001.json` | 8 / 30 |
| GM Co. | `CIK0001467858.json` and `CIK0001467858-submissions-001.json` | 9 / 68 |
| DuPont | `CIK0001666700.json` and `CIK0001666700-submissions-001.json` | 8 / 30 |
| Dow Inc. | `CIK0001751788.json` | 3 / 16 |
| Kraft Heinz | `CIK0001637459.json` | 2 / 10 |
| Five legacy/uncached candidates | No saved submissions catalogue found at those CIK paths | Unknown, not zero |

No CIK/accession-named research header/body fixtures were found for the ten additions. Before requesting anything, inventory other saved public fixtures and verify candidate catalogue CIK, arrays, duplicates, shard coverage and hashes. Freeze reusable cache bytes into the isolated research package without updating production caches. The 30 observed periodic rows for the five cached additions are an inventory starting point, not a completeness certification. The already visible 154 8-K-family rows for just those five additions demonstrate why complete 8-K retrieval for twenty issuers cannot be promised within this budget.

Missing evidence: all new-case dated headers and class/action documents; verified catalogues/shards for uncached candidates; independently reviewed bridges to internal security IDs; explicit action boundaries and at-window-edge identity corroboration; prewindow observations where available; remaining periodic headers/amendments; and a form-specific 8-K eligibility/coverage inventory. For GEHC/new issuers, lack of pre-inception filings must not be filled from a parent. Legacy issuers may cease periodic reporting during a window; an eight-filing quota is inappropriate.

Timestamp context only: reuse the relevant source-semantics and 22 ATVI/TWTR discrepancy rows from [acceptance-source investigation](sec_acceptance_source_discrepancy_2026-09-24/README.md), its `results.json`/raw submissions, and matching Stage 2/3 headers. The 103 agreeing Stage 3 controls remain useful. No new retrieval is needed to reconfirm those pairs. Its earlier TTWO next-action recommendation is superseded for the completed target: v2 manifest `c73fff2f6492a31f94422ee04e86332e01f0e2fd667bbaf37bc3943992401bda`, receipt `ttwo_acceptance_correction_2026-09-26_v2/executions/20260926T054533_173119Z/receipt.json`, status `COMMITTED_VERIFIED`, commit `5fc205ead225f8289b3275048ce91c424845b753`. Planning read only manifest/receipt scope and status. Do not rerun TTWO calculations, reapply it, relabel old saved event IDs as current, or reopen the 29,837-row repair. TTWO is not an extra roster issuer. The remaining timestamp exceptions are outside Stage 4.

## 3. Request allocation, batches and stops

Reserve before every outbound call, under one locked persistent stage-wide ledger. Deduplicate by canonical URL and evidence hash across all saved stages. A successful saved response must pass integrity checks before reuse; an existing filename alone is insufficient. Different submissions vintages remain separate evidence. No automatic refresh or hidden request by an importer is permitted.

| Envelope | Maximum attempts | Priority and use |
|---|---:|---|
| Catalogue discovery | 20 | Uncached main responses and only required historical shards; saved verified catalogues first. |
| Missing periodic headers | 90 | Complete all catalogue-listed 10-K, 10-K/A, 10-KT, 10-KT/A, 10-Q, 10-Q/A, 10-QT and 10-QT/A accessions. Amendments count separately. |
| Dated identity evidence | 50 | Up to 30 primary/action documents and 20 missing associated headers; reuse periodic headers. Prioritize the five paired cases and unresolved local bridges. |
| Prewindow/edge seeds | 20 | Nearest eligible issuer periodic seed first; distinguish identity corroboration from SIC evidence. No seed if the issuer/security did not yet exist. |
| Reviewed 8-K/8-K/A layer | 30 | Unretrieved issuer-side headers after baseline and identity needs; paired action/transition intervals first. |
| Contingency | 30 | All retries and unexpected catalogue/periodic/identity needs. Never treat as permission for an additional study. |
| **Total hard ceiling** | **240** | All new attempts, including unsuccessful ones. |

Assign each request once to its first purpose; a periodic header also supporting an identity document is not counted twice. These are proposed allocation envelopes, not success counts. Transfers of unused envelopes require a saved revised allocation reviewed by Clay and Codex; no transfer may expand 240. If complete periodic coverage needs more than the planned envelope, pause before broadening sampling and review the allocation. Preserve unfinished issuers rather than trimming windows silently.

Start with at most ten catalogue attempts per batch. Then use batches of at most twenty attempts, with a saved review between batches; this applies equally to failures and retries. Request sequentially with existing SEC pacing, timeouts, size limits, no redirects and one process lock. Persist `IN_FLIGHT` before calling; a crash reservation consumes a slot. At most three total attempts per canonical URL; stop a batch at the first request/processing failure and review before retry. A processing error with saved raw bytes should be handled offline, not by downloading the response again.

Predeclare accession selection before each batch using only identity/coverage needs. Complete periodic coverage for all roster issuers remains the first filing goal. Within the 8-K layer, inventory **all** 8-K/8-K/A catalogue accessions, separately report expected/retrieved/eligible/ineligible/unretrieved counts, and label each issuer's coverage complete or sampled. Prefer complete coverage for an affordable subset; otherwise select explicit identity-action or SIC-transition intervals and report their boundaries. Preserve existing proxy/SD/11-K/13F evidence as supplemental, outside the A versus A+8-K comparison. Do not promote a document because its SIC is favorable.

Stop retrieval immediately at 240 reservations; on 401/403/429 or an unexpected redirect; at the URL retry ceiling; on lock contention; on canonical-URL/CIK mismatch, changed pinned bytes, conflicting catalogue duplicates or unsafe response size. Review malformed/missing SIC and unmatched FILER evidence rather than discarding it. Identity or clock conflicts quarantine affected lookups; continue unrelated planned work only after a saved review records the conflict. Stop a case if establishing its relationship requires another unrostered issuer or more budget. The final report must disclose incomplete coverage and exhausted attempts, without implicit cap extensions.

## 4. Acceptance criteria: identity and clocks

Maintain separate ledgers for issuer identity, public security/class/ticker assertions, and the public-to-internal security bridge. Proposed fields: stable security ID if independently supported, CIK, class/title/context, symbol/exchange, asserted effective start/end (nullable), document acceptance/knowledge time, accession, source URL/path/hash/vintage, quoted evidence location, relationship type, reviewer decision and unresolved conflicts. Multiple classes under one CIK remain separate securities; mergers, spin-offs and symbol reuse do not merge histories or transfer SIC.

Accept a public issuer observation only when the target CIK, accession and form match, the header has an unambiguous target **FILER** SIC, and the source hash and acceptance parse validate. Reject owner/subject-only SIC and another co-filer's code. For a public security relationship require dated issuer evidence plus cover-page class/title/symbol context or equivalent explicit action text; distinguish debt, tracking stock, voting classes and ordinary equity. Older untagged filings need reviewed textual locations, not guessed XBRL contexts. A single cover supports identity at its disclosure, not an independently proven two-year interval.

Accept a dated interval or cross-CIK relationship only with explicit documentary action/boundary evidence and reviewed class-specific linkage. Preserve announcement, legal effective, distribution and trading dates separately. Historical knowledge starts no earlier than the source acceptance: a later filing describing an earlier action may corroborate it retrospectively but cannot supply evidence at an earlier historical cutoff. Open boundaries stay unknown. Local ID assignment requires a saved independently reviewed bridge; current ticker equality or an undated database mapping is insufficient. Without that bridge, issuer SIC may be reported but validated security classification remains UNKNOWN. Conflicting plausible bindings remain unresolved/AMBIGUOUS, never resolved by return continuity or a convenient symbol.

Propose retaining Stage 3's **explicit, research-only verified-header clock policy**, subject to review before implementation. Keep raw header clock, raw submissions value, both parsed UTC instants, filing date, vintage and parser/source basis. ISO `Z` retains its explicit UTC meaning; compact EDGAR clocks use the established header parser, including DST validation. Do not infer offsets from resemblance. Store disagreement magnitude and quarantine the conflicting source pair. A reviewed header can support a clearly labeled header-based research observation; it does not silently repair or override submissions data. If header validity/identity is unresolved, withhold time-qualified classification. At cutoffs where plausible source instants imply different availability, report the timing conflict separately even if SIC codes agree. No chosen production timestamp and no general exception repair follow from this study.

Reuse inclusive lookup `accepted_at <= cutoff` only after identity/time eligibility is checked. Latest simultaneous differing codes remain AMBIGUOUS; no prior eligible observation is UNKNOWN. Temporal disagreement between neighboring forms is a transition interval, not automatically an error. Report evidence age; 365 days remains descriptive, not a new rejection threshold. Do not backdate a new SIC to an asserted action date or infer continuity across unobserved gaps.

## 5. Deliverables and limits

Future saved report should distinguish: issuer observations from validated security lookups; class/security counts from unique issuer counts; periodic coverage from 8-K completeness/sampling; public identity proof from the local bridge; retrospective corroboration from point-in-time availability; and missing source evidence from conflicting evidence. Include excluded/ineligible observations with reasons, source-clock conflict rows, dated relationship review, coverage/missing-accession tables, observation ages and transition bounds. Preserve the existing Stage 3 event sample as a conditional comparison only. For new issuers use twenty-four first-of-month 09:30 America/New_York synthetic coverage probes per two-year window (480 issuer probes overall), not fabricated trading events or claims of exchange-session eligibility. Apply an identity eligibility gate and separately label dates before public security existence; retain UNKNOWN when existence is unproved. Share-class views may add security rows without changing the twenty-issuer denominator.

This can establish whether adverse cases have recoverable dated issuer/class evidence, where CIK boundaries or symbol reuse defeat ticker joins, catalogue-relative periodic completeness, the incremental timing/coverage evidence from reviewed 8-Ks, and the extent of unresolved binding/clock questions in this purposive sample. It cannot establish historical GICS, universe-wide prevalence or safety, all-form completeness, continuity between observations, contemporaneous SEC archive availability, vendor price continuity, investment performance, repaired baseline validity or production readiness. No thresholds, portfolio rules, train/test boundaries, membership methodology, signal definitions or backtest horizons change. No missing baseline events are manufactured.

## 6. Existing code and minimal future implementation

Reuse `sic_stage3.periodic`, `parse_observation`, `body_identity`, `canonical_url` and the locked reservation/pacing/fixture approach; `sic_validation_study.lookup`, `transitions`, `density`, `instant` and hash utilities; `src/sec/acceptance_time.py` source-specific parsers; and `src/sec/json_cache.py` atomic JSON writes. Existing tests are useful future regression coverage, not tests run in this planning task.

Smallest proposed implementation: an isolated Stage 4 runner/config and research output directory, importing validated parsing/lookup helpers while leaving the frozen Stage 3 defaults and production behavior unchanged. It needs:

1. Frozen roster/windows, saved-source manifest and effective-dated relationship review inputs rather than the hardcoded ten-case list; cache-independent replay with no database fallback.
2. Catalogue/main-and-shard retrieval in the same stage-wide 240-attempt ledger; explicit reviewed request plans, batches and cross-stage hash-verified reuse for headers, bodies and catalogues. Stage 3's path helpers and cap must not be redirected by ad hoc global monkeypatches.
3. A separate periodic versus periodic+eligible-8-K comparison, explicit missing coverage, and identity/clock eligibility gates with preserved rejected/conflicting evidence. Do not reuse the broad `rule == B` all-forms filter unchanged.
4. Class/action extraction support for reviewed older untagged documents and targeted exhibits when a primary document merely incorporates an action announcement. A document/exhibit request consumes the same cap. Preserve raw bytes and source locations; do not make automated interval inference a requirement.
5. Separate reviewed relationship ledger, source-vintage conflict table and canonical offline report artifacts. No new performance calculations, production writes or repairs.

The existing Stage 3 CLI has `--prepare`, `--fetch`, `--batch`, `--analyze`, a fixed Stage 3 directory and an exhausted 120-attempt cap. It has no Stage 4 package/roster selector. Stage 2 `--fetch-plan` likewise targets its own stage and ledger. **There is currently no supported executable Stage 4 retrieval/report command.** Do not reuse those old fetch commands, rerun frozen preparation, or run the old analyzer as a substitute. Exact Stage 4 commands must be documented only after the minimal runner exists and has been reviewed.

## 7. Clay execution and Codex review handoff

After roster/method and implementation review, use proposed isolated root `logs/research/sec_sic_stage4_2026-09-26/`. Future preparation should save `inputs.json` (roster, catalogues, saved-source hashes and compact identity/event evidence), `reuse_manifest.json`, a reviewed `relationships.json`, and versioned `plan_01.json`, `plan_02.json`, etc. No credentials or machine-specific paths belong in these artifacts.

Clay runs the future supported preparation command, saves its exact command/version and console receipt, and gives Codex the frozen inventory/plan paths for offline review. Then Clay runs one reviewed retrieval batch at a time and saves raw catalogue wrappers, headers, compressed original primary/exhibit bytes plus metadata, and the append-only/resumable `requests.json` ledger. Keep per-batch console output under `run_logs/`; redact credentials rather than saving environment dumps. Codex reviews saved hashes, counts, failures, identity/clock conflicts and next-plan allocation before another batch. No request is implied by this planning document.

When retrieval stops or the approved coverage goal is met, Clay runs the future supported **offline** report command from saved inputs only and saves `results.json`, `identity_review.json`, `clock_conflicts.json`, `coverage.json`, `validation.json` and `README.md`. Record partial coverage even on an early stop. Codex then reviews those outputs and source excerpts, without requesting the same evidence again. Pin outputs/code and retain old plans/vintages; do not overwrite Stage 3, acceptance investigation or TTWO packages. Packaging/commit remains a separate task.

No research executable is supplied here because no existing interface safely targets that proposed root. Supported existing local review commands, for Clay to use later from the repository root, are:

```bash
git status --short
git diff --check
sha256sum logs/research/sec_sic_stage4_plan_2026-09-26.md
```

## Decisions for joint review before implementation

- Confirm the five proposed predecessor/successor pairs, their candidate CIKs and windows; no discovery substitution without review.
- Confirm the proposed identity/point-in-time eligibility gates and the explicit header-based research clock policy, including conflict reporting rather than production timestamp selection.
- Confirm allocation envelopes, batch sizes and whether the bounded 8-K layer should prioritize complete affordable issuer windows or complete selected action/transition intervals. Both must disclose the unretrieved remainder.
- Confirm the isolated runner/output contract. Unknown internal IDs and unavailable dated bridges remain legitimate unfinished findings, not an invitation to query or alter production.

Planning changed only this document. No code implementation, tests, reports, replay, external requests, database operations, services, commits or pushes were performed. Prior Stage 3's 40 passing offline tests and TTWO v2's 37 passing tests are saved historical validation, not checks rerun here.
