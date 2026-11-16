// Run against a restored archive or a read-only source connection.
import { readFile, writeFile, mkdir, copyFile } from 'node:fs/promises'
import { resolve, basename, join } from 'node:path'
import pg from 'pg'
import { sha256 } from '../lib/storage.mjs'

const output = process.env.PRIVATE_EXPORT_DIR
const downloads = process.env.BLOB_EXPORT_DIR
const sourceCode = process.env.SOURCE_CODE_DIR
const envNamesFile = process.env.SOURCE_ENV_NAMES_FILE
if (!output || !downloads || !sourceCode || !process.env.SOURCE_DATABASE_URL || !envNamesFile) throw new Error('Set PRIVATE_EXPORT_DIR, BLOB_EXPORT_DIR, SOURCE_CODE_DIR, SOURCE_DATABASE_URL, and SOURCE_ENV_NAMES_FILE')
process.umask(0o077)
const client = new pg.Client({ connectionString: process.env.SOURCE_DATABASE_URL, statement_timeout: 15000 })
try {
  await client.connect()
  await client.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
  const query = async sql => (await client.query(sql)).rows
  const users = await query('SELECT id,email,banned FROM neon_auth."user" ORDER BY id')
  const accounts = await query(`SELECT u.id,u.email,a.password AS password_hash,u."createdAt" AS created_at
    FROM neon_auth."user" u JOIN neon_auth.account a ON a."userId"=u.id
    WHERE a."providerId"='credential' ORDER BY u.id`)
  if (users.some(user => user.banned) || accounts.length !== users.length || new Set(accounts.map(a=>a.id)).size !== users.length) {
    throw new Error('Account state needs an explicit migration: require one password credential per unbanned user')
  }
  const records = await query('SELECT * FROM public.records ORDER BY id')
  const documents = await query('SELECT * FROM public.documents ORDER BY id')
  const jobs = await query('SELECT * FROM public.report_jobs ORDER BY id')
  const scheduled_task_runs = await query('SELECT * FROM public.scheduled_task_runs ORDER BY id')
  const source_migrations = await query('SELECT * FROM public.schema_migrations ORDER BY version')
  const sessions = Number((await query('SELECT count(*) AS count FROM neon_auth.session'))[0].count)
  const nativeTables = await query(`SELECT table_name FROM information_schema.tables WHERE table_schema='neon_auth' ORDER BY table_name`)
  // These identity features need their own mapping. Do not silently discard them.
  for (const table of ['organization','member','invitation']) {
    if (Number((await query(`SELECT count(*) AS count FROM neon_auth.${table}`))[0].count)) throw new Error('Organization identity data needs an explicit migration')
  }
  if (Number((await query(`SELECT count(*) AS count FROM neon_auth.account WHERE "providerId" <> 'credential'`))[0].count)) throw new Error('External identity providers need an explicit migration')
  const configuration = JSON.parse(await readFile(join(sourceCode,'vercel.json'),'utf8'))
  if (JSON.stringify(configuration.crons) !== JSON.stringify([{path:'/api/cron/archive',schedule:'0 3 * * *'}])) throw new Error('Review the source schedule before exporting')
  await mkdir(join(output,'objects'),{recursive:true,mode:0o700})
  const objects = []
  for (const document of documents) {
    if (basename(document.filename) !== document.filename || !/^[0-9a-f]{64}$/.test(document.sha256)) throw new Error('Unsafe document metadata')
    // Accept either previously hashed exports or the fixture's original names.
    let path = resolve(downloads,document.sha256)
    let bytes
    try { bytes = await readFile(path) } catch (error) {
      if (error.code !== 'ENOENT') throw error
      path = resolve(downloads,document.filename); bytes = await readFile(path)
    }
    if (bytes.length !== document.byte_size || sha256(bytes) !== document.sha256) throw new Error('Source object integrity check failed')
    await copyFile(path,join(output,'objects',document.sha256))
    objects.push({ document_id:document.id,source_object_key:document.object_key,relative_path:`objects/${document.sha256}`,sha256:document.sha256,byte_count:bytes.length })
  }
  const snapshot = { format_version:1,accounts,records,documents,jobs,scheduled_task_runs,objects,
    source_manifest:{source_migrations,source_session_count:sessions,session_policy:'invalidate and require fresh login',native_auth_tables:nativeTables.map(t=>t.table_name),schedule:{expression:'0 3 * * *',timezone:'UTC',task:'archive_old_reports'},
      env_var_names:JSON.parse(await readFile(envNamesFile,'utf8')).env_var_names} }
  await client.query('COMMIT')
  await writeFile(join(output,'snapshot.json'),JSON.stringify(snapshot,null,2)+'\n',{mode:0o600,flag:'wx'})
  console.log('Private snapshot exported:',JSON.stringify({accounts:accounts.length,records:records.length,documents:documents.length,jobs:jobs.length,source_sessions:sessions}))
} catch (error) {
  await client.query('ROLLBACK').catch(()=>{})
  console.error('Export failed',error.code || error.message)
  process.exitCode=1
} finally { await client.end().catch(()=>{}) }
