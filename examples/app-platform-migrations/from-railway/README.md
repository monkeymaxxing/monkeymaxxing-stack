# Export and rehearse a Railway portal

Copy this directory into your application's repository.
Follow [From Railway](../../../docs/app-platform-migrations/from-railway.md) before running the export or restore commands.

- `app/` contains the standalone portal and locked dependencies.
- `data-transfer.mjs` exports a consistent database snapshot and bucket objects, then restores into an empty destination.
- `tests/` creates disposable rehearsal settings and checks preserved customer behavior.
- `test-record.md` states tested versions, results, and remaining deployment checks.

Exports contain account hashes and private documents. Store exports outside Git with mode 700 directories and mode 600 files.
The rehearsal changes only the disposable destination. The source stays read-only.
