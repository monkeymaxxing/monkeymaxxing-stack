# SvelteKit customer portal

Accounts, owned records, private S3 documents and PostgreSQL report jobs on Node 24.
Copy the whole directory into your application repository.
Follow [the guide](../../../docs/app-frameworks/sveltekit-pg.md) before building or running.
See [design.md](design.md) for boundaries and [testing.md](testing.md) for measured proof.

## Administrative replica report

Run `node scripts/replica_report.mjs` with the Stack environment available.
The report uses `DATABASE_READ_URL` for a stale record count and `DATABASE_URL` to identify the primary.
The report prints the server address and database role for each connection.
HTTP sessions, immediate reads, and job transactions stay on the primary.
The report includes all accounts and is an administrator command.

The replica report must select a standby when available and fall back to a reachable primary.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development bin/portal seed-test-data
```

`bin/portal seed-test-data --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
Production data stays on production servers. Add a missing data shape to the seed or a test.
