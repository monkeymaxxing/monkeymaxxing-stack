import { poolForDatabaseUrl } from './pg_with_multiple_database_servers.mjs';
import { readdir, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
export const pool = poolForDatabaseUrl(process.env.DATABASE_URL, { max: 10, connectionTimeoutMillis: 10000, statement_timeout: 10000, idle_in_transaction_session_timeout: 15000 });
pool.on('error', () => console.error('A database connection closed. A later request may reconnect.'));
export async function transaction(action) {
  const client = await pool.connect();
  try { await client.query('BEGIN'); const result = await action(client); await client.query('COMMIT'); return result; }
  catch (error) { await client.query('ROLLBACK').catch(()=>{}); throw error; }
  finally { client.release(); }
}
export async function migrate() {
  const client = await pool.connect();
  try {
    await client.query('SELECT pg_advisory_lock(20261104)');
    await client.query('CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())');
    for (const name of (await readdir(new URL('./migrations/', import.meta.url))).filter(n=>/^\d+_.*\.sql$/.test(n)).sort()) {
      const sql = await readFile(new URL('./migrations/'+name, import.meta.url), 'utf8');
      const hash = createHash('sha256').update(sql).digest('hex');
      const existing = await client.query('SELECT sha256 FROM schema_migrations WHERE version=$1',[name]);
      if (existing.rowCount) { if (existing.rows[0].sha256 !== hash) throw Error('Applied migration checksum differs: '+name); continue; }
      await client.query('BEGIN');
      try { await client.query(sql); await client.query('INSERT INTO schema_migrations(version,sha256) VALUES($1,$2)',[name,hash]); await client.query('COMMIT'); console.log('Applied migration '+name); }
      catch(error) { await client.query('ROLLBACK'); throw error; }
    }
  } finally { await client.query('SELECT pg_advisory_unlock(20261104)').catch(()=>{});client.release(); }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { await migrate(); } finally { await pool.end(); }
}
