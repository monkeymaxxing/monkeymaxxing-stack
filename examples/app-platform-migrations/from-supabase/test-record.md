# Supabase migration test record

Verified on PostgreSQL 17.11 and Node.js 24.22.2, on Debian 13.
The source ran PostgreSQL 17.11 with a manually authored React frontend and native Supabase services.
The source project and its temporary frontend were removed after phase-1 verification.

## Real source

Two synthetic users registered through Supabase Auth and created owned records, private files and pending jobs through native application endpoints.
Both users passed owned reads, guessed-ID refusals, record mutations, exact file-byte checks, CRUD, browser login and logout.
The first real deployment used the initial schema. A second deployment added descriptions and preserved existing rows.
One extra report completed with exact output `record_count=1` followed by LF.
The scheduled minute task produced real occurrences before being disabled for export.

## Export

The reusable exporter ran against the real frozen source using customer-scoped APIs and PostgreSQL 17 tools.
Its complete snapshot matched the separately recorded source facts and first export after normalizing row order.
Both private documents matched their recorded SHA-256 values.
The native archive's original `auth.users` table was restored separately. UUIDs, emails and bcrypt hashes matched the snapshot.
The original code archive, lockfile, function body, service settings, cron definitions/history and variable names were retained privately.

## Final fresh replay: 15 checks passed

2026-11-05: `seed-test-data` now fills laptops or staging, recognizes its fixed/generated accounts, and refuses unrelated accounts before any row changes or uploads. JavaScript syntax checks passed. On isolated Debian 13, Node 24.22.1, PostgreSQL 17.11 and pinned S3Mock, `node --test tests/seed-test-data.test.mjs` passed 1 test, proving both allowed environments, production/unset refusals, exact fixture preservation, 1,000 accounts twice, growth, smaller-count preservation no database or bucket changes on unrelated-account refusals, and the original minimum-character/maximum-byte password guards. `npm run build` passed; the existing `node tests/rehearse.mjs` passed all 15 checks and `node tests/restore-proof.mjs` passed all 4 checks using their own S3rver and a fresh synthetic snapshot. No source service was accessed and no new container image is claimed.

- The first ordered migration works alone.
- `WEB_CONCURRENCY=2` starts two workers on each instance's shared port.
- The additive migration preserves data and sessions with web instances running. Reapplying migrations changes nothing.
- Unsupported identities, active source cron and unsafe file keys are refused.
- The export imports once and refuses a populated destination.
- UUIDs, hashes, identities, descriptions, file references, bytes and job outputs are preserved.
- Barbara retains the password, shared session, CRUD and private file access, with other-owner requests refused.
- Michael passes the same checks.
- Unauthenticated reads and cross-origin writes are refused.
- Concurrent workers complete each imported pending job once with its owner's record count.
- Killing an open transaction leaves its job available to another worker.
- The source schedule is preserved. Concurrent minute tasks record one occurrence.
- Logout on one web instance revokes access through the second.
- New registration works after leaving Supabase.
- Both clustered web instances stop gracefully.

A separate direct validation check also refused an unrecognized application column before import.

## Logical restore: 4 checks passed

Every app table matched after a custom-format database archive was restored into another empty PostgreSQL database.
The comparison covered password hashes, active sessions, pending/completed jobs, outputs, schedules and migration checksums.
Private bytes were copied into a distinct restore bucket and verified independently of SQL.
The restored app accepted an active session and the original Supabase password.
A restored HTTP download matched the original hash, and a pending report remained pending.
The restored app also passed a browser login, owned-record and logout check.

## Pruned production runtime: 8 checks passed

After `npm prune --omit=dev`, development services and the Supabase client were absent.
The required server, password, database and S3 libraries remained available.
Built browser JavaScript contained no source Supabase endpoint.
Database-backed health, original-password login, owned data, logout and graceful clustered shutdown passed.
The lockfile remained byte-identical. The production-only audit reported zero vulnerabilities.
The development installation reported four advisories in development dependencies: one moderate and three high.
Those development dependencies are excluded from the runtime image.

## Remaining boundaries

No full Stack deployment, public destination cutover, primary promotion, PgBouncer behavior or real R2 permission test is claimed.
The Containerfile is supplied; this phase tested its install/build/prune sequence and runtime without building the container image.
Source sessions deliberately require a new login at the destination.
Email confirmation was disabled for synthetic accounts. Recovery email, OAuth, SSO, anonymous accounts and MFA need a separate design.
The schedule records current minutes and does not catch up missed minutes after downtime.

- 2026-11-05: Invalid `--accounts` checks now require the exact usage message on stderr and unchanged database rows. The seed suite and full isolated service rehearsal passed with PostgreSQL 17 and S3-compatible storage. Non-canonical generated email names were refused with every database row and storage object unchanged. The build and restore proof passed.
