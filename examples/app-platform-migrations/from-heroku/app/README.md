# Customer portal after Heroku

This handwritten Express app keeps customers' invoice records, private documents, and record-count reports on independent PostgreSQL and S3-compatible services.
The migration retains the source UUIDs, bcrypt password hashes, SQL migrations, file keys, checksums, and queued or completed report rows.

Run `npm ci`, then `npm run migrate` before starting web or jobs containers.
`npm start` runs WEB_CONCURRENCY web processes on PORT.
`npm run jobs` supervises the report worker and daily UTC clock together, matching the Stack's one jobs command.
With JOBS_PAUSED=true, reports stay pending and the combined jobs command does not start the clock.
Set JOBS_PAUSED=false and restart the jobs container only after the isolated destination is ready to execute work.
ARCHIVE_DAILY_UTC_TIME selects HH:MM in UTC. The default is 00:00.
A restart after today's selected time catches up through the unique schedule_runs occurrence.

The database module copies the Stack's unchanged Node primary-discovery helper.
DATABASE_URL lists database servers with target_session_attrs=read-write and connect_timeout.
Queries have deadlines. Requests with an uncertain commit are never automatically replayed.
DATABASE_SSL=false selects the Stack's WireGuard transport. The source's Heroku TLS setting must not be carried into a plain WireGuard connection.

S3_ENDPOINT, S3_REGION, S3_BUCKET, and S3_FORCE_PATH_STYLE select destination storage.
S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY must be scoped destination credentials.
COOKIE_SECURE=true is required behind hosted HTTPS. Use false only in the disposable loopback rehearsal.
NODE_ENV=production selects deployment operation. PORT and WEB_CONCURRENCY come from the Stack.

`npm run seed-test-data` creates its fixed invented fixture through the running laptop or staging portal.
The seed requires `APP_ENV=development` or `APP_ENV=staging`, `APP_URL`, and `FIXTURE_PASSWORD` at runtime.
Existing fixture accounts, passwords, records, documents, and jobs are preserved on rerun.

The Dockerfile runs Node 24.22.2 and installs the exact dependency lockfile.
The image's default command starts the web process. The Stack supplies separate migration and jobs commands.
No database export, fixture password, source credential, or uploaded file belongs in the image.

The [migration guide](../../../../docs/app-platform-migrations/from-heroku.md) describes export, restore, acceptance checks, and the remaining Stack proof.

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
