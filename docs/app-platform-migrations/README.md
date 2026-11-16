# App platform migrations

These guides explain moving app code, accounts, data, private files and background work to the Monkeymaxxing Stack.
Start with the guide for the services your app actually uses. A code download contains neither database rows nor private file bytes.
Each migration needs separate service exports, ownership checks and a rehearsal before production cutover.

- [Lovable](from-lovable.md): keep generated TanStack pages while replacing Lovable Cloud accounts, data, storage and scheduling.
- [Replit](from-replit.md): move a development portal's PostgreSQL data, custom accounts, App Storage files, jobs and schedules.
- [v0/Vercel](from-vercel.md): rehearse replacing Vercel hosting, Neon Auth, private Blob, Functions and Cron from a hand-written source.
- [Railway](from-railway.md): export PostgreSQL and bucket objects, then move web, worker and cron execution through verified cutover steps.
- [Fly.io](from-fly.md): move application-owned accounts, unmanaged PostgreSQL, Tigris files, process groups and scheduled Machines.
- [Render](from-render.md): replace web, worker and cron services, PostgreSQL and private files stored on a persistent disk.
- [Supabase](from-supabase.md): replace Auth, database APIs and permissions, private Storage, an Edge Function and a mapped cron task.
- [Firebase](from-firebase.md): replace Auth, Firestore, Storage rules, callable reports and scheduled functions with PostgreSQL and private S3 storage.
- [Heroku](from-heroku.md): preserve the application schema and accounts while moving web, worker, clock and separate object storage.
- [Netlify](from-netlify.md): retain React pages and account IDs while replacing Identity, Database, Blobs, Functions, schedules and reset mail.
- [Bolt](from-bolt.md): identify the actual backend and hosting, then follow the Supabase and Netlify routes where applicable.
- [Base44 feasibility](base44-feasibility.md): assess exports and the backend replacement required for an independent app; no migration is proved.

### Leaving a platform you run yourself

These guides move the app first, while it still uses the old database over WireGuard, then move PostgreSQL last by logical replication through the Stack's [Move a database into the Stack](../../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/move_a_database_into_the_stack.md) procedure. The final write pause is a few seconds. Start with the [shared container guide](from-any-container-platform.md).

- [Docker Compose](from-docker-compose.md): resolve production overrides and secret files, convert local uploads, and move a PostgreSQL 15 volume onto the Stack's PostgreSQL 17.
- [Coolify](from-coolify.md): recover settings Coolify holds outside Git through its API, stop its scheduler and webhooks, and publish the database on WireGuard only.
- [Kubernetes](from-kubernetes.md): stop controllers so nothing restarts the old app, reach the in-cluster database over WireGuard, and leave the cluster; EKS, GKE and DigitalOcean variations are documented, not live-tested.
- [Kamal](from-kamal.md): move a Rails app on PostgreSQL with its accessories, destination secrets, worker and schedule; SQLite apps are not covered.
- [Dokku](from-dokku.md): export host-held config, the PostgreSQL plugin's database, cron and a private upload mount; one external schedule becomes an MMX timer.
- [Amazon ECS](from-ecs.md): move a Fargate app off ECS with RDS, S3, Secrets Manager, EventBridge and SQS; RDS reaches the Stack through a temporary relay, and SQS becomes a PostgreSQL queue.

## What moves and what stays

Each row describes the source configuration in the linked guide. Another app can use different services or authentication.
Keeping passwords means returning users can authenticate with the existing password. Existing browser sessions are a separate migration question.
The last column distinguishes destination dependencies from source services retained for rehearsal or rollback.

| Guide | What moves or is replaced | Do users keep passwords? | What remains on the platform? |
| --- | --- | --- | --- |
| [Lovable](from-lovable.md) | Pages, accounts, records, private bytes, reports, schedule metadata and source migration history | Yes for the tested bcrypt accounts; unsupported account states stop conversion | No Lovable backend URL in the converted server; source stays through the rollback window |
| [Replit](from-replit.md) | Code, PostgreSQL schema and rows, custom identities, App Storage bytes, queue and schedule state | Yes for tested custom bcrypt accounts; managed Replit Auth exit is untested | Phase 1 leaves the source running; destination replaces Replit database and storage calls |
| [v0/Vercel](from-vercel.md) | App, Neon database and Auth credentials, Blob bytes, reports, Cron and runtime settings | Yes for the tested Neon Auth credentials; users log in again | Rehearsal leaves source services unchanged; later cutover must prove operation with source services inaccessible |
| [Railway](from-railway.md) | Code, database, bucket bytes, accounts, reports, cron schedule and receipts | Yes, unchanged application bcrypt hashes | Complete exit requires independent runtime addresses; source project deletion has a grace period |
| [Fly.io](from-fly.md) | Code, schema, accounts, Tigris bytes, worker state and hourly schedule | Yes for application-owned bcrypt accounts; external identity providers need separate assessment | No Fly runtime dependency is required; source Machines, Volumes and Tigris need separate cleanup after acceptance |
| [Render](from-render.md) | Code, PostgreSQL accounts and rows, disk bytes, queue and daily cron work | Yes for tested application bcrypt accounts; external identity providers need separate assessment | Destination uses independent PostgreSQL and S3; a real source stays for the agreed recovery window |
| [Supabase](from-supabase.md) | Frontend service calls, Auth accounts, tables, permissions, private bytes, reports and mapped schedule | Yes for tested confirmed email/bcrypt accounts; other auth features need design | Destination replaces Supabase services; source project and separately hosted frontend await completion and retention decisions |
| [Firebase](from-firebase.md) | Accounts, Firestore documents, ownership rules, private bytes, reports and daily scheduled work | Yes with modified-scrypt verifiers, salts and private project hash settings; browser sessions end | Destination calls no Firebase service; source retirement follows production checks and retention approval |
| [Heroku](from-heroku.md) | Code, application schema, accounts, separate S3 bytes, report queue and code-defined clock | Yes, unchanged application bcrypt hashes | Provider diagnostics stay outside the portable schema; app, add-ons and source storage need cleanup after acceptance |
| [Netlify](from-netlify.md) | React UI, account IDs and metadata, rows, Blobs bytes, jobs, schedule history and mail delivery | No through the normal customer route; returning users set a new password by one-time email link | Tested source was deleted after rehearsal and replay; destination uses app-owned accounts, PostgreSQL, S3 and SMTP |
| [Bolt](from-bolt.md) | Code download plus separate backend exports through the applicable Supabase or Netlify guide | Not established by code export or backend claim; follow the actual auth service's guide | Source stays until data and rollback checks pass; no hosted Bolt migration was proved |
| [Base44 feasibility](base44-feasibility.md) | Documented code export, record CSVs and user profiles; private bytes need live verification and backend services need replacement | No portable credential export established; plan reset or identity-provider reconnection unless export is proved | Hosting exported code elsewhere still uses Base44 data, login, functions and integrations until the backend is replaced |
| [Docker Compose](from-docker-compose.md) | Code, PostgreSQL by logical replication, accounts, private uploads, worker queue and host timer | Yes, unchanged application bcrypt hashes | Nothing after the old server is powered off; the old database is kept for the agreed recovery period |
| [Coolify](from-coolify.md) | Code, Coolify-held settings, PostgreSQL by logical replication, mounted files and scheduled task | Yes, unchanged application bcrypt hashes | Nothing after Coolify and its server are stopped |
| [Kubernetes](from-kubernetes.md) | Deployments, CronJob, Secrets, ConfigMaps, persistent uploads and the in-cluster PostgreSQL | Yes, unchanged application bcrypt hashes | Nothing on k3s; managed clusters keep their own storage and identity services until removed |
| [Kamal](from-kamal.md) | Rails app, accessories, destination secrets, worker, schedule and PostgreSQL | Yes, unchanged application bcrypt hashes | Nothing after the old hosts are stopped |
| [Dokku](from-dokku.md) | App, host-held config, PostgreSQL plugin database, cron and private upload mount | Yes, unchanged application bcrypt hashes | Nothing after the Dokku host is stopped |
| [Amazon ECS](from-ecs.md) | Fargate app, RDS PostgreSQL by logical replication through a relay, S3 bytes, secrets, schedule, and SQS replaced by a PostgreSQL queue | Yes, unchanged application bcrypt hashes | Nothing in AWS after the source stack is deleted |

The password results cover the tested account types. OAuth, MFA, account recovery and external identity providers can need additional work.
Preserve stable user IDs, ownership and identity issuer/subject mappings. Never join accounts by email alone.
Protect password verifiers, credentials, database archives and private files outside Git.
Before final cutover, freeze source writes and choose exactly one location for job and schedule execution.
After destination writes begin, returning traffic to the source requires reconciling the new data.

Rehearsal proves the exported copy works within the checks recorded in each guide.
Live Stack deployment, real storage permissions, database switching and backup recovery need separate evidence.
Bolt is a routing guide. Base44 is a documentation assessment. Neither establishes a completed platform exit.
