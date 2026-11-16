# Variances and guidance needs

Native Netlify Identity password verifiers are not a normal customer export.
The destination preserves accounts and data, then requires an expiring one-time password reset.
A support-supplied native verifier export is an optional separately verified route.

## Modules and data

The React source stays under `frontend/`. Its API client calls the portable server routes.
`web.mjs` starts the configured number of web processes. `server.mjs` owns HTTP sessions, authorization, CRUD, and private transfers.
`database.mjs` owns checksum-checked transactional migrations and the unchanged Stack database-host helper.
`storage.mjs` owns the private S3 API. File metadata retains original keys, lengths, and SHA-256 values.
`jobs.mjs` owns transactional report claims and UTC scheduled archival. `jobs_runner.mjs` runs background work separately from web startup.

`password_resets.mjs` owns reset requests, mail delivery, hashed tokens, expiry, and redemption.
A request row is keyed by normalized email and has a shared one-minute throttle.
Known and unknown emails use the same public request/response shape. The jobs process decides whether mail should be sent.
A token has one owner, a SHA-256 hash, an expiry, and a use timestamp.
The user-row lock serializes token issuance, password replacement, and login credential verification with session insertion.
Password replacement consumes all unused tokens and revokes sessions in one transaction.
Registration creates the account and initial session in one transaction.

Production mail uses configured TLS SMTP. Synthetic staging uses protected `.eml` files outside the web root.
The one-time token reaches the user through mail, never through the normal HTTP response.
The reset page clears its URL fragment and posts the token privately.

`import_netlify.mjs` maps the verified source audit into the destination schema.
User, record, document, and job IDs stay unchanged. Native Identity issuer/subject mappings and metadata remain explicit.
Source session cookies are invalidated by not importing their native-dependent session rows.
Imported passwords are NULL, so users must complete reset before authentication.
An import ledger rejects a changed snapshot and leaves a repeated identical import unchanged, including newly set passwords.

## Acceptance contracts

- Imported accounts retain native IDs, stored email addresses, owned records, private keys, jobs, outputs, and source migration history.
- Imported accounts and new laptop or staging test accounts begin with no password and can choose a password through an expiring one-time reset link.
- Token issuance, redemption, login, and session revocation cannot create an authenticated session from a superseded password.
- Invalid, expired, replaced, and used tokens fail. Concurrent redemption has exactly one winner.
- Reset never automatically logs a user in. New-password login creates a shared, revocable database session.
- Every record, document, and report route enforces owner ID, including guessed IDs and mutations.
- Private file downloads equal the source bytes. Existing different destination bytes are preserved and refused by the importer.
- Report claim, owner count, output, and completion commit together. Interrupted transactions leave work available.
- Daily archival retains report output and records each scheduled UTC occurrence once.
- Web startup does not migrate or run background work. Production data never enters laptop or staging test data.

## Test data command

`seed_test_data.mjs` owns `seed-test-data`. It accepts `APP_ENV=development`
or `staging`. Its fixed fixture and generated accounts all start with NULL
password verifiers and require password-reset links. There is no fixture
password, so the shared-hash rule does not apply and no generated passwords
are hashed. `--accounts` bulk-adds accounts, identity mappings and one owned
record each. Existing accounts, chosen passwords, documents and jobs remain
unchanged on reruns; smaller counts remove nothing.
