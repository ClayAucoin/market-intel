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

## One legacy Dell index diagnostic extension

`src.backtesting.sic_stage4_diagnostic` is separate from the pinned Stage 4 implementation. It supports only the ordinary index for CIK `0000826083`, accession `0000826083-12-000006`:

```text
https://www.sec.gov/Archives/edgar/data/826083/000082608312000006/0000826083-12-000006-index.html
```

Availability is unverified. The purpose is to inspect resource links after the recorded header HTTP 404, not to retry that header, accept identity or select a research clock. Default invocation prints help without preparation or retrieval. Original code, frozen inputs, evidence and reviews are not edited or re-pinned.

Preparation requires the exact six-attempt ledger hash `d5a833f52a11dd755b857901d7907512b43d376cfd3f94b9874cf47d576ea63c`, five completed successes and attempt 6's completed header HTTP 404. It verifies the original package/code pins, saved catalogue accession, pinned existing review, all three blockers and all 27 clock acknowledgements, with empty approvals. The extension explicitly acknowledges failed attempt 6 in its own continuation state; the original review remains unchanged. It exclusively creates `diagnostics/extension_01.json`, pinning implementation bytes (including the original Stage 4 module), original JSON/evidence dependencies, ledger, review, exact request and transport controls. Only this one extension is permitted; it is not a budget-reset or general diagnostic interface.

Clay's first manual command, from the repository root:

```bash
set -o pipefail
.venv/bin/python -m src.backtesting.sic_stage4_diagnostic \
  --package-dir logs/research/sec_sic_stage4_2026-09-26 --prepare \
  --review logs/research/sec_sic_stage4_2026-09-26/review_03.json \
  --review-sha256 a6cd4c1ead31ea245fc8b3deaee67351f0e43a17505e13956573cb579da7c604 \
  2>&1 | tee -a logs/research/sec_sic_stage4_2026-09-26/run_logs/diagnostic_prepare_console.log
```

Give Codex the printed manifest path/hash and console receipt for saved-file review before retrieval. Once reviewed and authorized, the separate manual fetch interface is:

```bash
set -o pipefail
.venv/bin/python -m src.backtesting.sic_stage4_diagnostic \
  --package-dir logs/research/sec_sic_stage4_2026-09-26 --fetch \
  --extension-manifest logs/research/sec_sic_stage4_2026-09-26/diagnostics/extension_01.json \
  --extension-sha256 '<exact reviewed manifest SHA-256>' \
  2>&1 | tee -a logs/research/sec_sic_stage4_2026-09-26/run_logs/diagnostic_fetch_console.log
```

Fetch verifies the exact manifest hash and all pinned state under the original package lock. It creates an exclusive extension reservation receipt, then immutable `attempts/000007.json` and the ledger snapshot before transport. The attempt consumes contingency: cumulative spending becomes 7/240, contingency 1/30; the six prior attempts and ordinary allocations remain intact. No repeated execution, automatic retry, redirect or linked-resource request is permitted. An interruption during reservation/storage leaves a durable stop requiring review; do not delete receipts or reservations to restart.

Transport uses existing SEC pacing/headers, `(10, 30)` timeouts, disabled redirects and a 256 KiB body bound. Every received HTTP status, including redirects and failures, retains its bounded body in `diagnostics/000007/body.bin` and metadata in `response.json`. Metadata pins the raw-body hash, URL, HTTP status, body length, reservation/manifest hashes and diagnostic provenance. Oversize responses preserve the first 256 KiB and mark truncation; incomplete reads preserve the received prefix and mark the failure. A transport failure before an HTTP response records null status and an empty body. Exception class names are saved without exception messages or credentials.

Durable outcomes remain in the shared `outcomes/` directory and `requests.json`. They use `diagnostic_evidence`, never ordinary `evidence` or `responses/` entries. Existing Stage 4 readers count the attempt and outcome but do not parse diagnostic content as a header, catalogue, identity or timestamp source. Subsequent continuation must acknowledge non-SUCCESS attempt numbers (including 6, and 7 if applicable). Denial/redirect/size stops still apply under the original rules. This extension does not authorize ordinary study continuation, another diagnostic or a retry.

Focused validation uses temporary packages and mocked transport with real network/database entry points blocked. No live preparation, manifest creation or retrieval is part of implementation validation.

## One legacy Dell submission-prefix diagnostic

`src.backtesting.sic_stage4_prefix_diagnostic` is a separate extension. It preserves the original index extension and its manifest. Its only target is the `.txt` resource explicitly linked by the saved attempt 7 index:

```text
https://www.sec.gov/Archives/edgar/data/826083/000082608312000006/0000826083-12-000006.txt
```

The saved index lists the complete submission as 24,438,849 bytes. This extension requests only bytes 0–262143; neither availability nor a complete SEC header within that prefix is presumed. Diagnostic bytes never become accepted research evidence. Any later proposal must demonstrate a complete SEC header from saved bytes, verify issuer/accession/form fields and preserve all identity and clock gates.

Offline preparation requires ledger SHA-256 `fa013e6ab012ffbd7f057f063babc993b6d7b327e5276b6a4e5201f4a683dc6d`: seven completed attempts, including attempt 6's periodic 404 and attempt 7's successful index diagnostic. It checks the index manifest/implementation pins, reservation-linked index result and body hash, exact saved `.txt` link, catalogue target, original code/frozen pins, all three blockers, 27 clock acknowledgements and empty approvals. It creates `prefix_diagnostics/extension_01.json`, pinning the new implementation, previous implementations, package dependencies, current ledger/evidence, review, single request and transport controls. Continuation explicitly acknowledges failed attempt 6 without approving a header retry. No existing manifest or frozen file is edited.

Clay's first manual preparation command, from the repository root:

```bash
set -o pipefail
.venv/bin/python -m src.backtesting.sic_stage4_prefix_diagnostic \
  --package-dir logs/research/sec_sic_stage4_2026-09-26 --prepare \
  --review logs/research/sec_sic_stage4_2026-09-26/review_03.json \
  --review-sha256 a6cd4c1ead31ea245fc8b3deaee67351f0e43a17505e13956573cb579da7c604 \
  2>&1 | tee -a logs/research/sec_sic_stage4_2026-09-26/run_logs/prefix_diagnostic_prepare_console.log
```

Review the saved manifest and printed hash before separately authorizing retrieval. The explicit manual fetch interface is:

```bash
set -o pipefail
.venv/bin/python -m src.backtesting.sic_stage4_prefix_diagnostic \
  --package-dir logs/research/sec_sic_stage4_2026-09-26 --fetch \
  --extension-manifest logs/research/sec_sic_stage4_2026-09-26/prefix_diagnostics/extension_01.json \
  --extension-sha256 '<exact reviewed prefix manifest SHA-256>' \
  2>&1 | tee -a logs/research/sec_sic_stage4_2026-09-26/run_logs/prefix_diagnostic_fetch_console.log
```

Under the same package lock, fetch validates manifest/state pins and makes a durable exclusive receipt and attempt 8 reservation before transport. It charges contingency, bringing spending to 8/240 and contingency 2/30. Reexecution cannot duplicate the request, including after interrupted storage. No automatic retry, redirect or linked-resource request is allowed. Default invocation only prints help.

The one request uses existing SEC pacing, `(10, 30)` timeouts, `Range: bytes=0-262143`, `Accept-Encoding: identity` and disabled redirects. Raw response-body streaming disables content decoding and enforces 256 KiB even if Range is ignored. Every received status retains bounded bytes and the relevant `Content-Range`, `Content-Length`, `Accept-Ranges` and `Content-Encoding` headers. Unexpected encoding does not establish a complete requested submission prefix. Oversize responses retain the first 256 KiB with `SIZE_FAILURE`/truncation; interrupted reads retain their prefix and record `NETWORK_FAILURE`. Exception messages are not persisted. Original denial/redirect/size continuation stops are preserved.

`prefix_diagnostics/000008/body.bin` and `response.json` hold diagnostic-only output, raw hash, reservation/manifest links and provenance. Metadata distinguishes HTTP-response completion, requested-prefix completion and full-submission completion. A normal 206 for bytes 0–262143 of a larger file completes the requested prefix, not the submission. A 200 ignoring Range may provide the whole requested prefix while streaming stops at the bound; it is marked truncated and not a complete submission. Invalid 206 range metadata is recorded as a processing failure. A non-200 body is preserved without claiming it is a submission prefix. Full-submission completion is a transport-length statement, not validation of SEC content or acceptance of identity/timestamp evidence.

The shared outcome and ledger use only `diagnostic_evidence`; no ordinary response/evidence entries are created. Original readers retain spending/outcome compatibility and ignore the diagnostic content. Implementation validation uses focused temporary fixtures with network/database entry points blocked; no live preparation or fetch is performed by Codex.
