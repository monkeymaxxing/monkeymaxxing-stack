# Dokku customer portal

This independent app keeps the Heroku example's accounts, records, sessions, jobs, and migration ledger.
`UPLOAD_DIR` selects the private local mount on the Dokku source. Without `UPLOAD_DIR`, storage uses the S3 settings.

Run `node migrate.mjs` before web and workers. `node web.mjs` listens on `PORT` and uses `WEB_CONCURRENCY` processes.
`node jobs.mjs` handles PostgreSQL report jobs. `JOBS_PAUSED=true` keeps the worker idle.
`node schedule.mjs` runs the daily archive once per UTC date. The source uses `app.json`; the destination uses the separate MMX timer.

[The migration example](../README.md) explains setup and verification.
