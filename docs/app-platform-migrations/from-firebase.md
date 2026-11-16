# Move a Firebase app to your own system

## Variances and guidance needs

Firebase runs more than the front end. A complete move must replace Firebase
Auth, Firestore, Storage rules, report functions and scheduled functions.
Copying a Hosting build leaves accounts, private files and server work behind.
This guide moves a small customer portal to PostgreSQL 17 and S3-compatible
storage. The [working destination](../../examples/app-platform-migrations/from-firebase/README.md)
contains the app, export/import tools and checks.

The important differences are:

- Firestore documents have no SQL schema or column defaults. Map each document
  and its owner to a table. Preserve original IDs and unmapped fields.
- Firebase's modified scrypt is different from standard scrypt. Password hashes
  alone are insufficient: retain each user's salt and the project's private
  hash settings. Browser sessions do not move; users sign in again.
- Browser calls were protected by Firestore and Storage rules. The destination
  server must enforce the same ownership rules on every read and write.
- Database exports do not contain Storage bytes, Auth users, deployed source,
  Scheduler settings or completed function outputs. Export each separately.
- A paused UI does not stop direct SDK calls, cached writes, account creation
  or scheduled work. Freeze the native services before the final export.

## What this example covers

The source is a hand-written React app using Firebase's Web SDK, email/password
Auth with Identity Platform enabled, Firestore Native, a private Cloud Storage
for Firebase bucket, Firebase
Hosting, an authenticated callable report function and a scheduled function.
The report counts only the caller's records. The scheduled function archives
completed reports older than 30 days, once each day at midnight UTC.

The destination expresses the same small portal with a Node.js server and HTML
client. It replaces Firebase SDK operations and rules with server routes, SQL
ownership checks and S3 access. For a larger React app, keep the existing UI and
replace its service calls using the same explicit data and authorization mapping.

The synthetic fixture has two users, one invoice and one private 27-byte
UTF-8 document each. It retains two pending reports, one completed proof report,
one recorded scheduled occurrence, and two source schema-migration documents.
The second release backfilled `records.description` with an empty value before
saving the fixture descriptions through the hosted app. An older client can
still omit the field. PostgreSQL provides the actual empty column default.

The source uses root-level collections. The exporter refuses nested
subcollections because silently omitting them would lose data. A different
app needs an explicit collection/table mapping, including document references,
arrays, Timestamp values, GeoPoints and any provider-specific types.

## Inventory the source

Record the project ID, Auth providers, custom claims, collection names and
rules, bucket names and rules, functions and regions, trigger configuration,
schedules and time zones, Hosting sites, code revision and dependency lockfiles.
Record environment variable names separately from their values. Check for
extensions, webhooks, mail delivery and third-party connectors; this fixture has
none. Preserve the original Auth issuer and UID rather than linking by email.

The destination maps:

| Source | PostgreSQL or S3 |
| --- | --- |
| Auth `localId` | Text `users.id`; same owner IDs everywhere |
| Auth email/password verifier and custom claims | Protected user/config rows; disabled accounts remain disabled |
| `records` | Owned records, with an empty `description` default |
| `documents` | Owned file metadata; original keys and SHA-256 |
| Private Storage objects | Private S3 objects with the same keys and exact bytes |
| `jobs` | Pending/completed reports and completed output |
| `controls`, `schedules`, `scheduled_runs` | Pauses, persisted daily schedule and occurrence ledger |
| Every Firestore document | `source_documents` retains original collection, ID and fields |
| Portable Auth fields and source schema ledger | Protected audit rows; native CLI archive retained separately |

Source `ARCHIVED` reports map to completed jobs with `archived=true`; the raw
source state remains in the audit table. Firebase security rules and callable
functions become server authorization and transactional PostgreSQL operations.
Keeping the original data in an audit table does not make an unmapped feature
work. Check every feature before cutover.

## Export accounts and password settings

Use a trusted operator machine and credentials for the selected project.
Firebase terms acceptance is an account-owner console step; an API cannot
accept the terms. Use the project's existing authorized account and billing
settings. The example does not require a new trial or an export subscription.

Firebase provides a [native Auth export](https://firebase.google.com/docs/cli/auth):

```sh
umask 077
export FIREBASE_PROJECT_ID=customer-portal-example
mkdir -p /secure/firebase-export
firebase auth:export /secure/firebase-export/native-users.json \
  --format=json --project "$FIREBASE_PROJECT_ID"
```

Export the private project hash configuration through the Identity Toolkit
[`projects.getConfig` API](https://docs.cloud.google.com/identity-platform/docs/reference/rest/v2/projects/getConfig),
or the Auth console's **Password hash parameters** dialog. Required fields are
`signIn.hashConfig.algorithm`, `signerKey`, `saltSeparator`, `rounds` and
`memoryCost`. Reading the hash configuration needs permission to read that
configuration, including the hash parameters. Never print the signer key.
The supplied exporter saves the native configuration directly into a private file.

Native CLI export and Admin SDK user export can use different base64 alphabets
for the same hash bytes. The exporter normalizes SDK values to the CLI's standard
base64 and the importer validates that representation. Compare decoded bytes,
UIDs and owner mappings, rather than accepting a textual mismatch silently.

The example verifies Firebase modified-scrypt passwords locally using Node's
standard crypto library and the [official Firebase algorithm](https://github.com/firebase/scrypt).
Its known-answer test is separate from the real imported-user login checks.
A user with an empty password hash cannot use that path. Plan a verified password
reset or provider reauthentication for such users. Social sign-in, anonymous
accounts, MFA and tenant migrations require separate mappings and are outside
this fixture. Firebase ID/refresh tokens are not PostgreSQL sessions. In
Firebase, local browser sign-out also does not revoke an ID token already issued
to another caller. The destination issues new database-backed sessions and
revokes those sessions across app processes on logout.

## Freeze and export the final source

Set `controls/runtime.maintenance`, `worker_paused` and `scheduler_paused` to
true. Let any in-flight report transaction settle. Pause the native Scheduler
job as well. In Storage rules, deny create/delete writes while retaining private
owner reads. Disable client account creation/deletion in Auth configuration;
stop account/profile/password changes and any other writer for the export window.
The fixture's controlled users are signed out before export.

```sh
gcloud scheduler jobs pause firebase-schedule-archiveReports-europe-west1 \
  --location=europe-west1 --project "$FIREBASE_PROJECT_ID"
```

Check the real job name and region against your inventory. Cloud Functions can
also be invoked directly: the report function must honor its processing pause.
Firestore security rules must block writes during maintenance, including writes
from clients that reconnect after going offline. Keep only one execution location
active throughout the move.

Retain the original source and lockfiles from your repository. Hosting normally
serves compiled browser assets; those assets are not the original React source.
Function build source and configuration also need their own export. Make a source
archive without dependency directories, credentials, provider debug logs or data.
On macOS, set `COPYFILE_DISABLE=1` and exclude `._*` metadata files from archives.
Set `SOURCE_CODE_ARCHIVE` to that archive's absolute path.

From the destination example directory, install the pinned export dependencies
and run the exporter with Application Default Credentials for the source project:

```sh
npm ci --no-audit --no-fund
export FIREBASE_STORAGE_BUCKET=customer-portal-example.firebasestorage.app
export SOURCE_CODE_ARCHIVE=/secure/customer-portal-source.tar.gz
export EXPORT_DIR=/secure/firebase-export
npm run export-firebase
npm run verify-export
```

The exporter requires frozen processing controls and saves Auth users and hash
settings, all supported root collections, native function/Scheduler/database/bucket/Hosting
configuration, observed environment variable names, private
object bytes, the source archive and a SHA-256 manifest. It checks every object's
bytes against the Firestore metadata. All files are private, mode 600, under a
mode-700 export directory. Keep the operator OAuth credentials on the operator
machine; only the export moves to the destination.

Also retain a [managed Firestore export](https://firebase.google.com/docs/firestore/manage-data/export-import):

```sh
gcloud firestore export \
  "gs://$FIREBASE_STORAGE_BUCKET/native-firestore-export" \
  --database='(default)' --project "$FIREBASE_PROJECT_ID"
gcloud storage cp --recursive \
  "gs://$FIREBASE_STORAGE_BUCKET/native-firestore-export" \
  /secure/firebase-export/
```

The managed export requires billing and incurs reads plus object-storage usage.
Its native format restores to Firestore; it is not a SQL dump or a PostgreSQL
import. The portable JSON export supplies the explicit table conversion.
Exports taken at different times are not a transaction across Auth, Firestore
and Storage. Keep source writers stopped, compare the complete inventory and
repeat the final source comparison before releasing the source.

## Restore and prove the destination

Create an empty PostgreSQL 17 database and a separate private S3 bucket. Copy
`environment.example` to a protected env file outside the source tree and supply
all settings. Read the example's README for the writer-discovery database URL,
object endpoint and required runtime commands.

```sh
set -a
. /secure/portal-destination.env
set +a
export EXPORT_DIR=/secure/firebase-export
npm run verify-export
npm run migrate
npm run import-firebase
npm run import-objects
npm run web
```

The database import is one transaction and refuses existing app data. It retains
stable IDs, verifiers, owner relationships, full source documents, completed
output, pending work and the schedule. Object import is a separate step; it
refuses to overwrite different bytes and downloads each result to verify its hash.
Both processing pauses and maintenance remain enabled after import. If a metadata
write fails after uploading a new file, the server keeps the private bytes: the
database commit may have succeeded even when its reply was lost. Reconcile
unreferenced objects later; deleting immediately could destroy a committed file.

Before cutover, compare each imported user and verifier, every source document,
owned record, file key/hash, job/output, schedule/occurrence and schema version.
Log in with both original passwords. Check record CRUD, cross-owner refusals,
private file bytes, cross-process sessions and logout. Test concurrent and
interrupted report work and the scheduled task on disposable destination data.
Run a fresh replay from the saved export into another empty database and bucket.
The example's tests change data; never run them on the production destination.

## Later production cutover and rollback

Phase 1 is an independent migration rehearsal. It does not switch customer
traffic or prove deployment on a full Stack fleet, real R2 authorization,
primary/replica failover or backup recovery.

For a production move, deploy the verified app through the Stack's normal image
and migration procedure. Retain the final source export, then change routing.
Enable destination writes and processing only when the source remains frozen.
Verify public behavior and both ownership boundaries before retiring the source.

Before any destination writes, routing can return to the unchanged source.
After destination writes begin, a route-only rollback would lose those writes.
Freeze the destination and reconcile its new accounts, records, files and jobs
before reversing the move. Do not run source and destination workers together.
Delete source services only after the agreed checks and retention decision.
Project deletion affects every Google Cloud and Firebase service in that project.

## Cost and service boundaries

This fixture needs Blaze billing: newly created default Storage buckets and
Cloud Functions cannot run solely on Spark. A managed Firestore export also
requires billing. No frontend-only download proves a free complete exit.
Firestore free usage includes one eligible database, 1 GiB stored, 50,000 reads,
20,000 writes and 20,000 deletes per day, plus 10 GiB monthly outbound transfer;
see the current [Firestore quota table](https://firebase.google.com/docs/firestore/quotas).
Native exports charge document reads even when free usage exists.

Hosting's free storage and transfer allowances, Auth limits, function compute,
build artifacts and Storage region allowances are separate. A Europe Storage
bucket does not receive the US-region-only Cloud Storage free allowance.
Cloud Scheduler provides three free jobs per billing account; additional jobs
are priced by the job, including paused jobs. Check the current
[Firebase pricing table](https://firebase.google.com/pricing),
[Auth limits](https://firebase.google.com/docs/auth/limits), and
[Scheduler pricing](https://cloud.google.com/scheduler/pricing)
before a customer's export. An estimated tiny fixture cost is not a measured bill.

## Fill a laptop or staging with test data

The command fills a developer's laptop database or staging with invented test data.
Use the local database and bucket from the rehearsal steps and run migrations first.
Supply `FIXTURE_PASSWORD` and run:

```sh
APP_ENV=development npm run seed-test-data
```

For staging, use `APP_ENV=staging` with its own database and bucket.
`npm run seed-test-data -- --accounts 200000` makes enough rows to show slow queries.
The count includes the two fixed accounts. Reruns preserve existing values and
add only missing accounts and records. Production data stays on production servers.
