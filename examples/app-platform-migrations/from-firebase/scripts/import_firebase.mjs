// Run migrations first. Import into an empty destination; never into the live source.
import { pool, transaction } from '../database.mjs';
import { readExport } from './export_data.mjs';
const timestamp=(value,fallback)=>{
  const date=new Date(value??fallback);
  if (!Number.isFinite(date.getTime())) throw new Error('A source timestamp is missing or invalid.');
  return date;
};
try {
  const {manifest,users,config,collections}=await readExport();
  const runtime=collections.controls.find(row=>row.id==='runtime')?.data;
  const schedule=collections.schedules.find(row=>row.id==='archive_reports')?.data;
  if (!runtime || typeof runtime.worker_paused!=='boolean' || typeof runtime.scheduler_paused!=='boolean' ||
      typeof runtime.maintenance!=='boolean' || !runtime.worker_paused || !runtime.scheduler_paused) {
    throw new Error('Pause the source report worker and scheduler before the final export.');
  }
  if (collections.schedules.length!==1 || schedule?.cron!=='0 0 * * *' || schedule.timezone!=='UTC') throw new Error('This example maps one daily UTC archive schedule. Map other source schedules explicitly before importing.');
  await transaction(async client=>{
    await client.query('SELECT pg_advisory_xact_lock(7341207)');
    for (const table of ['users','records','documents','jobs','source_documents','source_auth_users','firebase_auth_config']) {
      if ((await client.query('SELECT 1 FROM '+table+' LIMIT 1')).rowCount) throw new Error('Destination already contains app data. Use an empty migrated database.');
    }
    await client.query('INSERT INTO firebase_auth_config(id,source_project_id,hash_algorithm,signer_key,salt_separator,rounds,memory_cost) VALUES(1,$1,$2,$3,$4,$5,$6)',[manifest.project_id,config.algorithm,config.signerKey,config.saltSeparator,config.rounds,config.memoryCost]);
    for (const user of users) {
      const claims=user.customAttributes?JSON.parse(user.customAttributes):{};
      const created=timestamp(user.createdAt?Number(user.createdAt):manifest.exported_at);
      await client.query("INSERT INTO users(id,email,password_algorithm,firebase_password_hash,firebase_password_salt,disabled,is_admin,created_at) VALUES($1,$2,'firebase_scrypt',$3,$4,$5,$6,$7)",[user.localId,user.email.toLowerCase(),user.passwordHash,user.salt,user.disabled===true,claims.admin===true,created]);
      await client.query('INSERT INTO identities(issuer,subject,user_id) VALUES($1,$2,$2)',['https://securetoken.google.com/'+manifest.project_id,user.localId]);
      await client.query('INSERT INTO source_auth_users(firebase_uid,data) VALUES($1,$2)',[user.localId,user]);
    }
    for (const [name,rows] of Object.entries(collections)) {
      for (const {id,data} of rows) {
        await client.query('INSERT INTO source_documents(collection_name,source_document_id,data) VALUES($1,$2,$3)',[name,id,data]);
      }
    }
    for (const {id,data} of collections.records) {
      await client.query('INSERT INTO records(id,owner_id,title,description,created_at,updated_at) VALUES($1,$2,$3,$4,$5,$6)',[id,data.owner_id,data.title,data.description??'',timestamp(data.created_at,manifest.exported_at),timestamp(data.updated_at,data.created_at??manifest.exported_at)]);
    }
    for (const {id,data} of collections.documents) {
      await client.query('INSERT INTO documents(id,owner_id,filename,object_key,sha256,byte_length,created_at) VALUES($1,$2,$3,$4,$5,$6,$7)',[id,data.owner_id,data.name,data.object_key,data.sha256,data.byte_length,timestamp(data.created_at,manifest.exported_at)]);
    }
    for (const {id,data} of collections.jobs) {
      if (!['PENDING','COMPLETED','ARCHIVED'].includes(data.state)) throw new Error('A source job is in flight. Settle or explicitly reconcile it before import.');
      if (['COMPLETED','ARCHIVED'].includes(data.state) && (typeof data.output!=='string' || !data.completed_at)) throw new Error('A completed source job is missing its output or completion time.');
      await client.query('INSERT INTO jobs(id,owner_id,state,output,created_at,completed_at,archived) VALUES($1,$2,$3,$4,$5,$6,$7)',[id,data.owner_id,data.state==='ARCHIVED'?'COMPLETED':data.state,data.output??null,timestamp(data.created_at,manifest.exported_at),data.completed_at?timestamp(data.completed_at):null,data.state==='ARCHIVED'||data.archived===true]);
    }
    await client.query('UPDATE controls SET worker_paused=$1,scheduler_paused=$2,maintenance_enabled=$3 WHERE id=1',[runtime.worker_paused,runtime.scheduler_paused,runtime.maintenance]);
    await client.query('UPDATE schedules SET next_run_at=$1,last_run_at=$2 WHERE id=$3',[timestamp(schedule.next_run_at),schedule.last_run_at?timestamp(schedule.last_run_at):null,'archive_reports']);
    for (const {data} of collections.scheduled_runs??[]) {
      await client.query('INSERT INTO scheduled_runs(schedule_id,occurrence_at,completed_at,archived_count) VALUES($1,$2,$3,$4)',[data.schedule_id,timestamp(data.occurrence_at??data.occurrence),timestamp(data.completed_at),data.archived_count??0]);
    }
  });
  console.log('Imported Firebase accounts, stable identities, owned data, source document audit, paused jobs and schedule in one PostgreSQL transaction.');
} catch (error) {
  console.error('Firebase import failed: '+(error instanceof SyntaxError?'Invalid JSON in protected export.':error.code||error.message)); process.exitCode=1;
} finally { await pool.end(); }
