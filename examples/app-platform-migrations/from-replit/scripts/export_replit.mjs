// Run from the source project's Replit Shell, with its installed dependencies.
import pg from 'pg';
import { Client } from '@replit/object-storage';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { resolve, join } from 'node:path';

process.umask(0o077);
const directory = resolve(process.env.EXPORT_DIR || 'migration-export');
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
await mkdir(directory, { mode: 0o700 }); // Refuse to mix snapshots or overwrite an export.
await mkdir(join(directory, 'objects'), { mode: 0o700 });
const database = new pg.Client({ connectionString: process.env.DATABASE_URL, statement_timeout: 60000 });
try {
  await database.connect();
  await database.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');
  const snapshot = (await database.query('SELECT pg_export_snapshot() AS id')).rows[0].id;
  const url = new URL(process.env.DATABASE_URL);
  const databaseEnv = { ...process.env, PGHOST: url.hostname, PGPORT: url.port || '5432', PGDATABASE: decodeURIComponent(url.pathname.slice(1)), PGUSER: decodeURIComponent(url.username), PGPASSWORD: decodeURIComponent(url.password) };
  for (const [key, value] of url.searchParams) databaseEnv['PG' + key.toUpperCase()] = value;
  execFileSync('pg_dump', ['--format=custom', '--no-owner', '--no-acl', '--snapshot', snapshot, '--file', join(directory, 'database.dump')], { env: databaseEnv, stdio: ['ignore', 'ignore', 'pipe'] });
  const tableNames = (await database.query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).rows.map(row => row.tablename);
  const tables = {};
  for (const name of tableNames) tables[name] = (await database.query('SELECT * FROM public."' + name.replaceAll('"', '""') + '"')).rows;
  const storage = new Client();
  const listing = await storage.list();
  if (!listing.ok) throw new Error('Cannot list App Storage objects.');
  const objects = [];
  for (const object of listing.value) {
    const result = await storage.downloadAsBytes(object.name);
    if (!result.ok) throw new Error('Cannot export an App Storage object.');
    const bytes = Buffer.isBuffer(result.value) ? result.value : result.value[0];
    if (!Buffer.isBuffer(bytes)) throw new Error('Unexpected SDK download return type.');
    const digest = sha256(bytes);
    const filename = 'objects/' + digest;
    await writeFile(join(directory, filename), bytes, { mode: 0o600 });
    objects.push({ key: object.name, sha256: digest, byte_length: bytes.length, file: filename });
  }
  for (const document of tables.documents || []) {
    const object = objects.find(object => object.key === document.object_key);
    if (!object || object.sha256 !== document.sha256 || object.byte_length !== Number(document.byte_length)) throw new Error('Database and object bytes disagree.');
  }
  const archive = execFileSync('git', ['archive', '--format=zip', 'HEAD']);
  await writeFile(join(directory, 'source.zip'), archive, { mode: 0o600 });
  const manifest = {
    exported_at: new Date().toISOString(), project_id: process.env.REPL_ID,
    source_commit: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
    uncommitted_paths: execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8' }).trim().split('\n').filter(Boolean),
    database_version: (await database.query('SHOW server_version')).rows[0].server_version,
    pg_dump_version: execFileSync('pg_dump', ['--version'], { encoding: 'utf8' }).trim(),
    node_version: process.version, table_counts: Object.fromEntries(Object.entries(tables).map(([name, rows]) => [name, rows.length])),
    objects, secret_env_names: Object.keys(process.env).sort(),
    checksums: { 'source.zip': sha256(archive), 'database.dump': sha256(await readFile(join(directory, 'database.dump'))) }
  };
  await writeFile(join(directory, 'tables.json'), JSON.stringify(tables, null, 2), { mode: 0o600 });
  manifest.checksums['tables.json'] = sha256(await readFile(join(directory, 'tables.json')));
  await writeFile(join(directory, 'manifest.json'), JSON.stringify(manifest, null, 2), { mode: 0o600 });
  await database.query('COMMIT');
  console.log('EXPORT_COMPLETE: code, snapshot database, table audit, object bytes, environment names.');
} catch {
  console.error('EXPORT_FAILED: keep partial files private; inspect the source Shell without sharing credentials.');
  process.exitCode = 1;
} finally { await database.end(); }
