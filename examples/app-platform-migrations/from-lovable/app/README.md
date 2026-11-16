# Independent customer portal

This app keeps the exported TanStack Start pages and replaces Lovable Cloud with Postgres and private S3 storage.

Read the [migration guide](../../../../docs/app-platform-migrations/from-lovable.md) before using customer exports. Read the [file and service map](../design.md) to understand the generated app.

`settings.example.env` lists every required setting. Keep real values in a private file outside the repository. Use a new database and a separate bucket for rehearsal.

Build with Node 24 and `npm ci`, then `NITRO_PRESET=node-server npm run build`. Run `npm run migrate` before `npm start`.

The separate commands are `npm run jobs`, `npm run seed-test-data`, and `node operations.mjs maintenance`. Leave jobs and maintenance stopped during rehearsal import.

`npm run rehearse` imports the supplied synthetic snapshot into an empty database and tests two web servers. The migration guide lists the required inputs.

The rehearsal requires exactly the two synthetic accounts described in the guide. The importer requires the matching exported portal schema. Adapt another Lovable app before using this example.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
Use the guide's local database and bucket settings and run migrations first.
Supply `FIXTURE_PASSWORD` and run from `app/`:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Extra accounts get one owned record each
and no documents or report jobs. Reruns add missing rows; a smaller count removes nothing.
