# Public Git checkpoint review — 2026-09-24

No staging, restore, deletion, commit, push, database access, refresh, event rebuild, live paper/orchestrator execution, notifications or service changes occurred. Existing files remain untouched. Only this review and its JSON inventory were created; Python compilation produced ignored bytecode. The current 14,742-event / 191-signal snapshot is the accepted corrected-current-input baseline.

## Recommendation

Use four ordered commits: parser → SIC pilot → audit/repair → historical baseline/provenance. This avoids broken intermediate dependencies without refactoring trusted code: the SIC pilot imports the new header parser; the timestamp audit reads the pilot snapshot and the signal-impact tool imports the pilot. Both historical tools import repair helpers. The sector-readiness source/test/report/JSON are already committed in f8ff747 and need no staging.

Exact file lists below are an allowlist, not commands to execute now. Do not use `git add .`, `git add -A`, or broad research/cache directory staging. Every initial modified/untracked file is classified in the companion JSON with byte size, SHA-256, privacy flags and rationale.

## Current status and conventions

- Initial status: 104 modified tracked files (99 caches + four production source files + one freshness test); 90 untracked files (eight source modules, eight tests, 74 research artifacts); zero staged files.
- Caches: 10 companyfacts and 89 submissions files, 169.07 MiB total working content. Research artifacts: 42.54 MiB. Entire initial inventory: 194 files, 222,108,407 bytes.
- Two new review files bring untracked count to 92; tracked modifications remain 104. The only ignored research file is the prior provenance_tests.log.
- .gitignore currently ignores .venv, bytecode, .env, *.log, credentials and /logs/sec-production/. It does not ignore SEC caches or research JSON/GZIP.
- 1,853 SEC cache files are already tracked. Recent commits mixed generated cache updates and research evidence (notably f8ff747); that precedent does not justify publishing the current daily refresh. Existing research JSON/Markdown conventions support deliberately selected evidence snapshots.
- No .gitignore change is included in this plan. Ignore rules cannot hide modifications to already tracked cache files; untracking caches would be a separate policy change, not part of this checkpoint.

## Source and test review

All four tracked source diffs route submissions timestamps through the new explicit-offset parser; the only tracked test changes replace three naive fixture timestamps with their intended explicit Eastern offset. New files implement source-specific parsing, bounded audit/repair/preflight/replay and SIC pilot logic. No accidental builder, signal, strategy, portfolio, price-import or orchestrator modification was found. Header handling remains explicitly Eastern; no automatic historical correction is introduced. The repair runner is an archived pinned operation, not a migration to rerun. Its --apply mode requires explicit invocation and enforces old values/counts/cutover. Current cache and database drift deliberately prevents reapplication.

## Privacy and public-repository review

All 194 initial files were scanned, including decompressed GZIP/JSONL payloads; JSON structures and source/test changes were inspected. No email addresses, credential-bearing URLs, private-key blocks or recognized token patterns were found. No .env, credentials, OAuth payload, external account number or private Historical Portfolio data is in the proposed lists. No attempt was made to discover any private investment-club identity. This is a scoped content review, not a guarantee against arbitrary unrecognized secret encodings.

Paper account fields are a local synthetic row ID, the existing code-defined paper-account name, simulated cash and the already documented immutable cutover. The saved name was verified equal to the existing source constant without printing it. These are not brokerage/bank identifiers. CIKs, accessions, company/security IDs and SEC issuer business-contact fields are public issuer or local research identifiers. Credential-key scan hits were paper_accounts metadata/hashes, not secrets.

Some provenance artifacts contain local filesystem paths, operating-system username, PIDs, transaction IDs and timestamps. These are non-credential environment metadata already used in the saved provenance; they are explicitly disclosed here rather than classified as secret. The raw filtered journal is excluded. The retained report/verification/replay still include some local-path metadata; if the owner wants zero host-identity metadata public, create separately identified public derivatives before staging rather than edit hash-pinned originals. The proposed list assumes that non-secret host metadata is acceptable.

## Large files and reproducibility

Largest working cache is ~18.17 MB; none of the initial files exceeds 25 MB. Size alone is not the only criterion. Exclude the 24,366,859-byte replay-input archive (143,986,090 bytes expanded), two 1,300,759-byte full-row backups, and the 5,538,027-byte preflight snapshot from public Git. Keep them durably local; they are necessary for complete replay/rollback, not disposable just because generated. Both backups are identical. Do not loosen their original restricted permissions.

Preserve the 1,588,990-byte manifest unchanged, the 1,888,193-byte pinned final audit, and the 2,096,553-byte earlier audit explicitly referenced by the signal-impact script. Preserve the 1,802,695-byte deterministic event output: these small compressed historical snapshots cannot be reconstructed exactly from a changing live database. They carry information a Markdown summary cannot replace. The initial 2,095,335-byte audit is redundant and remains local. All 37 small SEC header fixtures are essential to offline tests and prevent repeated requests; both pilot snapshots retain retrieval accounting.

Public Git will contain baseline historical event output, compact summaries, source evidence extracts, pin/receipt hashes and full timestamp correction proposals. It will not be a self-contained archive of vendor prices or complete database state. References to excluded backups, input snapshots or logs deliberately identify locally retained evidence; their hashes are retained in receipts/verification. A public-only checkout cannot rerun the original full input replay without that local archive. The investigation CLI captures current DB inputs; replay(data) additionally requires typed dates/Decimals, so loading saved JSON directly is not a complete replay CLI.

## Cache restoration review

All 99 exact paths listed below are candidates for a separately authorized restore to HEAD, not for these commits. First preserve current evidence durably outside Git, especially GIS companyfacts/submissions and the baseline replay inputs. Do not replace live source caches simply to make status clean: a restore would revert local retrieval state even though it does not change the database.

88 modified submissions files occur in the pinned manifest: all 88 HEAD blobs match their pinned hashes and all 88 working copies differ after refresh. The other 1,051 pinned source files still match. The remaining changed caches are ten companyfacts files and one submissions file not cited by the repair manifest. Thus HEAD holds the complete pinned submissions evidence when combined with unchanged files; current working caches represent a later refresh. The inventory records each HEAD/current/pin hash. This is not a reason to rerun the completed repair.

## Ordered exact staging lists

### Commit 1: `fix(sec): normalize acceptance timestamps using explicit source semantics`

Production parser, both writers, both validation paths and focused parser/freshness regressions.

Dependency: existing HEAD only. All other inventory files are excluded from this commit.

```text
src/sec/acceptance_time.py
src/sec/filing_repository.py
src/sec/import_universe_filings.py
src/sec/json_cache.py
src/sec/sec_submissions.py
tests/test_sec_acceptance_time.py
tests/test_sec_production_freshness.py
```

### Commit 2: `research(sec): preserve bounded SIC pilot and cached header evidence`

Isolated pilot code/tests, both historical pilot snapshots, README and all 37 indispensable offline header fixtures.

Dependency: commits 1–1 in this sequence. All other inventory files are excluded from this commit.

```text
logs/research/sec_sic_pilot/README.md
logs/research/sec_sic_pilot/headers/0000019617_0000019617-18-000057.json
logs/research/sec_sic_pilot/headers/0000019617_0000019617-22-000319.json
logs/research/sec_sic_pilot/headers/0000019617_0001628280-26-054343.json
logs/research/sec_sic_pilot/headers/0000040545_0000040545-18-000014.json
logs/research/sec_sic_pilot/headers/0000040545_0000040545-22-000027.json
logs/research/sec_sic_pilot/headers/0000040545_0000040545-26-000049.json
logs/research/sec_sic_pilot/headers/0000320193_0000320193-18-000007.json
logs/research/sec_sic_pilot/headers/0000320193_0000320193-22-000059.json
logs/research/sec_sic_pilot/headers/0000320193_0000320193-26-000020.json
logs/research/sec_sic_pilot/headers/0000789019_0001193125-26-323660.json
logs/research/sec_sic_pilot/headers/0000789019_0001564590-18-001129.json
logs/research/sec_sic_pilot/headers/0000789019_0001564590-22-015675.json
logs/research/sec_sic_pilot/headers/0000849399_0000849399-18-000004.json
logs/research/sec_sic_pilot/headers/0000849399_0000849399-20-000007.json
logs/research/sec_sic_pilot/headers/0000849399_0000849399-22-000019.json
logs/research/sec_sic_pilot/headers/0000849399_0000849399-26-000031.json
logs/research/sec_sic_pilot/headers/0001031296_0001031296-18-000015.json
logs/research/sec_sic_pilot/headers/0001031296_0001031296-22-000020.json
logs/research/sec_sic_pilot/headers/0001031296_0001031296-26-000085.json
logs/research/sec_sic_pilot/headers/0001109357_0001109357-22-000059.json
logs/research/sec_sic_pilot/headers/0001109357_0001109357-26-000063.json
logs/research/sec_sic_pilot/headers/0001109357_0001628280-18-001324.json
logs/research/sec_sic_pilot/headers/0001175454_0001175454-18-000027.json
logs/research/sec_sic_pilot/headers/0001175454_0001175454-21-000039.json
logs/research/sec_sic_pilot/headers/0001175454_0001628280-24-008060.json
logs/research/sec_sic_pilot/headers/0001326801_0001326801-18-000009.json
logs/research/sec_sic_pilot/headers/0001326801_0001326801-22-000057.json
logs/research/sec_sic_pilot/headers/0001326801_0001628280-26-050705.json
logs/research/sec_sic_pilot/headers/0001652044_0001652044-18-000007.json
logs/research/sec_sic_pilot/headers/0001652044_0001652044-22-000029.json
logs/research/sec_sic_pilot/headers/0001652044_0001652044-26-000071.json
logs/research/sec_sic_pilot/headers/0001868275_0001868275-22-000044.json
logs/research/sec_sic_pilot/headers/0001868275_0001868275-24-000054.json
logs/research/sec_sic_pilot/headers/0001868275_0001868275-26-000104.json
logs/research/sec_sic_pilot/headers/0001932393_0001932393-23-000087.json
logs/research/sec_sic_pilot/headers/0001932393_0001932393-24-000050.json
logs/research/sec_sic_pilot/headers/0001932393_0001932393-26-000031.json
logs/research/sec_sic_pilot/pilot_2026-09-23_051959.json
logs/research/sec_sic_pilot/pilot_2026-09-23_052233.json
src/backtesting/sec_sic_pilot.py
tests/test_sec_sic_pilot.py
```

### Commit 3: `research(sec): archive acceptance audit and guarded timestamp repair`

Frozen legacy audit, signal-impact supplement, evidence-keyed manifest, guarded repair runner, focused tests and final execution evidence.

Dependency: commits 1–2 in this sequence. All other inventory files are excluded from this commit.

```text
logs/research/acceptance_repair/README.md
logs/research/acceptance_repair/execution_20260923_135745_721689/SUMMARY.md
logs/research/acceptance_repair/execution_20260923_135745_721689/receipt.json
logs/research/acceptance_repair/execution_20260923_135745_721689/receipt.json.sha256
logs/research/acceptance_repair/execution_20260923_135745_721689/regression_tests.txt
logs/research/acceptance_repair/execution_20260923_135745_721689/validation.json
logs/research/acceptance_repair/manifest.json.gz
logs/research/acceptance_repair/manifest.json.gz.sha256
logs/research/acceptance_repair/preflight_20260923_132450.json
logs/research/acceptance_repair/preflight_20260923_135055.json
logs/research/acceptance_signal_impact_2026-09-23_131228.json
logs/research/acceptance_timezone_2026-09-23.md
logs/research/acceptance_timezone_2026-09-23_123358.json.gz
logs/research/acceptance_timezone_2026-09-23_131057.json.gz
logs/research/acceptance_timezone_completion_2026-09-23.md
src/backtesting/acceptance_repair_manifest.py
src/backtesting/apply_acceptance_repair.py
src/backtesting/audit_acceptance_signal_impact.py
src/backtesting/audit_acceptance_timezone.py
tests/test_acceptance_repair_manifest.py
tests/test_apply_acceptance_repair.py
tests/test_audit_acceptance_signal_impact.py
tests/test_audit_acceptance_timezone.py
```

### Commit 4: `research(backtest): preserve corrected baseline and rebuild provenance`

Read-only preflight/replay tooling, focused tests, historical comparisons, baseline event output and verification reports.

Dependency: commits 1–3 in this sequence. All other inventory files are excluded from this commit.

```text
logs/research/timestamp_rebuild_2026-09-23/INTERVENING_REBUILD_PROVENANCE.md
logs/research/timestamp_rebuild_2026-09-23/PREFLIGHT_STOP.md
logs/research/timestamp_rebuild_2026-09-23/before_20260924_023350.json.summary.json
logs/research/timestamp_rebuild_2026-09-23/deterministic_replay.json.gz
logs/research/timestamp_rebuild_2026-09-23/local_source_confirmation.json
logs/research/timestamp_rebuild_2026-09-23/observed_cohort_field_changes.json
logs/research/timestamp_rebuild_2026-09-23/observed_intervening_changes.json
logs/research/timestamp_rebuild_2026-09-23/prior_saved_signal_statistics.json
logs/research/timestamp_rebuild_2026-09-23/provenance_summary.json
logs/research/timestamp_rebuild_2026-09-23/provenance_verification.json
src/backtesting/investigate_event_provenance.py
src/backtesting/timestamp_rebuild_preflight.py
tests/test_investigate_event_provenance.py
tests/test_timestamp_rebuild_preflight.py
logs/research/git_checkpoint_review_2026-09-24.md
logs/research/git_checkpoint_review_2026-09-24.json
```

## Exact cache restore candidates (do not restore yet)

```text
data/cache/sec/companyfacts/CIK0000019617.json
data/cache/sec/companyfacts/CIK0000040704.json
data/cache/sec/companyfacts/CIK0000070858.json
data/cache/sec/companyfacts/CIK0000072971.json
data/cache/sec/companyfacts/CIK0000091419.json
data/cache/sec/companyfacts/CIK0000831001.json
data/cache/sec/companyfacts/CIK0000886982.json
data/cache/sec/companyfacts/CIK0000895421.json
data/cache/sec/companyfacts/CIK0001090012.json
data/cache/sec/companyfacts/CIK0001564708.json
data/cache/sec/submissions/CIK0000004977.json
data/cache/sec/submissions/CIK0000006281.json
data/cache/sec/submissions/CIK0000019617.json
data/cache/sec/submissions/CIK0000021344.json
data/cache/sec/submissions/CIK0000031791.json
data/cache/sec/submissions/CIK0000034088.json
data/cache/sec/submissions/CIK0000035527.json
data/cache/sec/submissions/CIK0000036270.json
data/cache/sec/submissions/CIK0000040533.json
data/cache/sec/submissions/CIK0000040545.json
data/cache/sec/submissions/CIK0000040704.json
data/cache/sec/submissions/CIK0000047111.json
data/cache/sec/submissions/CIK0000052988.json
data/cache/sec/submissions/CIK0000059478.json
data/cache/sec/submissions/CIK0000063908.json
data/cache/sec/submissions/CIK0000066740.json
data/cache/sec/submissions/CIK0000070858.json
data/cache/sec/submissions/CIK0000072971.json
data/cache/sec/submissions/CIK0000077360.json
data/cache/sec/submissions/CIK0000079282.json
data/cache/sec/submissions/CIK0000091419.json
data/cache/sec/submissions/CIK0000091576.json
data/cache/sec/submissions/CIK0000093410.json
data/cache/sec/submissions/CIK0000093751.json
data/cache/sec/submissions/CIK0000096021.json
data/cache/sec/submissions/CIK0000315293.json
data/cache/sec/submissions/CIK0000319201.json
data/cache/sec/submissions/CIK0000320193.json
data/cache/sec/submissions/CIK0000320335.json
data/cache/sec/submissions/CIK0000354950.json
data/cache/sec/submissions/CIK0000720005.json
data/cache/sec/submissions/CIK0000723254.json
data/cache/sec/submissions/CIK0000723531.json
data/cache/sec/submissions/CIK0000732712.json
data/cache/sec/submissions/CIK0000764478.json
data/cache/sec/submissions/CIK0000796343.json
data/cache/sec/submissions/CIK0000798354.json
data/cache/sec/submissions/CIK0000804328.json
data/cache/sec/submissions/CIK0000831001.json
data/cache/sec/submissions/CIK0000833444.json
data/cache/sec/submissions/CIK0000842023.json
data/cache/sec/submissions/CIK0000866787.json
data/cache/sec/submissions/CIK0000878927.json
data/cache/sec/submissions/CIK0000882095.json
data/cache/sec/submissions/CIK0000884887.json
data/cache/sec/submissions/CIK0000885725.json
data/cache/sec/submissions/CIK0000886982.json
data/cache/sec/submissions/CIK0000895421.json
data/cache/sec/submissions/CIK0000909832.json
data/cache/sec/submissions/CIK0000912595.json
data/cache/sec/submissions/CIK0000915913.json
data/cache/sec/submissions/CIK0000920148.json
data/cache/sec/submissions/CIK0000936395.json
data/cache/sec/submissions/CIK0000946581.json
data/cache/sec/submissions/CIK0001000228.json
data/cache/sec/submissions/CIK0001002047.json
data/cache/sec/submissions/CIK0001014473.json
data/cache/sec/submissions/CIK0001045810.json
data/cache/sec/submissions/CIK0001053507.json
data/cache/sec/submissions/CIK0001090012.json
data/cache/sec/submissions/CIK0001090872.json
data/cache/sec/submissions/CIK0001120193.json
data/cache/sec/submissions/CIK0001137774.json
data/cache/sec/submissions/CIK0001137789.json
data/cache/sec/submissions/CIK0001145197.json
data/cache/sec/submissions/CIK0001174922.json
data/cache/sec/submissions/CIK0001260221.json
data/cache/sec/submissions/CIK0001327567.json
data/cache/sec/submissions/CIK0001327811.json
data/cache/sec/submissions/CIK0001341439.json
data/cache/sec/submissions/CIK0001390777.json
data/cache/sec/submissions/CIK0001393818.json
data/cache/sec/submissions/CIK0001402057.json
data/cache/sec/submissions/CIK0001403161.json
data/cache/sec/submissions/CIK0001478242.json
data/cache/sec/submissions/CIK0001512673.json
data/cache/sec/submissions/CIK0001535527.json
data/cache/sec/submissions/CIK0001561550.json
data/cache/sec/submissions/CIK0001564708.json
data/cache/sec/submissions/CIK0001571996.json
data/cache/sec/submissions/CIK0001601046.json
data/cache/sec/submissions/CIK0001613103.json
data/cache/sec/submissions/CIK0001633978.json
data/cache/sec/submissions/CIK0001679788.json
data/cache/sec/submissions/CIK0001705696.json
data/cache/sec/submissions/CIK0001783879.json
data/cache/sec/submissions/CIK0001811074.json
data/cache/sec/submissions/CIK0001932393.json
data/cache/sec/submissions/CIK0002115436.json
```

## Other exact exclusions: retain locally

- `logs/research/acceptance_repair/execution_20260923_135613_911626/receipt.json` — Aborted sandbox preparation; retain locally; successful receipt records completed operation.
- `logs/research/acceptance_repair/execution_20260923_135646_830619/filings_before.jsonl.gz` — Access-controlled full-row backup; local only, duplicate of successful execution backup.
- `logs/research/acceptance_repair/execution_20260923_135646_830619/receipt.json` — Intermediate read-only preparation receipt; retain locally; final receipt supersedes it.
- `logs/research/acceptance_repair/execution_20260923_135745_721689/filings_before.jsonl.gz` — Access-controlled rollback backup; preserve locally, do not publish; manifest supplies public timestamp before-images.
- `logs/research/acceptance_repair/preflight_20260923_132417.json` — Superseded initial preflight lacking historical subset count; retain locally.
- `logs/research/acceptance_timezone_2026-09-23_122141.json.gz` — Superseded initial audit snapshot; retain locally. Other two snapshots are explicit tool/pin dependencies.
- `logs/research/timestamp_rebuild_2026-09-23/before_20260924_023350.json.gz` — Large full preflight snapshot with duplicated filing/fact data; preserve locally and publish summary/hash plus canonical event output.
- `logs/research/timestamp_rebuild_2026-09-23/journal_provenance.json` — Raw filtered host/process log is redundant for Git; retain locally. Report and verification preserve chronology and source hash.
- `logs/research/timestamp_rebuild_2026-09-23/provenance_inputs.json.gz` — 24 MB compressed / 144 MB expanded full replay input archive with 1.27 million vendor-price rows; preserve locally. Redistribution scope not established; no need to publish entire price database.

- `logs/research/timestamp_rebuild_2026-09-23/provenance_tests.log` — already ignored by *.log; no need to force-add mocked test chatter. Current test result is recorded here.

## Potential ignore rules (proposal only)

Use narrow local excludes first for this operational evidence, or add these exact repository rules in a separately reviewed documentation/hygiene change. Do not blanket-ignore logs/research, *.json or *.gz, because that would hide mandatory fixtures and immutable evidence.

```gitignore
/logs/research/acceptance_repair/execution_*/filings_before.jsonl.gz
/logs/research/acceptance_repair/execution_20260923_135613_911626/
/logs/research/acceptance_repair/execution_20260923_135646_830619/
/logs/research/acceptance_repair/preflight_20260923_132417.json
/logs/research/acceptance_timezone_2026-09-23_122141.json.gz
/logs/research/timestamp_rebuild_2026-09-23/before_20260924_023350.json.gz
/logs/research/timestamp_rebuild_2026-09-23/provenance_inputs.json.gz
/logs/research/timestamp_rebuild_2026-09-23/journal_provenance.json
```

Adding /data/cache/sec/ to .gitignore would only affect future untracked caches and would not resolve these 99 tracked modifications. Do not use assume-unchanged/skip-worktree to conceal them. Broader cache versioning policy remains separate.

## Validation and readiness

- 219 focused offline tests passed in 1.444 seconds: parser/writers, manifest/repair guards, timezone/signal/sector audits, all 37 SIC header hashes and 395 lookups, freshness, paper protection, preflight and provenance adapters. Mocked paper output is not a live paper run.
- All 21 changed/new Python files compiled. git diff --check passed. Manifest/source-audit/receipt pins verified; no database query or historical analysis rerun.
- Existing sector-readiness artifacts remain unchanged and already tracked. Old report statements describing pending repair/rebuild are historical context, superseded by the successful repair receipt and intervening-rebuild report; do not silently rewrite old evidence.
- Ready for deliberate allowlist staging/commits after approval of this split and public non-secret metadata scope. Not ready for blanket staging, and a completely clean working tree additionally needs separately authorized cache archival/restoration and ignore decisions. No current file was restored/deleted and no ignore rule was applied.
- Files created by this review: this Markdown and the companion JSON only. Test stdout is temporary under /tmp. Expensive audit/rebuild, DB repair/migrations, all imports, paper/orchestrator jobs and external services were deliberately not run.
