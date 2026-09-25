# TTWO disposable PostgreSQL integration verification

**Five checks passed on PostgreSQL 18.6. No production write occurred.** The original correction source and manifest were unchanged; no defect fix or manifest supersession was required.

The runner creates a new cluster with initdb, uses a private owner-only Unix-socket directory, disables TCP, and checks data_directory, current database and system identifier on every connection. It redirects only the connection factory and artifact root. Actual correction SQL, snapshot queries, locking, transactions, calculations and receipt handling are unchanged and unmocked. Production configuration is not used for test connections.

Saved schema metadata was obtained through a database-enforced read-only production transaction. It preserves all ten tables' column types/nullability and primary, unique, check and foreign-key constraints. The existing paper-signal trigger is included. There are no user triggers on filings/backtest_events. The empty paper_accounts reference stub, synthetic company name/security is_primary and generated fixture price IDs supply required non-calculation fields; no production business input is substituted. Sequence/default machinery is unnecessary for the tested explicit-ID UPDATEs and is not reproduced.

Results in results.json cover:

- Actual apply and post-commit verification, with exactly filing 108402 and event 413248 changed across complete fixture tables.
- Actual rollback restoring business fields, IDs and creation times, while accepting PostgreSQL's new MVCC versions.
- An event-update CHECK violation rolling back the earlier filing update; no changed values or xmin remain.
- A dependency writer on another connection causing the correction's three-second lock timeout, without partial updates.
- Actual correction locks preventing concurrent UPDATE, DELETE and INSERT on separate connections.

The cluster was stopped and its files removed. Test-specific captured inputs, manifests and full execution receipts were confined to disposable roots and removed. No database dump, server log, temporary connection information or production execution receipt is retained. The saved production inputs/before-images/comparison remain byte-identical. A sandbox startup denial required running the local server outside the sandbox; it was an environment restriction, not a correction defect.

Reproduce from repository root using installed PostgreSQL 18 binaries:

```sh
PYTHONPATH=. .venv/bin/python -B tests/integration_ttwo_postgres.py --run
```

The runner requires permission to launch a local Unix-socket server. It does not need production database access or SEC/network retrieval. It uses the schema fixture here and references the captured correction inputs rather than copying them.

After integration, all 32 focused offline regression tests passed and the final production database-enforced read-only dry-run returned DRY_RUN_READY. Production application/rollback remain unexecuted. These tests verify this package, not arbitrary schema changes, future price/fact versions, or live scheduling conditions.
