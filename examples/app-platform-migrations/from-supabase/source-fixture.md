# Source fixture

The source is a handwritten Vite/React portal using the Supabase JavaScript client directly.
Supabase Auth owns confirmed synthetic email/password accounts. Postgres owns app data and applies owner policies through PostgREST.
Private Storage uses a `documents` bucket and owner UUID prefixes.
The `report-job` Edge Function validates the access token, then calls an authenticated SQL function to queue or process an owned report.
The `portal-minute-marker` pg_cron job records one occurrence per minute.

| User | Record | Description | File | Exact bytes |
| --- | --- | --- | --- | --- |
| barbara@example.com | Barbara invoice | First synthetic record | barbara-note.txt | `Barbara synthetic document` plus LF |
| michael@example.com | Michael invoice | Second synthetic record | michael-note.txt | `Michael synthetic document` plus LF |

Each user has one private document and one pending report at export. One extra Barbara report is completed.
The exported file hashes are:

- Barbara: `05fc126dc203e0579d73a6365e130ba77d1f422d87042b362456a2885029d32a`
- Michael: `784483c538543c904f1232e9c939417711e771b531e3f04c3d45f6699ad65c55`

The second schema version adds `records.description` with an empty default.
The source uses Vite 7.2.2, React 19.2.0, Supabase JavaScript 2.108.2 and PostgreSQL 17.11.
The independent example pins its own runtime dependencies in `package-lock.json`.
Source identifiers, credentials and full exports stay outside this public example.
