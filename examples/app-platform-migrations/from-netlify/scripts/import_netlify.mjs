import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { verifyExport, sha256 } from './verify_export.mjs';
import { pool, transaction } from '../database.mjs';
export async function importNetlify(directory){
 const {manifest,audit}=verifyExport(directory);
 const digest=sha256(fs.readFileSync(path.join(directory,'manifest.json')));
 return transaction(async client=>{
  await client.query('SELECT pg_advisory_xact_lock(7341207)');
  const previous=(await client.query('SELECT * FROM source_imports WHERE source_site_id=$1',[manifest.site_id])).rows[0];
  if(previous){if(previous.manifest_sha256!==digest)throw Error('This site was imported from a different snapshot. Existing data was preserved.');return {already_imported:true,password_reset_required:true};}
  if((await client.query('SELECT id FROM users LIMIT 1')).rowCount||(await client.query('SELECT 1 FROM source_imports LIMIT 1')).rowCount)throw Error('Import requires an empty dedicated destination. Existing data was preserved.');
  const native=JSON.parse(fs.readFileSync(path.join(directory,'identity_users.json'),'utf8'));
  const issuer=new URL('/.netlify/identity',manifest.source_url).href;
  for(const u of audit.application_users){
   await client.query('INSERT INTO users(id,email,password_hash,is_admin,created_at) VALUES($1,$2,NULL,$3,$4)',[u.id,u.email,u.is_admin,u.created_at]);
   await client.query('INSERT INTO identities(issuer,subject,user_id) VALUES($1,$2,$3)',[issuer,u.id,u.id]);
   await client.query('INSERT INTO source_identity_metadata(user_id,metadata) VALUES($1,$2)',[u.id,JSON.stringify(native.find(n=>n.id===u.id))]);
  }
  for(const r of audit.records)await client.query('INSERT INTO records(id,owner_id,title,description,created_at,updated_at) VALUES($1,$2,$3,$4,$5,$5)',[r.id,r.owner_id,r.title,r.description,r.created_at]);
  for(const d of audit.documents)await client.query('INSERT INTO documents(id,owner_id,filename,object_key,sha256,byte_length,created_at) VALUES($1,$2,$3,$4,$5,$6,$7)',[d.id,d.owner_id,d.file_name,d.object_key,d.sha256,d.byte_length,d.created_at]);
  for(const j of audit.report_jobs)await client.query('INSERT INTO jobs(id,owner_id,state,output,archived,created_at,completed_at) VALUES($1,$2,$3,$4,$5,$6,$7)',[j.id,j.owner_id,j.state,j.output,j.archived,j.created_at,j.completed_at]);
  for(const m of audit.portal_schema_migrations)await client.query('INSERT INTO source_schema_migrations(version,sha256,applied_at) VALUES($1,$2,$3)',[m.version,m.sha256,m.applied_at]);
  for(const s of audit.scheduled_runs)await client.query("INSERT INTO scheduled_runs(schedule_id,occurrence_at,completed_at,archived_count) VALUES('archive_old_reports',$1,$2,$3)",[String(s.occurrence_date).slice(0,10)+'T00:00:00Z',s.completed_at,s.archived_reports]);
  await client.query("UPDATE schedules SET next_run_at=(date_trunc('day',now() AT TIME ZONE 'UTC')+interval '1 day') AT TIME ZONE 'UTC',last_run_at=(SELECT max(completed_at) FROM scheduled_runs) WHERE id='archive_old_reports'");
  await client.query('UPDATE controls SET maintenance_enabled=true,worker_paused=true,scheduler_paused=true WHERE id=1');
  // Source session cookies depend on Netlify Identity. Every returning user logs in again after resetting.
  await client.query('INSERT INTO source_imports(source_site_id,manifest_sha256) VALUES($1,$2)',[manifest.site_id,digest]);
  return {imported_users:audit.application_users.length,imported_records:audit.records.length,imported_jobs:audit.report_jobs.length,password_reset_required:true,source_sessions_imported:0};
 });
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 try{if(process.env.AUTH_MIGRATION_MODE!=='reset-required')throw Error('Set AUTH_MIGRATION_MODE=reset-required to acknowledge the one-time password reset.');if(!process.env.NETLIFY_EXPORT_DIR)throw Error('Set NETLIFY_EXPORT_DIR.');console.log(JSON.stringify(await importNetlify(process.env.NETLIFY_EXPORT_DIR)));}
 catch(error){console.error(error.message);process.exitCode=1;}finally{await pool.end();}
}
