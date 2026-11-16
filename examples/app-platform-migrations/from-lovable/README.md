# Move the Lovable customer portal

This example exports and converts an email/password customer portal built by Lovable's AI. The generated pages stay in TanStack Start.

The destination runs on Node, Postgres and an S3-compatible private bucket. Source database credentials and API tokens never enter browser code.

- [Migration guide](../../../docs/app-platform-migrations/from-lovable.md)
- [Every generated file and service](design.md)
- [Independent app](app/README.md)
- [Versions, results and limits](test-record.md)
- [Original source specification](source-fixture.md)

`inspect-project.mjs` inventories exported code without executing code or reading `.env` values. `read-export.py` reads native database archives without executing source SQL.

Local helper checks:

```sh
node --test examples/app-platform-migrations/from-lovable/inspect-project.test.mjs
PYTHONDONTWRITEBYTECODE=1 python3 examples/app-platform-migrations/from-lovable/read_export_test.py
```

A successful helper test does not prove a migrated app. Use the real exported rows, files and password hashes in the rehearsal.

## Acceptance contracts

- Export code, auth accounts, exact owned rows, private object bytes, queue output, schedule state, migration history and secret names separately.
- Preserve the original UUIDs and bcrypt passwords for the matching email/password fixture. Refuse stronger unsupported account requirements.
- Refuse unknown application columns and nonempty destination imports. Never silently discard source values or overwrite destination data.
- Run the generated TanStack pages independently with PostgreSQL and S3. Keep server-only credentials out of the browser.
- Prove owned CRUD, private file byte equality, shared sessions, logout, interrupted/concurrent jobs, ordered migrations, assigned ports and graceful shutdown.
- Keep source writers and schedules unchanged during phase 1. Defer Stack deployment, real R2 policy checks, primary switching and cutover to phase 2.
- A fresh agent must replay the guide before phase 1 is complete. Record versions, source hashes, passed checks and remaining limits.
