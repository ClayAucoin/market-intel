Market Intel — Codex Instructions
Project purpose

Market Intel is a personal stock-market research and paper-trading system. It combines SEC/XBRL financial data, historical prices, filings, backtesting, signal research, scoring, paper trading, and notifications.

Research correctness is more important than implementation convenience.

Human decision authority

Codex performs implementation, inspection, testing, debugging, and other mechanical engineering work.

Do not independently change investment strategy, signal definitions, scoring methodology, portfolio rules, research methodology, or production behavior unless the task explicitly instructs you to do so.

If completing a task would require making one of those decisions, stop and report the decision that is required rather than choosing one yourself.

Research integrity

Never introduce lookahead bias.

All historical analysis must use only information that would have been available as of the historical analysis date.

Preserve point-in-time S&P 500 membership when performing historical index analysis. Do not substitute current index membership for historical membership.

Preserve historical security identity and ticker history. Do not assume a security's current ticker was its ticker at every historical date.

Do not silently change train/test boundaries, signal thresholds, holding periods, benchmark methodology, universe definitions, sector-confidence rules, or other validated research assumptions.

Prefer existing validated project functions over duplicating established logic.

Historical Portfolio privacy

Historical investment-club data in this repository is intentionally anonymized.

Never add, infer, restore, search for, or expose the investment club's real identifying name.

Use only the neutral names already established by the project, including:

Historical Portfolio
portfolio_history
portfolio_history_YYYY_MM

Do not place identifying investment-club information in source code, database values, filenames, reports, logs, comments, commit messages, or generated output.

Secrets and credentials

Never display, print, log, summarize, copy, commit, or expose secret values.

This includes .env contents, database passwords, connection strings containing credentials, API keys, OAuth tokens, Gmail credentials, Slack credentials, Tiingo credentials, Alpha Vantage credentials, and files under credentials/.

You may determine whether required configuration exists without displaying its value.

Never add secrets or credential files to Git.

Production safety

Do not modify production or paper-trading behavior unless explicitly instructed.

Do not place real trades.

Paper trading must remain prospective. Do not retroactively manufacture paper trades from historical signals unless an explicitly requested research simulation requires it and keeps those simulated results separate from the prospective paper account.

Do not start, stop, enable, disable, or modify systemd services or timers unless explicitly instructed.

Database safety

Inspecting database schema or running focused read-only queries is allowed when needed for a task.

Do not run migrations, destructive SQL, bulk deletes, database rebuilds, or large data modifications unless explicitly instructed.

Do not alter established historical data merely to make a test pass.

Expensive and long-running operations

Do not run expensive or long-running operations unless explicitly instructed.

In particular, do not run the full historical backtest-event rebuild, full historical price imports, full SEC/XBRL imports, universe-wide external API imports, or other jobs known or likely to take substantial time.

Prefer py_compile, focused unit tests, small read-only diagnostics, and targeted tests when validating ordinary code changes.

If you believe a long-running operation is required, stop and report the exact command you recommend and why it is necessary. Wait for explicit approval before running it.

External services

Do not make external API calls, send Gmail messages, send Slack messages, or perform other external side effects during ordinary testing unless explicitly instructed.

Do not assume network access is required merely because production code normally uses an external service.

Git

Do not commit, push, reset, rebase, force-push, or otherwise rewrite Git history unless explicitly instructed.

Before modifying code, check the working tree. Do not overwrite unrelated user changes.

At the end of a coding task, report which files changed.

Testing

After modifying Python code, run appropriate lightweight validation.

At minimum, compile changed Python files with python -m py_compile or the project's .venv Python.

Run focused tests when they exist and can be completed without triggering expensive jobs or external side effects.

A test failure must be reported; do not hide it or alter unrelated behavior merely to make the test green.

Scope discipline

Make the smallest change that correctly completes the requested task.

Do not perform unrelated refactoring, cleanup, dependency upgrades, formatting sweeps, or architectural changes unless explicitly requested.

When investigating a bug, establish the cause before changing trusted central code when practical.

Completion report

At the end of every implementation task, report:

What you changed.
Which files changed.
What validation/tests you ran.
The results of those tests.
Anything you deliberately did not run because it would be expensive, destructive, or externally visible.
Any remaining uncertainty or decision that requires human input.
