import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const require = createRequire(new URL('../app/package.json', import.meta.url));
const { Client } = require('pg');
const client = new Client({ connectionString: process.env.DATABASE_URL });
const tables = ['users','sessions','records','documents','report_jobs','schedule_runs','schema_migrations'];
await client.connect();
try {
  await client.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');
  const rows = {}, checks = {};
  for (const table of tables) {
    rows[table] = (await client.query(`SELECT row_to_json(value) AS row FROM public.${table} value ORDER BY row_to_json(value)::text`)).rows.map(value => value.row);
    checks[table] = { count: rows[table].length, sha256: createHash('sha256').update(JSON.stringify(rows[table])).digest('hex') };
  }
  await client.query('COMMIT');
  await writeFile(process.env.SNAPSHOT_FILE, JSON.stringify(rows, null, 2) + '\n', { mode: 0o600 });
  console.log(JSON.stringify(checks, null, 2));
} finally { await client.end(); }
