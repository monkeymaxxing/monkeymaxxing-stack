import { readFile } from 'node:fs/promises'
import { resolve, join } from 'node:path'
import { database, transaction, closeDatabase } from '../lib/database.mjs'
import { importDocument, getDocument, sha256 } from '../lib/storage.mjs'

const directory=process.env.PRIVATE_EXPORT_DIR
if (!directory) throw new Error('Set PRIVATE_EXPORT_DIR to the protected snapshot directory')
try {
  const raw=await readFile(join(directory,'snapshot.json'))
  const snapshot=JSON.parse(raw)
  const digest=sha256(raw)
  if (snapshot.format_version !== 1) throw new Error('Unsupported snapshot version')
  await transaction(async client=>{
    await client.query('SELECT pg_advisory_xact_lock(61409331)')
    const prior=await client.query('SELECT snapshot_sha256 FROM migration_imports')
    if (prior.rowCount) {
      if (prior.rows.length !== 1 || prior.rows[0].snapshot_sha256 !== digest) throw new Error('A different snapshot was already imported')
      // Recheck storage even on a rerun. Missing objects must remain visible.
      for (const d of snapshot.documents) await getDocument({object_key:d.object_key,sha256:d.sha256,byte_count:d.byte_size})
      console.log('The identical snapshot was already imported')
      return
    }
    for (const table of ['accounts','sessions','records','documents','report_jobs','scheduled_task_runs']) {
      if ((await client.query(`SELECT 1 FROM ${table} LIMIT 1`)).rowCount) throw new Error('Import requires empty app tables and stopped workers')
    }
    if (snapshot.source_manifest.schedule.expression !== '0 3 * * *' || snapshot.source_manifest.schedule.timezone !== 'UTC') throw new Error('Source schedule needs an explicit mapping')
    for (const d of snapshot.documents) {
      const object=snapshot.objects.find(o=>o.document_id===d.id)
      if (!object || object.source_object_key!==d.object_key || object.sha256!==d.sha256 || object.relative_path!==`objects/${d.sha256}` || !/^[0-9a-f]{64}$/.test(d.sha256)) throw new Error('Invalid object mapping')
      const bytes=await readFile(resolve(directory,object.relative_path))
      if (bytes.length!==d.byte_size || sha256(bytes)!==d.sha256) throw new Error('Exported object integrity check failed')
      // The assigned bucket must be empty. UUID-based source keys remain unchanged.
      await importDocument(d,bytes)
      await getDocument({object_key:d.object_key,sha256:d.sha256,byte_count:d.byte_size})
    }
    for (const a of snapshot.accounts) {
      if (!/^[0-9a-f]{32}:[0-9a-f]{128}$/i.test(a.password_hash)) throw new Error('Unsupported native password hash')
      await client.query('INSERT INTO accounts(id,email,password_hash,created_at) VALUES($1,$2,$3,$4)',[a.id,a.email,a.password_hash,a.created_at])
    }
    for (const r of snapshot.records) await client.query('INSERT INTO records(id,account_id,title,description,created_at,updated_at) VALUES($1,$2,$3,$4,$5,$6)',[r.id,r.owner_id,r.title,r.description,r.created_at,r.updated_at])
    for (const d of snapshot.documents) await client.query('INSERT INTO documents(id,account_id,object_key,file_name,sha256,byte_count,created_at) VALUES($1,$2,$3,$4,$5,$6,$7)',[d.id,d.owner_id,d.object_key,d.filename,d.sha256,d.byte_size,d.created_at])
    for (const j of snapshot.jobs) {
      if (!['PENDING','COMPLETED'].includes(j.state) || (j.state==='COMPLETED')!==(j.output!==null && j.completed_at!==null)) throw new Error('Invalid source job state')
      await client.query('INSERT INTO report_jobs(id,account_id,output,created_at,finished_at,archived_at) VALUES($1,$2,$3,$4,$5,$6)',[j.id,j.owner_id,j.output,j.created_at,j.completed_at,j.archived_at])
    }
    for (const s of snapshot.scheduled_task_runs) await client.query('INSERT INTO scheduled_task_runs(id,task_name,affected_reports,completed_at) VALUES($1,$2,$3,$4)',[s.id,s.task_name,s.affected_reports,s.completed_at])
    await client.query('INSERT INTO migration_imports(snapshot_sha256,source_manifest) VALUES($1,$2)',[digest,JSON.stringify(snapshot.source_manifest)])
    console.log('Snapshot imported; native sessions were invalidated')
  })
} catch (error) {
  console.error('Import failed',error.code || error.message)
  process.exitCode=1
} finally { await closeDatabase() }
