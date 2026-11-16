# Customer portal after a Vercel export

## Variances and guidance needs

This app replaces managed Neon Auth, private Vercel Blob, request-scoped reports, and Vercel Cron.
The [migration guide](../../../docs/app-platform-migrations/from-vercel.md) gives preparation, export, import, rehearsal, and later deployment steps.
The [test record](testing.md) separates phase 1 proof from live cutover work.

Copy this directory into your app repository. Use Node 24, PostgreSQL, and a private S3-compatible bucket.
Run `npm ci`, `npm test`, and `npm run build` without database credentials.
Apply migrations with `npm run migrate` before starting `npm run web` or `npm run jobs`.
The guide lists every required environment variable.

## Acceptance contracts

- Export source identities, password hashes, stable IDs, ownership, object metadata/bytes, job output/state, schedule history, and configuration names.
- Preserve source IDs and native password hashes. Require a fresh login and share revocable destination sessions through PostgreSQL.
- Refuse foreign ownership, invalid request origins, corrupt file exports, conflicting snapshots, and nonempty first-import databases.
- Process jobs through transactional row locks. Commit report output and completion together.
- Coordinate the daily 03:00 UTC archive through PostgreSQL. Retain report output.
- Apply ordered migrations once, support additive descriptions, use configured ports/workers, and shut down gracefully.
- Use the unchanged Stack multi-host PostgreSQL helper. Never automatically replay an uncertain request.
- Keep source services read-only during phase 1. Claim a live migration only after the separate cutover proof.

The private archive and canonical snapshot must stay outside Git and image build contexts.
The source fixture has password identities only. Unsupported identity states require explicit mappings before import.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
Use the guide's local database and bucket settings and run migrations first.
Supply `FIXTURE_PASSWORD` and run:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts get one owned record each
and no documents or report jobs. Reruns add missing rows; a smaller count removes nothing.
