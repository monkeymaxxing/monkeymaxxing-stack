# Move a Netlify app to your own system

## Variances and guidance needs

Netlify Identity does not offer customers a normal self-service password-hash export.
Users keep their accounts, emails, IDs, and owned data, but must set a new password on the Stack.
The destination sends a one-time reset link to the existing account email.
A verifier export supplied by Netlify support is an optional exception. Do not hold the migration open while chasing that route.

A Netlify repository export also omits live Database rows, Blobs objects, account metadata, runtime settings, and queued work.
Export every service separately and compare the results before deleting anything.
The [destination example](../../examples/app-platform-migrations/from-netlify/README.md) contains the complete React portal, web process, jobs process, migrations, reset delivery, and import tools.

## Identify the customer's actual backend

Inventory the source URL, site ID, production database branch, framework, dependency locks, and runtime versions.
Record authentication, private storage, function settings, schedules, and environment-variable names.
Keep secret values in private files outside the source checkout.

Bolt apps may use Netlify hosting with a separate backend.
Inspect the code and service panels before assuming Netlify Identity, Database, or Blobs holds the customer's data.
A Supabase-backed Bolt app needs Supabase's own account, data, and storage export routes.
Bolt Database also needs its authorized backend export route.
The tested fixture was hand-written on Netlify. No Bolt-generated app or Bolt account export was tested.

## Source and destination responsibilities

| Part | Netlify source | Destination |
| --- | --- | --- |
| Browser interface | React and Vite | Retained React interface, built as static files |
| HTTP API | Modern Netlify Functions | Persistent Express web process |
| Accounts | Netlify Identity | Same IDs and emails, with app-owned passwords after a one-time reset |
| Sessions | Native Identity plus application session hashes | New shared Postgres sessions. Source sessions are discarded. |
| Records and metadata | Netlify Database, backed by Neon | PostgreSQL 17 |
| Private bytes | Named Netlify Blobs store | Private S3-compatible bucket with unchanged keys |
| Reports | Background Function and Postgres rows | Separate jobs process with transactional `SKIP LOCKED` claims |
| Daily archive | Native Scheduled Function | UTC schedule and durable occurrence history in Postgres |
| Mail | Native Identity emails | Destination SMTP delivery, configured before customer cutover |

The source database ran Postgres 18.6. A logical dump from that source was separately restored into isolated Postgres 17.11.
The destination app imports the verified row audit into its own schema.
Do not restore the original source dump over the destination app's tables.

The source frontend's API client is adapted for the portable server routes.
The [example README](../../examples/app-platform-migrations/from-netlify/README.md) names each command and configuration setting.
Source code and dependency locks remain in the protected archive for comparison.

## Export a consistent source snapshot

Pause application writes, report processing, and scheduled work before the final export.
Wait for active transactions to complete or roll back.
Keep the source available for rollback until destination checks pass.

Use a mode-700 export directory and `umask 077` so exported files have mode 600.
Use the production branch's connection details. Netlify preview branches are separate databases.
Use a `pg_dump` client matching or newer than the source server.
The exporter shares one repeatable-read snapshot between the dump and full row audit.
The manifest checksums the dump and audit separately.

The supplied exporter covers the fixture's public schema and ownership tables.
Adapt table and schema selection for a different application.
A source-only schema extension must not silently disappear from the export.

Export code through the customer's repository or supported download, with its revision and archive SHA-256.
Include migration files, `netlify.toml`, redirects, function code, build rules, and dependency locks.
The service exporter records native function runtime, background mode, cron settings, and variable names.
The exporter never places service credentials in frontend code.

Download Blobs separately from SQL.
Match every database object reference against the complete native store listing.
Verify each downloaded object's key, byte length, and SHA-256.
A database backup cannot recover object bytes.

## Preserve accounts and explain the password change

The ordinary Identity API exports native account IDs, emails, metadata, and confirmation timestamps without password hashes.
The tested verifier-export request returned `Invalid export secret`.
That route depends on a separate operator secret and is not a normal customer export.
No further verifier-export request or support contact is required by this workflow.

Tell returning users before cutover: their account and private data remain, but their first Stack login requires a new password.
Send reset mail to the stored account address. Do not link accounts merely because another record has an equal email address.
Preserve the native Identity issuer and subject mapping alongside the unchanged application user ID.
Retain native profile metadata and source schema history for audit and later adaptation.

The importer creates accounts with NULL password hashes.
Old Netlify passwords cannot authenticate until the user sets a new password.
Do not hash a known fixture password during import and describe the result as preserved native credentials.
If Netlify support supplies an actual verifier export, validate the format and destination verifier separately before changing this route.

Source sessions depend on native Identity and are deliberately discarded.
Returning users log in again after resetting. Already issued source cookies do not grant destination access.

## Configure one-time reset delivery

Configure `PUBLIC_APP_URL`, `SMTP_URL`, and `MAIL_FROM` before opening the destination to customers.
`PUBLIC_APP_URL` is the canonical HTTPS origin. A request's Host header never chooses the reset-link host.
SMTP uses TLS. Credentials remain in the private runtime env file.
Verify real mailbox receipt and sender configuration before a live customer cutover.
The fixture rehearsal uses a protected file mail sink instead of contacting the invented example.com addresses.

The reset form queues the same response and request shape for known and unknown emails.
The jobs process generates and delivers the token only for an existing account.
The per-address one-minute throttle is shared across web processes.
Add public-edge rate limits for login and reset requests to control broader automated abuse.

Each token contains 256 random bits and expires after thirty minutes.
Only the SHA-256 token hash is stored in the token table.
Mail delivery contains the token, so staging mail files and operational mail logs must remain private.
Tokens appear in URL fragments. The reset page clears the fragment and submits the token in a POST body.
The reset page has no third-party resources and sends no referrer.

A newly issued token invalidates earlier links for the account.
Password replacement, token consumption, other-token invalidation, and session revocation commit together.
Concurrent use of the same link has exactly one successful result.
Login verifies the password and creates its session under the same user-row lock as reset, preventing an in-flight old-password login from escaping revocation.
A password must contain twelve characters and at most seventy-two UTF-8 bytes, avoiding bcrypt's truncation boundary.
The user confirms the new password and then logs in normally. Reset does not automatically sign the user in.

The jobs process handles reset mail even while report processing remains paused.
Temporary SMTP failures leave the request pending for another attempt after one minute.
An interrupted delivery may leave an earlier email with an invalid link. The latest successfully issued link is the usable link.
Never expose reset tokens in HTTP responses, access-log URLs, shared screenshots, or public reports.

## Import and prove the destination

Create a fresh dedicated PostgreSQL 17 database and private S3-compatible bucket.
Run migrations, import object bytes, then import the verified account and application rows.
The importer maps source table names to destination names without changing ownership IDs:

| Source | Destination |
| --- | --- |
| `application_users` | `users`, with NULL password hashes |
| Native Identity IDs and metadata | `identities` and `source_identity_metadata` |
| `records` | `records`, retaining descriptions and timestamps |
| `documents.file_name` | `documents.filename`, retaining keys and hashes |
| `report_jobs` | `jobs`, retaining pending state and completed output |
| `scheduled_runs.occurrence_date` | UTC `scheduled_runs.occurrence_at` |
| `portal_schema_migrations` | `source_schema_migrations` |
| `application_sessions` | Discarded, because native sessions are replaced |

An import ledger makes a repeated identical snapshot safe.
Reimport does not reset a newly set password or overwrite destination changes.
A different snapshot or unrelated nonempty destination is refused.
The object importer preserves matching bytes and refuses a different existing object.
Destination writes, reports, and scheduling remain paused until the operator enables the controls.

For each imported user, request a reset link, set a new password, and log in.
Confirm the original user ID, email, record IDs, owners, private-file keys, and exact downloaded bytes.
Reuse the session on a second web process, then prove logout and later resets revoke the session everywhere.
Check expired, invalid, replaced, reused, and concurrently redeemed reset tokens.
Check cross-owner CRUD, downloads, and report reads.
Run concurrent workers, interrupt an open job transaction, and verify pending work can complete once.
Check the preserved completed output and deduplicated daily schedule.

Run an independent replay from a fresh copy and empty database/bucket.
The [test record](../../examples/app-platform-migrations/from-netlify/testing.md) states measured checks and the remaining live-deployment boundaries.
The included Stack driver discovers the database writer from the configured host list without automatically replaying uncertain writes.
A full Stack deployment and live primary promotion remain separate deployment checks.

## Cutover and source deletion

Before routing real traffic, verify SMTP receipt, canonical HTTPS URLs, private storage permissions, backups, and the intended rollback window.
Run exactly one report worker and schedule execution location during cutover.
Start destination web and jobs processes separately. Web startup does not run migrations or background work.
`seed-test-data` fills a developer's laptop database or staging with invented test data. Use a separate database and bucket; all new test accounts require a password-reset link.

After the authorized rehearsal passes, retain protected exports and delete only the source project's Blobs, Database, Identity instance, and site.
Database deletion must use the dashboard's Data & storage → Database → Delete database action.
The API returned HTTP 401 with `This operation must be performed from the Netlify dashboard.`, despite personal-token write access.
The dashboard confirmation removes all database branches and managed backups. Type `delete` only after verifying the intended source project.
Confirm empty or absent native data services before deleting the site, then verify the site ID is absent and its URL no longer serves the app.
Do not delete unrelated projects or the retained code and export evidence.
The tested source was deleted after destination reset/login, data checks, and independent replay passed.

## Free-plan and native-service guidance

The source used credit-based Free with a 300-credit allowance and disabled credit overages.
Two production deploys were made. [Netlify credit documentation](https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/how-credits-work/) lists fifteen credits per production deploy.
Function and Database compute, requests, and bandwidth also consume credits.
Capability counters remained stale after deploys, so counters were not treated as final billing evidence.

The [Database limits](https://docs.netlify.com/build/data-and-storage/netlify-database/billing-and-usage/) list three databases, twenty branches, and five-minute idle sleep on Free.
The source dashboard confirmed one compute unit, three-day daily backup retention, and the last published-deploy backup.
The documentation lists five GB of storage, monthly writes and outgoing bandwidth, plus forty-eight monthly compute units.
Storage-billing text still names July 2026. Check current account metering instead of assuming indefinite free storage.

[Background Functions](https://docs.netlify.com/build/functions/background-functions/) allow fifteen minutes on credit-based Free.
[Scheduled Functions](https://docs.netlify.com/build/functions/scheduled-functions/) have thirty seconds and run automatically only for published deploys.
The deployed source functions used 1024 MB and twenty-four-hour log retention.
New projects can start private behind Netlify team login. Production visibility needed an explicit Public setting for customer access.
Previews remained Private.

Identity confirmation settings were under Registration → Configure in the tested dashboard.
The documentation's Emails-panel route led to a Pro upgrade panel.
Custom email settings, Identity audit logs, and removal of the public Netlify badge showed paid-plan boundaries.
No paid plan or trial was started.

[Blobs limits](https://docs.netlify.com/build/data-and-storage/netlify-blobs/#requirements-and-limitations) include five GB per object, two KB metadata, sixty-four-byte store names, and six-hundred-byte keys.
The fixture uses a smaller one MiB application transfer limit because uploads are buffered in memory.

## Fill a laptop or staging with test data

After the local database and bucket setup, run migrations and then:

```sh
APP_ENV=development npm run seed-test-data
```

Use `APP_ENV=staging` for staging. `npm run seed-test-data -- --accounts 200000`
makes enough rows to show slow queries. The count includes the two fixed accounts.
Generated accounts also have no password and use the existing reset-required policy.
They get one owned record each, no documents and no report jobs. Reruns preserve
chosen passwords and existing rows. A smaller count removes nothing.
