import { poolForDatabaseUrl } from './pg_with_multiple_database_servers.mjs';
import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

export const pool = poolForDatabaseUrl(process.env.DATABASE_URL, { statement_timeout: 10000, query_timeout: 12000, max: 5 });
export async function transaction(work) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await work(client);
    await client.query('COMMIT');
    client.release();
    return result;
  } catch (error) {
    try { await client.query('ROLLBACK'); } catch {}
    client.release(error);
    throw error;
  }
}
export async function migrate() {
  const names = (await readdir(new URL('./migrations/', import.meta.url))).filter(name => /^\d+_[a-z_]+\.sql$/.test(name)).sort();
  for (const name of names) {
    const sql = await readFile(new URL('./migrations/' + name, import.meta.url), 'utf8');
    const sha256 = createHash('sha256').update(sql).digest('hex');
    await transaction(async client => {
      await client.query("SET LOCAL lock_timeout='5s'");
      await client.query('SELECT pg_advisory_xact_lock(7341205)');
      await client.query('CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())');
      const previous = (await client.query('SELECT sha256 FROM schema_migrations WHERE name=$1', [name])).rows[0];
      if (previous) {
        if (previous.sha256 !== sha256) throw new Error('Applied migration changed: ' + name);
        return;
      }
      await client.query(sql);
      await client.query('INSERT INTO schema_migrations(name,sha256) VALUES($1,$2)', [name,sha256]);
      console.log('Applied migration ' + name);
    });
  }
}
if (process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href) {
  try { await migrate(); } catch(error) { console.error(error.message); process.exitCode=1; }
  finally { await pool.end(); }
}
