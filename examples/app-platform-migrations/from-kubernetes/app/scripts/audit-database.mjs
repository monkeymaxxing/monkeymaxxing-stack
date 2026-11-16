import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { pool, transaction } from '../database.mjs';

const tables = ['users', 'sessions', 'records', 'documents', 'report_jobs', 'controls', 'scheduled_runs', 'schema_migrations'];
const path = (process.env.EXPORT_DIR || '/export') + '/table-audit.json';
const normalize = value => JSON.stringify(value, (_, item) =>
  item && typeof item === 'object' && !Array.isArray(item) && !(item instanceof Date)
    ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item);
try {
  const rows = await transaction(async client => {
    await client.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY');
    const result = {};
    for (const table of tables) {
      result[table] = (await client.query(`SELECT to_jsonb(source_row) AS row FROM ${table} AS source_row`)).rows.map(result => result.row)
        .sort((a, b) => normalize(a).localeCompare(normalize(b)));
    }
    return result;
  });
  if (process.argv[2] === 'export') {
    if (!rows.controls[0].maintenance || !rows.controls[0].jobs_paused) throw Error('Pause HTTP writes and jobs before audit export');
    await writeFile(path, JSON.stringify(rows), { flag: 'wx', mode: 0o600 });
  } else if (process.argv[2] === 'compare') {
    const expected = JSON.parse(await readFile(path, 'utf8'));
    if (normalize(expected) !== normalize(rows)) throw Error('Database rows differ from the frozen source audit');
  } else throw Error('Usage: audit-database.mjs export|compare');
  console.log(JSON.stringify({ database_audit: 'PASS', tables: tables.length,
    row_counts: Object.fromEntries(tables.map(table => [table, rows[table].length])),
    sha256: createHash('sha256').update(normalize(rows)).digest('hex') }));
} finally { await pool.end(); }
