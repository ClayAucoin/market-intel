# Isolated Stage 4 SEC SIC tool

Implementation of [the Stage 4 plan](../../logs/research/sec_sic_stage4_plan_2026-09-26.md), with the user's adopted decisions: twenty candidate issuers/windows unchanged; periodic baseline; complete explicitly selected action/transition intervals for 8-K/8-K/A; reviewed identity, knowledge-time and source-clock gates; fixed allocation envelopes; Clay executes study commands. SEC SIC remains distinct from GICS. Candidate pairs are hypotheses, not accepted predecessor/successor relationships.

`src.backtesting.sic_stage4` supports separate `--prepare`, `--plan`, `--fetch` and `--analyze` modes and an explicit `--package-dir`. Default invocation prints help and performs no action. Preparation, planning and analysis use saved files only, with no network/database fallback. Only `--fetch` calls transport. No production cache, Stage 3, timestamp investigation, TTWO evidence, database, services, events, prices or investment rules are changed.

## First manual preparation, run by Clay

From the repository root, run this **once**. It has not been executed on the actual study data during implementation.

```bash
mkdir -p logs/research/sec_sic_stage4_2026-09-26/run_logs
set -o pipefail
.venv/bin/python -m src.backtesting.sic_stage4 \
  --package-dir logs/research/sec_sic_stage4_2026-09-26 \
  --prepare 2>&1 | tee -a logs/research/sec_sic_stage4_2026-09-26/run_logs/prepare_console.log
```

Expected console result: `PREPARED_OFFLINE`, twenty candidates, frozen input hash, blocked and unsupported CIK lists. Exceptions terminate with a nonzero exit; `pipefail` preserves that exit through `tee`. Append console output rather than overwriting it. Do not save environment dumps or SEC User-Agent values.

Expected files for the **next Codex review**:

- `inputs.json`, `inputs.sha256`: frozen roster/windows, compact original saved event/identity samples, catalogues, code hashes, allocations, source pins, changed/unavailable vintage limitations and adopted decisions. `inputs.sha256` is a JSON string, not a `sha256sum` sidecar.
- `reuse_manifest.json` and `evidence/*.gz`: hash-verified local copies of reused raw header/body bytes, still-matching original-vintage submissions/shards, and available new-case serialized submissions caches. Original pinned catalogues also expose nearest prewindow seeds without refreshing changed main responses. Cache serialization is explicitly distinguished from original HTTP response bytes. These copies make subsequent replay independent of changing production caches.
- `candidate_review.json`: supporting source paths/hashes/names, conservative disagreement flags and blocked cases. A match is candidate support only, not accepted issuer identity or security continuity.
- `relationships.json`: frozen **unreviewed template**; no IDs or interval boundaries are guessed. Subsequent review decisions go in a new versioned file.
- `requests.json`: empty ledger snapshot. No requests occur during preparation.
- `run_logs/prepare_console.log`; `.lock` is a transient lock file, not research evidence.

Preparation refuses to overwrite frozen inputs or a partially created manifest. A failed preparation before retrieval should be reviewed, with a new package directory if necessary; do not delete artifacts to defeat guards. Package directories overlapping protected research/production paths are rejected. Code changes after preparation invalidate the package's code pins and require review. Once retrieval has started, retain this package and its ledger: changing directories does not authorize a fresh 240-attempt budget. There is no ledger migration or budget-reset interface; any future migration must explicitly preserve all attempts and successful response evidence before continuing this same study.

## Saved candidate issues and limits

Local inspection supports the five cached additions' current CIK/name associations: Dell Technologies, GM Co., DuPont, Dow Inc., Kraft Heinz. Five uncached candidates remain discovery targets (legacy Dell, legacy GM, both Fox candidates, Kraft Foods Group). No missing identity is inferred. Current ticker arrays do not establish historical class/issuer relationships.

An existing-case name discrepancy needs review: Stage 3's FLEETCOR names at CIK `0001175454` differ from the saved ticker catalogue's `CORPAY, INC.`. This alone does **not** establish that the CIK is wrong or prove ticker continuity. Preparation conservatively flags the name disagreement and blocks that case's retrieval. Acknowledgement permits unrelated cases to proceed, never silently substitutes CORPAY or unblocks the case. Any correction to the candidate evidence rules requires explicit review and a newly frozen package; do not edit `candidate_review.json` or `inputs.json`.

Stage 3 has 22 known ATVI/TWTR source-clock disagreements. They remain conflicts, not offsets to apply globally. Preparation records unavailable/changed Stage 3 extraction-source pins without replacing the frozen catalogues. TTWO v2 is already applied and committed; this tool does not repeat or expand that correction or the 29,837-row repair.

## Versioned review input

Clay and Codex review preparation outputs before retrieval. Save decisions as `review_01.json` in the package, using the exact `inputs_sha256` printed by preparation. Review files are pinned by their byte hashes; create `review_02.json`, etc., for later decisions rather than overwriting files used by plans/reports.

Initial review shape (fill real evidence; empty arrays preserve UNKNOWN):

```json
{
  "inputs_sha256": "<prepared input hash>",
  "reviewed_by": "Clay",
  "issuer_reviews": [],
  "relationships": [],
  "eight_k_intervals": [],
  "clock_reviews": [],
  "identity_requests": [],
  "acknowledged_contradictions": [],
  "acknowledged_clock_conflicts": [],
  "continuation": null
}
```

An `issuer_reviews` entry needs `cik`, `status: "ACCEPTED"`, `reviewed_by`, an aware ISO `knowledge_at`, and `evidence` entries with exact `url`, raw `sha256`, `location` and `quote`. Quotes must occur in normalized saved document/header text. Each source requires a matching eligible dated issuer-FILER header. Document CIK tags, when present, must match. A reviewer cannot backdate knowledge: the gate uses the later of declared knowledge and every cited source acceptance. Future conflict entries (`status: "CONFLICT"`, `knowledge_at`) affect cutoffs only from their knowledge time.

Security `relationships` additionally need `security_id`, `class_title`, explicit `effective_from` (aware ISO), nullable exclusive `effective_to`, and `interval_basis` describing reviewed explicit action evidence. At least one quoted class/action body or exhibit is required; the class title must be in quoted evidence. If `symbol` is supplied, the same quote must support its class association. Missing starts/IDs stay unknown. Do not fill starts from the first available cover or infer economic continuity from symbol equality. Overlapping accepted bindings, including across CIKs, are AMBIGUOUS. Class records stay separate. Action assertions, distribution/trading dates and retrospective corroboration should be retained as additional review fields; they do not backdate knowledge.

For a clock decision use `clock_reviews` entries with `cik`, `accession`, `header_sha256`, `basis: "verified_header_research_only"`, and `reviewed_by`. This explicitly authorizes a research header clock for that exact observation while retaining both raw representations and parsed instants. It does not fix submissions, reinterpret explicit Z, or choose a production timestamp. Without approval, time-qualified lookups are quarantined; density/transition calculations exclude the unreviewed clocks. A cutoff between disagreeing instants remains reported as a timing conflict even with header approval.

To continue unrelated retrieval without choosing a clock, `acknowledged_clock_conflicts` must list all pending conflicts as sorted strings `CIK/accession/header_sha256`. Existing conflicting sources remain quarantined. `acknowledged_contradictions` lists all blocked CIKs, sorted; those cases stay blocked. The offline report can be generated without either acknowledgement to preserve unresolved evidence.

After **every executed batch**, the next review must include `continuation` with the exact current ledger digest and all non-SUCCESS attempt numbers:

```json
{"ledger_sha256": "<digest of requests.json as printed by the offline command below>", "acknowledged_attempts": [1]}
```

`requests.json` is written in the tool's canonical JSON format; `sha256sum` on it yields the required digest. For a fully successful ledger, use `acknowledged_attempts: []`. Interrupted reservations count and require acknowledgement. Denial (401/403/429), redirect and response-size stops cannot be acknowledged away by this tool. Security lookup additionally requires accepted issuer identity; a class binding alone does not promote an unaccepted candidate.

## Planning and retrieval

`eight_k_intervals` entries need `cik`, inclusive `start`, exclusive `end_exclusive` (filing dates), a selection `reason`, and `reviewed: true`. The planner selects every 8-K/8-K/A catalogue accession in those action/transition intervals. If the complete remaining selection exceeds the 30-attempt envelope, it stops for interval review instead of silently sampling. Selected intervals can span multiple batches; partial completion is disclosed. Outside-interval unexamined accessions are listed in reports. All verified saved 8-K evidence can be reused without new requests, while other Stage 3 forms stay supplemental.

`identity_requests` are explicit reviewed items with `kind` (`header`, `body` or `exhibit`), `cik`, `accession`, `reason`, and `document` for bodies/exhibits. Accession must occur in the frozen catalogue; `body` must equal its `primaryDocument`; exhibits require the exact reviewed filename. This implementation supports bounded `.htm`/`.html` documents, not arbitrary URLs, PDF downloads or automated exhibit crawling. Header requests and document requests consume separate identity sub-envelopes (20 and 30).

Supported planning command after saving a reviewed file:

```bash
stage4_review_sha=$(sha256sum logs/research/sec_sic_stage4_2026-09-26/review_01.json | cut -d ' ' -f 1)
set -o pipefail
.venv/bin/python -m src.backtesting.sic_stage4 \
  --package-dir logs/research/sec_sic_stage4_2026-09-26 --plan \
  --review logs/research/sec_sic_stage4_2026-09-26/review_01.json \
  --review-sha256 "$stage4_review_sha" \
  2>&1 | tee -a logs/research/sec_sic_stage4_2026-09-26/run_logs/plan_console.log
```

The planner saves `plans/plan_01.json`, then increasing versions, and prints its exact path/hash and proposed attempt count. Each plan pins the frozen inputs/code, current evidence and ledger, review file, allocation and canonical request list. Planning without a review is supported only while no prior batch, pending source-clock conflict or candidate disagreement requires acknowledgement. A default real-study plan is expected to need the initial review because the known conflicts are retained.

Clay reviews the exact plan before the explicit fetch. Example for a reviewed first plan:

```bash
stage4_plan_sha=$(sha256sum logs/research/sec_sic_stage4_2026-09-26/plans/plan_01.json | cut -d ' ' -f 1)
set -o pipefail
.venv/bin/python -m src.backtesting.sic_stage4 \
  --package-dir logs/research/sec_sic_stage4_2026-09-26 --fetch \
  --request-plan logs/research/sec_sic_stage4_2026-09-26/plans/plan_01.json \
  --plan-sha256 "$stage4_plan_sha" \
  2>&1 | tee -a logs/research/sec_sic_stage4_2026-09-26/run_logs/fetch_console.log
```

Each plan executes at most once. It is refused if inputs, code, review, evidence or ledger changed. No request runs without the explicit plan hash. Each outbound call first creates an immutable fsynced `attempts/NNNNNN.json` reservation and updates `requests.json`; its immutable `outcomes/NNNNNN.json` references that reservation hash. `responses/NNNNNN.json` pins a successful raw response before processing, so interruption during processing does not authorize refetching it. `batches/plan_NN.json` records plan reservation. Interrupted attempts remain `IN_FLIGHT`; retries need a new reviewed plan and consume contingency. Counts are reconstructed/validated from durable reservations and outcomes, never from a reset counter. Missing or inconsistent ledger files cause a stop and require reconciliation, not removal or reset.

Ceilings: catalogue 20, periodic 90, identity 50 (30 documents/20 headers), seed 20, selected 8-K 30, contingency 30; total 240. First requests use their purpose envelope; any retry uses contingency. No budget transfer interface exists. Each batch is capped at ten when it contains catalogue/shard requests, otherwise twenty, with one attempt per URL per batch and at most three across the stage. Failure stops the batch. Unused slots after a stopped batch are not counted as attempts. Transport is sequential, paced, `(10, 30)` timeout, with redirects disabled and limits of 256 KiB for headers, 8 MB for catalogues/shards, 16 MB for bodies/exhibits.

SUCCESS raw responses are retained even when processing fails; those URLs are never refetched. Discovery, source-clock and issuer-role contradictions stop for review with saved provenance. Periodic completeness is checked before spending the 8-K envelope. If an envelope binds, the planner preserves unfinished work instead of transferring funds or silently trimming the required baseline. An empty plan means no eligible work fits the current controls; inspect coverage and review rather than raising caps.

## Offline reports and handoff

Supported offline report command, after saving the appropriate review version:

```bash
stage4_review_sha=$(sha256sum logs/research/sec_sic_stage4_2026-09-26/review_01.json | cut -d ' ' -f 1)
set -o pipefail
.venv/bin/python -m src.backtesting.sic_stage4 \
  --package-dir logs/research/sec_sic_stage4_2026-09-26 --analyze \
  --review logs/research/sec_sic_stage4_2026-09-26/review_01.json \
  --review-sha256 "$stage4_review_sha" \
  2>&1 | tee -a logs/research/sec_sic_stage4_2026-09-26/run_logs/analyze_console.log
```

Without `--review`, analysis still produces an unresolved/UNKNOWN report. It never fetches missing evidence. It saves a new immutable `reports/report_NN/` each time: `results.json`, `coverage.json`, `clock_conflicts.json`, `identity_review.json`, `validation.json`, `README.md`. Prior reports, raw evidence and plans stay unchanged. Raw clocks and conflicts are retained; malformed saved responses are reported without transport retries. Partial coverage is a valid result, not a reason to expand the budget.

Reports separate issuer observations from gated security lookups, synthetic first-of-month 09:30 Eastern probes from original saved events, class counts from issuer counts, and selected 8-K interval coverage from the full catalogue. No synthetic probe is a trading-session assertion. Periodic completeness is catalogue-relative header coverage, not identity or timestamp correctness certification. Synthetic issuer coverage is UNKNOWN before reviewed issuer evidence is known; real saved security events additionally require a reviewed dated class/ID bridge. Supplemental forms, rejected headers and quarantined clock observations remain visible. SIC transition bounds cannot prove continuity between observations; evidence age is descriptive.

For each next review send Codex the saved plan/review paths and hashes, console log, `requests.json`, new reservations/outcomes/evidence and any partial report paths. Do not ask Codex to refetch successful evidence. The 240 cap, unknown identities, frozen vintages and protected packages remain unchanged. Committing this implementation or study outputs is a separate authorized task.

## Offline validation

New tests exercise only temporary fixtures with real network and database access blocked. Relevant existing tests are selected individually to exclude saved-study replay/report methods. Validation results are recorded in the implementation completion response; historical Stage 3/TTWO saved test results are not presented as newly run tests.

Implementation validation on September 26, 2026: both changed Python files passed `.venv/bin/python -m py_compile`; **84 focused offline tests passed, zero failures** (47 Stage 4, 10 Stage 3, 8 SIC validation, 11 pilot, 8 SEC acceptance-time tests). The three existing saved-study replay methods were explicitly excluded. Network sockets, Requests session transport and PostgreSQL connection entry points were blocked during the suite; approved transport tests use local mocked responses. All preparation/planning/fetch/report interface exercises used temporary fixture packages. No real study preparation, retrieval, analysis, database access, production change, service action, commit or push occurred.
