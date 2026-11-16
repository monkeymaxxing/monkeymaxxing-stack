# Variances and guidance needs

The tested migration preserves native accounts, emails, IDs, ownership, files, jobs, and schedule history.
Returning users set a new password using an expiring one-time link, then log in normally.
Native Netlify Identity password hashes were not exported or fabricated.
A support-supplied verifier export remains an optional separate route.

## Source and export proof

The hand-written source used React 19.3.1, Vite 8.3.5, Netlify Functions on Node 24.x, native Identity, Database, and Blobs.
The source database was PostgreSQL 18.6.
Both invented users registered through the running source app and created their required owned records and exact private documents.
The second deployment retained the original data and added `records.description`.
Source ownership checks, exact downloads, CRUD, report completion, and logout-cookie replay refusal passed.

The source dump and complete row audit share one repeatable-read snapshot.
The manifest checksums the dump and audit separately.
The native Blobs listing matched exactly two document references and both required twenty-seven-byte contents, including LF.
The source archive matched all seventeen authored source files and the pinned revision.
Native identity metadata, function modes, cron settings, and environment-variable names were exported separately.

The original PostgreSQL 18.6 custom dump also restored into a separate PostgreSQL 17.11 database.
All eight source tables matched the original audit.
That offline source restore is distinct from the destination import's documented table mapping.

## Destination behavior

2026-11-05: Renamed the seed to `seed-test-data` for laptops and staging and added `--accounts`. JavaScript syntax and Containerfile source-path checks passed. On isolated Debian 13, Node 24.22.1, PostgreSQL 17.11 and pinned S3Mock, `node --test tests/seed-test-data.test.mjs` passed 1 test, `npm run build` passed, export verification and object/account imports passed, and `npm run test-rehearsal` passed all 9 tests against a fresh synthetic snapshot. Seed checks covered both allowed environments, production/unset refusals, exact fixture rows and bytes, 1,000 accounts/identity mappings/owned records twice, NULL generated verifiers, smaller-count preservation and preservation of a chosen password. No generated password hashing, source-platform access or new container image is claimed.

The destination keeps React 19.3.1 and Vite 8.3.5, uses Express and bcrypt, and discovers the database writer through the unchanged Stack driver.
The isolated Linux rehearsal uses PostgreSQL 17.11, Node 24.22.2, npm 11.19.1, and S3rver 3.7.1.
The source app and destination test accounts use invented addresses. No reset mail is sent outside the private staging sink.

The initial destination rehearsal passed import preservation, token expiry and reuse, concurrent token redemption, new-password login, and shared-session revocation.
Owned CRUD, exact source downloads, cross-owner refusals, report ownership, interrupted job recovery, concurrent workers, and daily archival also passed.
The final independent replay passed all nine test results. The final exact-artifact run also passed nine results with exit zero.

The reproducible suite checks:

- Native user IDs and emails, record/document/job IDs, owner mappings, file hashes, pending state, completed output, and migration history.
- NULL imported passwords and discarded source sessions.
- Generic reset responses for known and unknown accounts, shared per-address throttling, and cross-origin refusal.
- Private mail delivery from the jobs process while report processing is paused.
- Random token format, hashed storage, thirty-minute expiry, invalid/replaced/used token refusal, and exactly one concurrent redemption winner.
- Password confirmation, no automatic reset login, preserved account IDs, and new-password authentication.
- Sessions shared across web processes and revoked across those processes after a later reset or logout.
- A deterministic old-password login racing password replacement is refused after the replacement commits.
- Safe repeated import and laptop or staging test-data seeds that preserve newly chosen passwords.
- Owned CRUD, title-only description defaults, private upload/download byte equality, and both-direction owner refusals.
- Concurrent report workers, a killed worker's open transaction, preserved output, and deduplicated UTC archival.

## Scope of the proof

The staging mail sink exercises message construction and the real token flow. Production SMTP receipt and DNS sender records require live deployment checks.
The S3-compatible rehearsal proves object API behavior and byte integrity. Real R2 bucket permissions require their own check.
The shared Stack driver is copied unchanged. A full Stack deployment, live primary promotion, production traffic cutover, and customer-facing mail delivery are outside this rehearsal.
The owned source Blobs, Database, Identity instance, and site were deleted after the successful destination and independent-replay checkpoint.
The two source objects were removed and the store verified empty.
The database dashboard returned to database creation, the site reported no database, and its branch API returned 404.
Identity and site lookups returned 404. The source URL returned 404 and the site ID was absent from the site listing.
Database deletion required the dashboard because the API explicitly refused that operation.
The task-owned destination test guests, projects, and staging directories were removed after proof.

- 2026-11-05: Invalid `--accounts` checks now require the exact usage message on stderr and unchanged database rows. The seed suite and full isolated service rehearsal passed with PostgreSQL 17 and S3-compatible storage.
