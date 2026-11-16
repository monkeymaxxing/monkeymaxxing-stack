# Private customer portal with TanStack Start and PostgreSQL

Keep account-owned records and private documents, then queue reports that count
only your records. The app runs on Node 24 with TanStack Start, pg and an S3 API.

Start with the [guide](../../../docs/app-frameworks/tanstack-start-pg.md).
The [design](design.md) explains module boundaries.
The [test record](testing.md) states what passed and what still needs a live Stack run.

Copy this whole directory into your app repository. Run commands from the copied
directory. The guide in the Stack repository remains the setup reference.

```sh
npm ci
npm test
npm run build
npm run typecheck
npm run migrate
npm start
```

Supply the protected runtime settings described in the guide before migration or
startup. The build needs no app secrets. Start `npm run jobs` separately.
`npm run seed-test-data` requires `APP_ENV=development` or `APP_ENV=staging` and `FIXTURE_PASSWORD`.
Use HTTPS for browser sessions. The image's default command is
`node scripts/web.mjs`; migration and job commands override the image command.

## Administrative replica report

Run `node scripts/replica_report.mjs` with the Stack environment available.
The report uses `DATABASE_READ_URL` for a stale record count and `DATABASE_URL` to identify the primary.
The report prints the server address and database role for each connection.
HTTP sessions, immediate reads, and job transactions stay on the primary.
The report includes all accounts and is an administrator command.

The replica report must select a standby when available and fall back to a reachable primary.

For laptop test data, migrate against your local PostgreSQL database and local bucket, then run:

```sh
APP_ENV=development node scripts/manage.mjs seed-test-data
```

`node scripts/manage.mjs seed-test-data --accounts 200000` makes enough invented rows to show slow queries.
The total defaults to two accounts. Larger totals add accounts and owned records without extra documents or reports.
Production data stays on production servers. Add a missing data shape to the seed or a test.
