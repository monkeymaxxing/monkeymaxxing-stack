# Netlify migration example

## Variances and guidance needs

Netlify Identity does not provide customers a normal self-service password-hash export.
Returning users keep their accounts, emails, IDs, records, and private documents, but must set a new password on the Stack.
The app delivers an expiring one-time link to the existing account email, then asks the user to log in normally.
A verifier export supplied by Netlify support is an optional exception. This example uses the tested reset route.

The source React interface is retained. Express replaces Netlify Functions, PostgreSQL owns accounts and sessions, and S3-compatible storage replaces Blobs.
The [migration guide](../../../docs/app-platform-migrations/from-netlify.md) explains exports, mappings, communication, and later cutover.

## Install and configure

Use Node 24 and PostgreSQL 17. Run `npm ci`, then `npm run build`.
The frontend build writes `web/client/`. The source lives under `frontend/`.
Copy `environment.example` into a mode-600 file outside the checkout and replace every placeholder.
The container image excludes env files, private exports, mail files, and tests.

| Setting | Purpose |
| --- | --- |
| `DATABASE_URL` | Dedicated destination database. The included Stack driver accepts multiple database hosts. |
| `PORT`, `WEB_CONCURRENCY` | Web listener and number of web processes |
| `PUBLIC_APP_URL` | Canonical HTTPS origin used for reset links. Never derived from a request's Host header. |
| `SMTP_URL`, `MAIL_FROM` | Production SMTP delivery, with TLS and the configured sender |
| `APP_ENV` | `development` for a laptop, `staging` for isolated checks, `production` for the live app; the test-data seed refuses production |
| `PASSWORD_RESET_EMAIL_DIR` | Staging-only private mail sink. Do not set in production. |
| `AUTH_MIGRATION_MODE` | Set to `reset-required` to acknowledge that imported accounts need a new password. |
| `NETLIFY_EXPORT_DIR` | Protected source export directory, outside the checkout |
| `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET` | Private destination object storage |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | Runtime storage credentials |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | The same storage credentials for the export object-import tool |
| `S3_FORCE_PATH_STYLE` | Set to `true` for the object importer. The runtime uses path-style S3 requests. |

The production SMTP URL format is `smtps://USER:PASSWORD@smtp.example.com:465`.
Percent-encode reserved characters in the private URL's user and password.
No SMTP password or reset token belongs in a command argument or report.

## Export the source

Create a private inventory file with the real site ID, source URL, team slug, Identity instance ID, and source code revision:

```json
{
  "site": {
    "id": "11111111-1111-4111-8111-111111111111",
    "ssl_url": "https://portal.example.com",
    "account_slug": "your-netlify-team"
  },
  "identity_instance_id": "your-native-identity-instance-id",
  "source_repository": {"url": "https://github.com/example/portal", "commit": "your-source-commit"}
}
```

Pause source writes, report processing, and scheduled work before the final export.
Load `NETLIFY_AUTH_TOKEN` privately, then run:

```sh
umask 077
export NETLIFY_SOURCE_FACTS_FILE=/absolute/path/to/private/source_facts.json
export NETLIFY_DATABASE_URL_FILE=/absolute/path/to/private/database_url
export NETLIFY_EXPORT_DIR=/absolute/path/to/private/export
export PG_DUMP_BIN=/absolute/path/to/pg_dump
npm run export-netlify
npm run verify-export
```

Use a `pg_dump` client matching or newer than the source server. The tested source used PostgreSQL 18.6.
Choose an empty export directory, so an earlier backup cannot be overwritten.
Export source code separately through the customer's repository and record the archive hash alongside the revision.

The export includes a consistent dump, full row audit, native identity metadata, exact object bytes, function settings, and variable names.
The dump and audit share one repeatable-read snapshot. The manifest checksums the dump and audit separately.
The exporter expects this fixture's public schema. Adapt table and schema selection for a different app.
The exporter does not request native password hashes.

## Import into an empty destination

Load the private destination settings before running each command.
Create an empty dedicated database and private bucket using the storage provider's normal tools.
Do not restore the source dump over the destination app's schema. The importer maps the verified audit into the destination schema.

```sh
npm run migrate
npm run import-objects
npm run import-netlify
```

The importer keeps user, record, document, and job IDs unchanged.
The source Identity subject remains mapped to the same user ID. Native identity metadata and source migration history are retained.
Source sessions are discarded. Imported password hashes are NULL, so no old password can authenticate before reset.
A repeat import of the same snapshot preserves newly set passwords and other destination changes.
A different snapshot or a nonempty unrelated destination is refused.

The object importer preserves source keys and refuses different existing bytes.
Every imported object is downloaded and checked against its source length and SHA-256.
Destination writes, report processing, and scheduling remain paused after import.

## Run the portal and reset delivery

Run the web process and jobs process separately:

```sh
npm run web
npm run jobs
```

Open `/reset-password` and request a link using the existing account email.
The response is the same for known and unknown accounts. No reset token is returned by the API.
The jobs process sends mail even while report processing is paused.
A per-address one-minute throttle limits inbox flooding across all web processes.
Add public-edge request limits for sign-in and reset routes before a real public cutover.

The link uses the configured `PUBLIC_APP_URL` and puts the token in the URL fragment.
The page clears the fragment and sends the token in a POST body, keeping the token out of normal request URLs.
Tokens contain 256 random bits, expire after thirty minutes, and are stored only as SHA-256 hashes.
A newer issued link invalidates earlier links for that account.
Password replacement, token consumption, other-token invalidation, and session revocation commit together.
Concurrent redemption has exactly one winner.

The new password must contain at least twelve characters and at most seventy-two UTF-8 bytes.
The byte limit prevents bcrypt from silently truncating a password.
The user confirms the password twice, then logs in normally. Reset does not automatically create a session.

After validation, the imported administrator can disable maintenance through the portal's controls.
Enable report processing and scheduling only after the source execution location is disabled.
`npm run seed-test-data` fills a developer's laptop database or staging with invented test data.
It accepts only `APP_ENV=development` or `APP_ENV=staging` and creates reset-required accounts.
Reruns preserve existing accounts and never assign a password to an account awaiting reset.
Generated accounts also use `password_hash=NULL` and the existing password-reset flow.
The shared-password-hash rule does not apply to this app: its fixture has no password,
and the seed does no generated password hashing.

## Rehearse without sending mail

Use a separate disposable database, bucket, and private mail directory.
Set `APP_ENV=staging`, `PASSWORD_RESET_EMAIL_DIR` to a mode-700 directory, and `PUBLIC_APP_URL=http://127.0.0.1:18001`.
Use S3rver credentials only for the isolated S3-compatible rehearsal. Real provider credentials must remain outside the repository.

After migration and import, run:

```sh
REHEARSAL_CONFIRM=disposable-destination npm run test-rehearsal
```

The test reads reset links from protected `.eml` files instead of contacting the invented users.
The test covers preserved account IDs, reset expiry and reuse, concurrent redemption, login, shared sessions, revocation, ownership, private bytes, CRUD, jobs, and scheduling.
The tests mutate the disposable destination. Never point the tests at a customer database.
See [testing.md](testing.md) for the exact measured proof and remaining live-deployment boundaries.

## Fill a laptop or staging with test data

After the guide's local database and bucket setup, run migrations and then:

```sh
APP_ENV=development npm run seed-test-data
```

Use `APP_ENV=staging` for staging. `npm run seed-test-data -- --accounts 200000`
makes enough rows to show slow queries. The count includes the two fixed accounts.
Generated accounts get one owned record each and no files or report jobs.
Reruns add only missing rows; a smaller count removes nothing.
