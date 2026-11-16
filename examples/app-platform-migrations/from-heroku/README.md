# Heroku migration example

## Variances and guidance needs

This example moves a handwritten Heroku customer portal onto independent PostgreSQL and S3-compatible storage.
Heroku's native source uses web, worker, and clock dynos, Essential Postgres, and an external private object store.
Heroku has no native object storage.

The [guide](../../../docs/app-platform-migrations/from-heroku.md) covers the full export and standalone rehearsal.
The source's PostgreSQL 18 export must be restored on PostgreSQL 17 before compatibility is claimed.
The exporter preserves every row in this fixture's seven application tables, including password hashes, session state, job output, and migration checksums.
The exporter separately retains code, current bucket objects, source schedule settings, and variable names.
Provider-owned _heroku and pg_stat_statements instrumentation are excluded from the application dump.
A different application must inventory additional tables, functions, extensions, and integrations before adapting the table list.

## Acceptance contracts

- Accounts retain UUIDs and bcrypt verifiers, and returning users can use their existing passwords.
- Every record, document, and report keeps its owner. Guessed IDs cannot cross the ownership boundary.
- SQL restores every application row exactly before any destination process creates new session or work rows.
- Object downloads match the source keys, byte lengths, and SHA-256 values separately from the database restore.
- Pending and completed jobs retain state and output. Only the chosen execution location may run jobs and schedules.
- Concurrent report workers lock different pending rows. An interrupted transaction leaves unfinished work available.
- The daily UTC archive commits one occurrence despite overlapping clock runs or restart catch-up.
- The Stack's one jobs command runs reports and clock work, and stops the process group cleanly.
- The Node database helper accepts the Stack multi-host URL. Real failover and Stack recovery remain separate empirical checks.
- Source services and source bucket objects are removed only after the protected export and independent replay pass.

## Contents

`app/` holds the portable app and Dockerfile.
`data-transfer.mjs` exports and restores protected code, SQL, exact rows, and file bytes.
`tests/prepare-rehearsal.py` creates an isolated PostgreSQL role/database and private destination settings.
`tests/create-rehearsal-bucket.mjs` creates the separate S3-compatible test bucket.
`tests/rehearsal.mjs` exercises the restored copy. The rehearsal changes data and must never target a live application.
