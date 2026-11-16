# Railway portal on the Stack

An Express portal with accounts, owned records, private documents, and queued reports.
The [migration guide](../../../../docs/app-platform-migrations/from-railway.md) explains export, restoration, and rehearsal.

Run `npm ci` before using the commands below.

| Command | Purpose |
| --- | --- |
| `npm run migrate` | Apply ordered transactional migrations once during deployment |
| `npm start` | Listen on `PORT` with `WEB_CONCURRENCY` processes and `/healthz` |
| `npm run jobs` | Process reports and run the five-minute UTC archive schedule |
| `npm run cron` | Run the current archive occurrence once, then exit |
| `npm run seed-test-data` | Fill a laptop database or staging with invented test data; the fixed fixture uses `APP_URL` and runtime `FIXTURE_PASSWORD` |
| `npm run check` | Check application JavaScript syntax |

Web and jobs startup do not apply migrations. Deployment runs migrations before starting the new release.
`DATABASE_URL` lists the Stack database hosts and includes `target_session_attrs=read-write&connect_timeout=3`.
The copied `pg_with_multiple_database_servers.mjs` finds the primary for each new connection.
The portal reads through the primary pool. Requests with uncertain commits are never replayed automatically.

Set `NODE_ENV=production` behind HTTPS so login cookies have `Secure`.
Set `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY` for private object storage.
`S3_FORCE_PATH_STYLE=false` preserves Railway virtual-host addressing and selects R2 host-based addressing.
The loopback rehearsal uses `S3_FORCE_PATH_STYLE=true`.

The restored `controls.worker_paused` row pauses reports and scheduled work.
Only the administrator can change the worker pause through `/api/worker`.
Schedule receipts prevent duplicate archive work across concurrent job containers.
The archive schedule sets `archived_at` for completed reports older than 30 days and deletes no report row.
Missed schedule intervals are not replayed individually. The next successful occurrence archives all eligible reports.

Uploads and downloads are buffered. The 1 MiB upload limit bounds per-request memory use.
Accounts use bcrypt cost 12. Sessions remain in PostgreSQL and are revoked on logout across web servers.
Keep the migration SQL unchanged because `schema_migrations` checks each applied file's SHA-256.

## Acceptance contracts

- Returning users retain UUIDs and passwords after restoring PostgreSQL.
- Owners can read and change only their records, files, jobs, and report outputs.
- Downloaded bytes match the stored SHA-256 and length.
- Report claims use `FOR UPDATE SKIP LOCKED`. Report output and completion commit together.
- A disconnected job transaction rolls back, leaving unfinished work available.
- Migration 002 adds an empty-default description without changing existing record IDs.
- Sessions cross web servers. Logout revokes the shared session.
- Web and jobs exit cleanly on SIGTERM.
- Source and destination execute jobs in only one location during cutover.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
After the guide's local database and bucket setup, run migrations and start the app.
Set `APP_URL` to that app and supply `FIXTURE_PASSWORD`, then run from `app/`:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts use bulk SQL through
`DATABASE_URL`; they get one record each and no files or report jobs.
Reruns add missing rows, and a smaller count removes nothing.
