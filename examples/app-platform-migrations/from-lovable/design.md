# How the Lovable portal works

The exported portal uses TanStack Start and Lovable Cloud. The converted portal keeps the generated React pages and runs on Node, Postgres and S3 storage.

A code export does not include the running backend. Auth accounts, table rows, object bytes, schedules and secrets need separate exports or replacements.

## Chosen boundary

Two designs can preserve the pages. Self-hosted Supabase preserves the generated auth, REST and storage interfaces, but requires operating several additional services.

The example instead replaces the managed interfaces with a small server API. Postgres stores accounts, sessions, records and jobs. An S3 bucket stores private document bytes.

The server API owns authentication and ownership checks. Browser code never receives a database password or an S3 secret. The converted server has no Lovable backend URL.

This example covers email/password accounts and the portal's actual service calls. External identity providers, MFA, passkeys, unconfirmed accounts, realtime subscriptions and third-party connectors need separate designs when used.

The export helper refuses stronger account requirements that the replacement cannot preserve. The import mapping refuses changed application columns instead of silently losing new fields.

## One request through the original app

A customer opens `/login`. `login.tsx` submits the email and password through `supabase.auth.signInWithPassword`.

Lovable Cloud checks the stored bcrypt hash and returns an access token and a refresh token. A hash verifies a password without storing the password itself.

A JWT is a signed access token carrying identity and expiry. The refresh token obtains a replacement access token when the access token expires. The generated browser client persists the session and refreshes tokens.

Source logout revokes refresh tokens and clears browser state. The source worker observed that an already-issued access JWT remains accepted until expiry.

`_authenticated/route.tsx` checks `supabase.auth.getUser()` before showing protected pages. This browser check controls navigation. Database policies provide the security boundary.

`records.tsx` asks the backend REST API for records. PostgreSQL's row-level security, or RLS, only returns rows whose `user_id` equals `auth.uid()`.

`auth.uid()` reads the verified identity from the backend request. For example, Barbara cannot select Michael's record even when Barbara knows Michael's record ID.

The Account page follows another path. `useServerFn(getAccountSummary)` calls a TanStack server function. `src/start.ts` registers `attachSupabaseAuth` globally.

`auth-attacher.ts` adds the browser's bearer token. `auth-middleware.ts` checks the token's claims and creates a backend client carrying that user's identity.

`getAccountSummary` counts the caller's rows. The server uses the user's backend token, so the database policies still restrict the count.

## Original framework and files

TanStack Start provides server rendering and server functions. TanStack Router maps filenames to URLs. React renders the pages. React Query caches browser requests.

Vite builds the app. Nitro produces the deployment output. The generated build wrapper defaults to Cloudflare, so a Node deployment must select `NITRO_PRESET=node-server`.

The original lockfile pins TanStack Start 1.168.60, Router 1.170.41, React 19.2.8 and Vite 8.1.5. Keep the original lockfile with the export.

The file map below names the original exported files. Converted files with different responsibilities are described later.

| Original path | Job |
| --- | --- |
| `.lovable/project.json` | Identifies the generator template and revision. No application behavior. |
| `README.md` | Generated overview, original platform runtime, service behavior and builder instructions. Check claims against running services. |
| `package.json` | Build, development, lint and test commands, plus dependency ranges. |
| `bun.lock` | Exact original dependency resolution. A source snapshot identifier when Git sync is unavailable. |
| `bunfig.toml` | Bun installation settings, including the generated package-age rule. |
| `.env` | Generated environment values. Keep private. Inventory names without publishing values. |
| `.gitignore` | Files Git omits, including local build output and dependencies. |
| `.prettierignore`, `.prettierrc` | Formatting exclusions and formatting settings. |
| `AGENTS.md` | Generated editing guidance. Read with the source. The migration guide owns destination instructions. |
| `components.json` | UI component generator settings and aliases. |
| `drizzle.config.ts` | Points Drizzle tools at the schema and migration URL. Not the app's runtime database connection. |
| `drizzle/schema.ts` | Placeholder schema module. The exported SQL migrations contain the actual portal tables and policies. |
| `drizzle/migrations/0000_initial_portal_schema.sql` | Tables, constraints, ownership policies, report function, maintenance function and storage policies. |
| `drizzle/migrations/0001_daily_maintenance_schedule.sql` | Registers the daily job and disables the schedule. |
| `drizzle/migrations/meta/0000_snapshot.json`, `0001_snapshot.json`, `_journal.json` | Drizzle's generated schema snapshots and migration order. Inspect the actual database too. |
| `eslint.config.js` | JavaScript/TypeScript lint rules, including server-only module boundaries. |
| `tsconfig.json` | TypeScript settings and `@/` source alias. |
| `vite.config.ts` | Lovable's Vite wrapper and custom `src/server.ts` entry. |
| `vitest.config.ts` | Test runner settings and browser simulation. |
| `public/favicon.ico`, `public/robots.txt` | Browser icon and crawler instructions. Public assets, not private document storage. |
| `src/router.tsx` | Creates a router and a request-specific React Query client. |
| `src/routeTree.gen.ts` | Generated route registration. Regenerated by the build. |
| `src/server.ts` | Loads the TanStack server handler and renders a readable page for catastrophic server errors. |
| `src/start.ts` | Installs bearer attachment, error handling and cross-site request protection for server functions. |
| `src/styles.css` | Tailwind setup, colors, typography and utility classes. |
| `src/routes/__root.tsx` | HTML shell, metadata, styles, fonts, query provider, notifications and error page. Refreshes caches after auth events. |
| `src/routes/index.tsx` | Public landing page and links to sign-in and registration. |
| `src/routes/login.tsx` | Email/password sign-in form. |
| `src/routes/register.tsx` | Registration form, validation and sign-in result. |
| `src/routes/healthz.ts` | HTTP health route. The original route does not prove database or storage health. |
| `src/routes/README.md` | Explains TanStack filename routing. |
| `src/routes/_authenticated/route.tsx` | Browser authentication gate, navigation and global logout. Clears React Query caches on logout. |
| `src/routes/_authenticated/records.tsx` | Owned record listing, creation, title editing and deletion. |
| `src/routes/_authenticated/documents.tsx` | Hashes and uploads file bytes, saves metadata, requests signed download URLs and deletes documents. |
| `src/routes/_authenticated/reports.tsx` | Lists and queues jobs. Calls the server function when the customer clicks Run pending report. |
| `src/routes/_authenticated/account.tsx` | Shows identity and counts returned by the authenticated server function. |
| `src/components/AuthCard.tsx` | Shared sign-in and registration layout. |
| `src/components/DetailsPanel.tsx` | Page headings and expandable record/file details. |
| `src/hooks/use-mobile.tsx` | Tracks the narrow-screen breakpoint for UI components. |
| `src/integrations/supabase/client.ts` | Lazy browser backend client. Handles public keys, refreshes sessions and rewrites server requests to an internal backend URL when configured. |
| `src/integrations/supabase/client.server.ts` | Lazy administrator client with a service-role key. Bypasses RLS. Not used in the portal's ordinary user path. |
| `src/integrations/supabase/auth-attacher.ts` | Adds the current access token to TanStack server-function calls. |
| `src/integrations/supabase/auth-middleware.ts` | Validates bearer claims and passes the user ID and user-scoped backend client to server functions. |
| `src/integrations/supabase/cron-auth.ts` | Constant-time comparison for current/previous cron bearer secrets. The SQL maintenance schedule does not call this helper. |
| `src/integrations/supabase/previewAuthStorage.ts` | Session persistence for editor previews, including brokered iframe storage. Separate from database storage. |
| `src/integrations/supabase/types.ts` | Generated TypeScript description of the backend API. Types do not create tables or enforce permissions. |
| `src/lib/portal.functions.ts` | Account counts and customer-triggered report execution. |
| `src/lib/hash.ts` | Exact-byte SHA-256 and owner-prefixed object-key construction. |
| `src/lib/utils.ts` | Merges CSS class names. |
| `src/lib/error-capture.ts` | Retains an error for the server's error wrapper to report. |
| `src/lib/error-page.ts` | Generates the fallback HTML error page. |
| `src/lib/lovable-error-reporting.ts` | Forwards browser errors to optional editor telemetry hooks. Not a database or authentication dependency. |
| `src/test/setup.ts` | Browser-test setup. |
| `src/test/app-routing.test.tsx` | Checks that `/` matches a real route. Does not prove authentication or backend behavior. |
| `supabase/config.toml` | Generated backend project binding. Not a database export or a portable account configuration. |

### Generated UI library

`src/components/ui/` contains reusable widgets, mostly wrapping Radix UI. A widget file does not imply the portal uses the widget.

The portal directly uses `badge.tsx`, `button.tsx`, `input.tsx`, `label.tsx` and `sonner.tsx`. Preserve widget dependencies when retaining the generated library.

| File in `src/components/ui/` | Purpose |
| --- | --- |
| `accordion.tsx` | Expandable sections. |
| `alert-dialog.tsx` | Confirmation dialogs. |
| `alert.tsx` | Inline status messages. |
| `aspect-ratio.tsx` | Fixed image/media proportions. |
| `avatar.tsx` | Profile images and fallbacks. |
| `badge.tsx` | Compact labels, including report status. |
| `breadcrumb.tsx` | Location navigation. |
| `button.tsx` | Buttons and their visual variants. |
| `calendar.tsx` | Date picker calendar. |
| `card.tsx` | Content panels. |
| `carousel.tsx` | Sliding item lists. |
| `chart.tsx` | Chart styling and tooltips. |
| `checkbox.tsx` | Checkboxes. |
| `collapsible.tsx` | Expand/collapse control. |
| `command.tsx` | Searchable command lists. |
| `context-menu.tsx` | Context menus. |
| `dialog.tsx` | Modal dialogs. |
| `drawer.tsx` | Sliding panels. |
| `dropdown-menu.tsx` | Button menus. |
| `form.tsx` | Form labels, messages and field context. |
| `hover-card.tsx` | Hover information panels. |
| `input-otp.tsx` | Segmented code inputs. Does not implement MFA. |
| `input.tsx` | Text inputs. |
| `label.tsx` | Accessible field labels. |
| `menubar.tsx` | Menu bars. |
| `navigation-menu.tsx` | Navigation menus. |
| `pagination.tsx` | Page navigation. |
| `popover.tsx` | Anchored floating panels. |
| `progress.tsx` | Progress bars. |
| `radio-group.tsx` | Radio choices. |
| `resizable.tsx` | Resizable panels. |
| `scroll-area.tsx` | Scroll containers. |
| `select.tsx` | Dropdown choices. |
| `separator.tsx` | Visual separators. |
| `sheet.tsx` | Side panels. |
| `sidebar.tsx` | Responsive sidebar framework. |
| `skeleton.tsx` | Loading placeholders. |
| `slider.tsx` | Numeric range sliders. |
| `sonner.tsx` | Toast notification host. |
| `switch.tsx` | Toggle switches. |
| `table.tsx` | Table elements. |
| `tabs.tsx` | Tab controls. |
| `textarea.tsx` | Multiline inputs. |
| `toggle-group.tsx` | Grouped toggle buttons. |
| `toggle.tsx` | Pressed-state buttons. |
| `tooltip.tsx` | Hover/focus hints. |

## Original database and policies

User IDs are UUIDs, long random identifiers. Keeping IDs stable preserves record and document ownership across the move.

`auth.users` owns identities and password hashes. `auth.identities` links sign-in providers to user UUIDs. Portal tables reference user UUIDs without foreign keys to managed auth.

`records` stores `id`, `user_id`, `title`, `created_at` and `updated_at`. The title constraint requires 1–200 trimmed characters. A trigger updates `updated_at`.

`records_select_own`, `records_insert_own`, `records_update_own` and `records_delete_own` compare `auth.uid()` with `user_id`. The update policy checks existing and replacement ownership.

`documents` stores its UUID, owner UUID, optional record UUID, original filename, object key, SHA-256, byte count and creation time.

A unique constraint prevents duplicate object keys. A key-prefix constraint requires the first path segment to equal the owner UUID. Deleting a record clears document attachment.

`documents_select_own` and `documents_delete_own` restrict rows to the caller. `documents_insert_own` also checks the key prefix and any attached record's owner.

The original user role has no document-update grant. A file is uploaded and then receives a metadata row. A failed insert attempts to remove the uploaded object.

`report_jobs` stores owner, state, requested/start/completion times, output, attempt count and archive time. States are PENDING, RUNNING, COMPLETED and FAILED.

`report_jobs_select_own` restricts reads. `report_jobs_insert_own_pending` only allows fresh PENDING jobs with zero attempts and no timestamps, archive time or output.

The user role cannot directly change job state. The report function performs state changes with elevated privileges and an explicit owner check.

RLS supplements SQL grants. `authenticated` receives limited table operations. `service_role` receives broad access. A service-role request cannot prove customer privacy.

## Original private files

S3-style storage saves file bytes under object keys inside buckets. PostgreSQL keeps the document metadata and references to those keys.

The `documents` bucket is private. `documents_objects_select_own`, `documents_objects_insert_own` and `documents_objects_delete_own` check the bucket and first object-key segment.

`documents.tsx` computes SHA-256 over the exact bytes. Keys use `<user UUID>/<random UUID>/<safe filename>`. Metadata includes the original filename and byte length.

The source UI limits uploads to 20 MiB. A signed URL grants temporary download access for 60 seconds. Anyone holding that URL can download during the validity period.

Deleting a document removes object bytes and then the metadata row. Object storage and PostgreSQL do not share a transaction. Check orphaned objects and broken references during migration.

## Original functions, queue and schedule

`run_pending_report()` selects the caller's oldest pending job with `FOR UPDATE SKIP LOCKED`. A locked job is skipped so another worker can claim different work.

The function also accepts RUNNING jobs older than ten minutes. The source function marks RUNNING, counts owned records and saves completion within one database transaction.

An interrupted transaction rolls back. The completed report contains `record_count=<count>` plus LF. The report performs no external side effect.

The source does not run queued reports automatically. A customer must click Run pending report. The source fixture deliberately leaves two pending reports untouched.

`daily_maintenance()` archives COMPLETED reports older than 30 days. The function never consumes pending jobs. Only the service role can call maintenance.

The exported cron row records `0 3 * * *`, UTC, `SELECT public.daily_maintenance();`, and `active=false`. A SQL migration alone does not prove dashboard state.

The real archive includes the paused cron row and empty run history. Preserve the paused state during rehearsal. Do not enable destination schedules while source schedules can execute.

## Secrets and configuration

Public backend values identify the API and public client key. RLS and verified identity provide protection. A public key is not an administrator key.

| Original name | Role and treatment |
| --- | --- |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` | Browser build settings. Rebuild after changing browser settings. |
| `SUPABASE_PROJECT_ID`, `VITE_SUPABASE_PROJECT_ID` | Generated project identifiers. Record bindings separately from credentials. |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | Server access to the user-scoped managed backend. |
| `SUPABASE_SERVICE_ROLE_KEY` | Privileged server-only backend key. Never expose in browser code. |
| `LOVABLE_DB_MIGRATION_URL` | Database access for generated migration tooling. |
| `LOVABLE_CRON_SECRET`, `LOVABLE_CRON_SECRET_PREVIOUS` | Current/previous cron authentication helper inputs. Only the current name appeared in the live secrets list. |
| `LOVABLE_API_KEY` | Platform-injected API secret shown in the live list. The portal's reviewed code has no required AI-gateway call. |

The native secrets inventory is separate from environment names found in code. An unused helper can reference a name absent from the dashboard.

The generated template includes optional auth, cron and administrator helpers. Keep the actual import graph separate from available boilerplate.

## Converted files and behavior

`app/backend.mjs` owns server authentication, ownership checks, parameterized queries, S3 operations and transactional report completion. Every customer query includes the authenticated owner.

`app/src/lib/portal-client.ts` sends same-origin requests. The browser receives an HttpOnly session cookie. JavaScript cannot read the session token.

Postgres stores a SHA-256 digest of each random session token. Requests to any app process use the shared session table. Logout deletes all sessions for the account. Sessions expire after seven days; a new login creates a fresh session.

The destination matches the fixture's disabled email-confirmation behavior. Email verification, password-recovery delivery and MFA are not implemented by this example.

Source refresh tokens, access JWTs and signing secrets are not imported. Returning customers sign in again with the preserved bcrypt hashes.

`app/src/lib/portal.functions.ts` retains real TanStack Account and report server functions. The functions read the shared cookie instead of forwarding a Supabase bearer token.

`app/src/start.ts` retains error handling and TanStack cross-site protection. `backend.mjs` also requires the configured Origin on API writes.

`app/src/server.ts` dispatches `/api/` requests before the TanStack page handler. `start.mjs` forks `WEB_CONCURRENCY` workers. Nitro listens on `HOST` and `PORT`.

`pg_with_multiple_database_servers.mjs` is copied unchanged from the Stack. New connections discover the current primary. Requests are not automatically retried after an uncertain commit.

`operations.mjs migrate` applies ordered transactional SQL once and checks saved migration hashes. `001_portal.sql` creates the independent schema. `002_record_description.sql` adds an empty description.

`operations.mjs import` requires an empty destination. The importer preserves account, record, document and job IDs. The importer checks every object hash before and after copying.

`imported_schedules` records the original schedule definition without executing schedules. `source_migrations` records source migration rows separately from destination migrations.

`operations.mjs jobs` runs background reports. Keep destination workers stopped until a real cutover. `maintenance` runs the archive operation when explicitly scheduled later.

`seed-test-data` fills a developer's laptop database or staging with invented accounts and data. `APP_ENV` must be `development` or `staging`. `--accounts` includes the two fixed accounts and adds generated accounts and owned records with bulk SQL and one password hash. Repeated seeds preserve existing rows; a smaller count removes nothing. The seed does not load source exports.

The converted API replaces source RLS with server ownership checks. Restrict database and bucket credentials to the app. Do not expose PostgreSQL as a customer API.

Source document uploads perform two browser calls. Destination uploads use one server request, so the server computes the hash and chooses the owner prefix.

An S3 success followed by a database failure can leave an unreferenced object. Retain object inventories for cleanup. Database backup alone never protects object bytes.

The original Supabase integration, Drizzle source definitions and Bun lockfile stay with the source export. The destination uses npm's lockfile and its own migrations.
