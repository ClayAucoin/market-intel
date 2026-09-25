# Market Intel continuity note
Updated September 25, 2026, America/Chicago.

## Read this first
This note consolidates the communication rules recovered from earlier market-intel conversations, the repository's published AGENTS.md, and the current user-supplied Codex transcripts. It is a handoff reference, not an exhaustive archive of every conversation or proof of current live database state.

**Latest reported checkpoint: the TTWO correction is tested and committed, but has NOT been applied to production.** No execution receipt has been provided. Clay is considering waiting for the five-hour usage window to reset. Do not confuse a prepared command, authorization prompt, or code commit with a completed database correction.

## Working agreement

### Roles and communication
- Clay and the chat assistant make substantive technical and research decisions. The assistant should provide a clear recommendation rather than make Clay decipher implementation details.
- Codex does the mechanical repository work: inspect files, implement agreed changes, debug, compile, and run focused tests or bounded diagnostics.
- Codex must not independently choose investment strategy, signal definitions, scoring, portfolio rules, research methodology, or production behavior.
- Proceed one task at a time. Give concise explanations and exact copyable prompts or terminal commands. When manual editing is needed, provide clear file paths and complete replacements where appropriate.
- Clay pastes Codex's completion output back into this chat for review. Ask for /status after Codex work when assessing usage and the next model choice.
- Completion summaries should say what changed, the exact files, validation performed and outcomes, actions deliberately not run, and remaining decisions.
- Do not assume browser project history has been transferred into the separate Codex session. Explicit context and repository instructions are the handoff.

### Task authorization and autonomous completion
- Once Clay submits an agreed task prompt to Codex, that authorizes completion of its full stated scope. Do not ask for another "continue" or consent to perform steps already covered by that task.
- Continue through necessary in-scope implementation, ordinary fixes, focused validation and completion documentation without waiting for Clay to return. Resolve routine implementation choices using the agreed requirements.
- Write each task prompt with a concrete completion goal and any real stop conditions. A progress update is informational, not a request for permission or a reason to pause.
- Stop only at completion, a genuine blocker, an explicit task stop condition, or a new substantive decision or action outside the authorized scope. Explain the precise blocker and complete any remaining safe, authorized work first.
- Clay still runs reports and long jobs under the policy below. Autonomous completion does not authorize Codex to run those reports, expand research, change strategy, or override the task's limits.
- CLI command approvals and sandbox controls are separate from conversational consent. Prompt wording does not disable those controls, and this agreement does not change the CLI permission configuration.
- Preserve the TTWO application's explicit drift, timeout and uncertain-commit stop conditions. Do not automatically retry or roll back that operation.

### Model and credit discipline
- EVERY next operational step must begin with **KEEP** or **CHANGE**, the exact Codex model, and the reasoning setting, plus a short reason.
- Select a less costly suitable model for routine work. Earlier discussion considered GPT-5.6 Sol for routine work and GPT-6-Astra / Low for demanding research or sensitive operations.
- The recovered history did not establish a complete, fixed model/effort matrix. Do not invent one or present a new recommendation as an old agreement.
- Current recommendation: **KEEP GPT-6-Astra / Low for the final, narrowly scoped TTWO production operation, after the reset.** Reassess routine follow-up work for a cheaper model.
- Do not predict exact usage from task duration or remaining percentage. Model, context, reasoning, tool output and caching affect consumption. Current official guidance supports this uncertainty.
- Last supplied /status: 35% context remaining, 8% of the five-hour allowance remaining with reset shown at 16:21, 40% weekly remaining, 2,347 credits. These are a snapshot, not a live meter. Read a fresh status before relying on them.
- Avoid repeatedly printing large files, repeating completed research, expanding already sufficient tests, or initiating optional work that does not address a concrete remaining problem.

### Who runs reports
**Clay runs reports and long jobs in his own terminal. Codex reads the saved outputs.**
- When a report is needed, the assistant supplies the exact manual command and output path.
- The subsequent Codex prompt identifies those saved outputs and tells Codex to read them, not regenerate the report.
- Codex may prepare or fix report code within an authorized coding task. That does not authorize executing the report.
- Focused compilation, tests, and small diagnostics are distinct from report jobs. Do not relabel a report as a diagnostic to evade this rule.
- No full historical event rebuild, full price import, full SEC/XBRL import, universe-wide API job, or expensive analysis unless Clay explicitly requests that operation.
- A coding completion summary or test receipt is not permission to run an analytics report.
- When the boundary is unclear, give Clay the manual execution command and have Codex consume its saved result.

### Permissions, scope and data protection
- Check the working tree before editing and preserve unrelated changes.
- Use the smallest change needed. No unrelated refactoring, dependency upgrades, formatting sweeps, or architecture changes.
- The published AGENTS.md permits focused read-only schema/data inspection when needed; a task can impose a stricter boundary. Respect the current task's scope.
- Production changes, paper-trading behavior changes, migrations, bulk changes, service/timer changes, external side effects, and Git commits/pushes must be covered by the submitted task's explicit instructions. When already included, proceed without requesting the same authorization again.
- Do not place real trades. Do not send Gmail or Slack messages during tests without explicit authorization.
- Do not expose .env values, credential files, passwords, connection strings containing credentials, API keys, or tokens.
- Historical investment-club records are intentionally anonymized. Use only the established neutral names: Historical Portfolio, portfolio_history, and portfolio_history_YYYY_MM. Do not search for, infer, restore, or disclose the real identifying name.
- When committing, use a reviewed explicit file allowlist, not blanket staging.
- Do not weaken guards or modify historical data simply to make a test pass.
- This note records standing permission to finish an already authorized task; it does not initiate a new database operation or Git action.

## Project knowledge that must carry forward

### Purpose and architecture
- Market Intel is a personal stock-market research and prospective paper-trading system using SEC/XBRL financial data, filings, historical prices, backtests, signal research, scoring and notifications.
- Working repository: ~/projects/market-intel on the Ubuntu VM, normally accessed through VS Code Remote SSH. GitHub repository: ClayAucoin/market-intel.
- Python project with a virtual environment and PostgreSQL. Tiingo has been used for prices; SEC submissions and Company Facts are separate input sources.
- Keep raw provider evidence distinct from derived analysis. Preserve retrieval versions, provenance and reproducible inputs. Provider licensing assumptions need current verification before making retention decisions.
- Local AI is an optional component. Earlier planning used an ai_client abstraction and OLLAMA_BASE_URL so inference could move to the always-on Windows PC. An unavailable or overloaded model should not stop the ordinary data pipeline. This is a recovered design principle, not proof that the PC endpoint migration is complete.
- Historical index analysis requires dated membership and security/ticker identity. Current membership and current tickers cannot substitute for history.

### Research rules
- Research correctness takes priority over implementation convenience.
- Avoid lookahead bias. Use information that was available at the historical decision time.
- Preserve validated train/test boundaries, signal thresholds, holding periods, benchmark methodology, universe definitions and sector-confidence rules.
- Reuse established validated functions instead of quietly implementing different formulas.
- Earlier work used training through 2023-12-31 and testing from 2024-01-01. Treat this as historical context; inspect the current validated configuration before a new analysis.
- Distinguish historical simulation from prospective paper trading. Do not backfill a live paper account with historical signals.
- A changed historical return is not, by itself, a change in signal eligibility or evidence of improved strategy performance.
- Keep research evidence and proposed corrections separate from applied production changes.
- Historical security coverage, derived-fact lineage, vendor price vintages, and unresolved timestamps remain limitations that must not disappear from conclusions.

### Scheduled work and mutable event IDs
- The daily workflow runs through src/run_daily_market_intel.py. Retrieved earlier material described market-intel-daily.service and a weekday 17:00 Chicago schedule; verify current scheduling locally before relying on it.
- The historical event builder deletes and recreates events. IDs can change even when a security/period's calculated fields remain the same.
- TTWO event 398505 was replaced by 413248. Target a stable business key together with the reviewed current ID and exact before-image.
- A scheduled rebuild is a reason to recheck state, not permission to silently retarget a reviewed correction.
- Production filing refresh was inspected as reusing valid stored metadata. A separate non-production upsert path can overwrite acceptance timestamps. A one-off repair does not create a permanent source override.

### Timestamp source policy and completed work
- Preserve the completed 29,837-row safe acceptance-timestamp repair.
- Honor explicit Z and numeric offsets in submissions timestamps.
- Parse compact EDGAR header timestamps separately using the Eastern timezone.
- Never globally reinterpret Z as Eastern. Preserve raw evidence and retrieval versions, and surface source conflicts instead of silently selecting a new precedence.
- Independently verified headers are required before proposing exceptional-row repairs.
- The acceptance-source investigation found 22 ATVI/TWTR submissions values repeating Eastern header clock values while marked Z. Project extraction did not create those discrepancies; these cases did not intersect the saved repair/event population.
- All 103 current-issuer controls agreed; five exceptional CIEN/TTWO headers supported similar older-cache inconsistencies.
- No contradiction was found in the 65 checked safe repairs. This is a sampled finding, not an assertion that every possible row was revalidated.
- The investigation identified 71 exceptions and 205 evidence-missing rows. The single TTWO case does not resolve the whole population.
- Source-conflict detection and a general source-precedence policy remain separate design work. Do not quietly add them during the one-filing correction.
- Stage 3's header-based SIC conclusions were reported unaffected. Do not assume this alone authorizes scaling historical SIC work.

## Exact TTWO handoff

### Identity and sources
| Item | Value |
| --- | --- |
| Accession | 0001628280-25-026694 |
| CIK | 0000946581 |
| Filing / company | 108402 / 362 |
| Security / period | 358 / 2025-03-31 |
| Last reviewed event | 413248 |
| Obsolete event | 398505 |
| Form / filing date | 10-K / 2025-05-20 |
| Revenue fact | 547980 |
| Gross-profit fact | 548242 |

- Original saved submissions: 2025-05-20T06:32:02.000Z.
- Later saved submissions: 2025-05-20T10:32:02.000Z.
- Independently verified header: 20250520063202, meaning 06:32:02 Eastern / 10:32:02 UTC.
- Stored filing value in the reviewed live snapshot: 2025-05-20T14:32:02Z, or 10:32:02 Eastern.
- Proposed correction: 14:32:02 UTC to 10:32:02 UTC on May 20, 2025. The verified header and later submissions agree on the proposed instant.

### Reproduction and impact
The accepted earlier saved baseline was captured September 24 at 02:51:28 UTC. Fresh package inputs were captured September 25 at 16:52:38 UTC. All 31 event calculation fields reproduced from the captured current dependencies. No further drift was reported in the final read-only dry-run.

| Metric | Reviewed baseline | Proposed replacement |
| --- | --- | --- |
| Entry date | 2025-05-21 | 2025-05-20 |
| Adjusted opening price | $228.03 | $233.02 |
| 30-day exit | 2025-06-20 | 2025-06-20 |
| 90-day exit | 2025-08-19 | 2025-08-18 |
| 180-day exit | 2025-11-17 | 2025-11-17 |
| 20-session excess momentum | +0.67% | -1.38% |
| 30-day stock return | 4.53% | 2.30% |
| 30-day SPY return | 1.29% | 0.50% |
| 30-day excess return | 3.24% | 1.80% |
| Exact-signal eligibility | False | False |

Revenue acceleration remains 13.56%, below the 20% requirement; operating-margin change is missing. The alternative also fails positive momentum. Financial facts and financial metrics are not proposed for modification.

### Committed artifacts
- Acceptance investigation commit: b416f0e96448e61bbd89d1dcca024fddc75ca5e1.
- Correction package commit: bd402a59990d2cf20325b202fe7a91c308ee1f8f.
- Correction manifest SHA-256: fc032a801e529743dd476d2638dc3f52409f5e459f749381e579b5c5e7d7f3e4.
- Correction tool: src/backtesting/ttwo_acceptance_correction.py.
- Package: logs/research/ttwo_acceptance_correction_2026-09-25/.
- PostgreSQL test evidence: logs/research/ttwo_acceptance_pg_integration_2026-09-25/.
- Source investigation: logs/research/sec_acceptance_source_discrepancy_2026-09-24/.
- Earlier reproducible inputs: logs/research/timestamp_rebuild_2026-09-23/provenance_inputs.json.gz.
- Earlier provenance report: logs/research/timestamp_rebuild_2026-09-23/INTERVENING_REBUILD_PROVENANCE.md.

The latest completion report says 15 reviewed files were committed, the working tree was clean, and nothing was pushed. Do not assume those local commits are available from GitHub.

### Verification completed
- 32 focused regression tests passed.
- Five real PostgreSQL 18.6 checks passed in a separate disposable cluster: apply and post-write verification; rollback; atomic rollback after failure of the event update; correction lock timeout; exclusion of competing UPDATE/DELETE/INSERT operations.
- Only filing 108402 and event 413248 changed in the integration apply test.
- The disposable cluster was removed.
- The final production read-only dry-run returned DRY_RUN_READY.
- No production correction was reported as executed.

### Pending operation and stop conditions
The next intended action is one explicitly authorized application of the existing committed correction tool using the exact manifest pin, followed by its post-commit verification and a durable receipt.

The tool revalidates rows and dependencies under database locks; it preserves event identity, period and creation time and updates filing/event atomically. It aborts on drift, lock timeout, or a replacement event. Locks briefly exclude writers across the dependency tables.

Do not re-run research, refresh the manifest, change source precedence, perform a broad rebuild, or repair other exceptions as part of application. If anything fails or commit state is uncertain, inspect read-only and report the state. Do not automatically retry or roll back. An application receipt with its verified status is required before describing the production correction as completed.

Waiting may allow scheduled data changes to invalidate the pinned package. That means stop and review the mismatch; it does not justify bypassing the guard.

## Historical context that requires reconfirmation
An earlier September 19 conversation reported prospective paper-trading schema/migration work completed with a $10,000 starting cash balance, zero signals/positions and a NULL cutover, pending an SEC freshness fix. These are historical observations, not verified September 25 live balances or activation status. Later refresh or activation decisions were not fully recovered.

Earlier SIC pilots and follow-up studies had bounded sampling/request budgets. Their old budgets are not permission for new requests.

## Sources and coverage
- Clay's explicit September 25 communication correction: model KEEP/CHANGE guidance, user-run reports, saved results for Codex, and project continuity.
- Clay's subsequent September 25 instruction: complete already assigned work without repeated consent or "continue" prompts, including when Clay is away from the computer.
- Retrieved September 18 communication/role agreements; September 6 handoff discussion; August 31 architecture and workflow discussions; September 19 prospective-paper/freshness discussion. Retrieval was partial.
- User-supplied September 24–25 Codex transcripts, including Pasted text.txt, Pasted text(1).txt and Pasted text(2).txt.
- Published repository instructions read September 25: https://github.com/ClayAucoin/market-intel/blob/main/AGENTS.md, blob SHA 099c1f69bd7f79071ac4df0842402481e49c4eee. This is the fetched GitHub version; a newer local AGENTS.md must also be read in the repository.
- Current usage guidance read September 25: https://learn.chatgpt.com/docs/pricing.

No complete archive of all prior feeds was recovered. Do not claim that unknown historical decisions are settled. Use this note as a starting reference, then retrieve the specific missing decision or read the current authoritative project file before making a change. A saved note is not automatic synchronization with the Codex repository or a guarantee that every future chat will load it.
