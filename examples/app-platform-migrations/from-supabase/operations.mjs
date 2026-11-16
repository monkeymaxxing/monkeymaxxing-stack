import {readFile,readdir} from 'node:fs/promises';
import {resolve,relative,sep} from 'node:path';
function requireSeedEnvironment() {
 if (!['development','staging'].includes(process.env.APP_ENV)) throw new Error('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data');
}
if (process.argv[2]==='seed-test-data') requireSeedEnvironment();
const {pool,storage,sha256,transaction,putObject,objectBytes,runJob,scheduledTask}=await import('./backend.mjs');
export async function migrate(limit=Infinity){await transaction(async c=>{await c.query("select pg_advisory_xact_lock(hashtext('supabase-exit-migrations'))");await c.query('create table if not exists schema_migrations(version text primary key,sha256 text not null)');for(const name of (await readdir(new URL('./migrations/',import.meta.url))).filter(x=>x.endsWith('.sql')).sort().slice(0,limit)){const text=await readFile(new URL('./migrations/'+name,import.meta.url),'utf8'),hash=sha256(text);const {rows:[old]}=await c.query('select * from schema_migrations where version=$1',[name]);if(old){if(old.sha256!==hash)throw new Error('Applied migration checksum changed: '+name);continue;}await c.query(text);await c.query('insert into schema_migrations values($1,$2)',[name,hash]);}});}
export function validateSnapshot(s){
 for(const key of ['users','identities','mfa_factors','records','documents','report_jobs','schedule_occurrences','cron_jobs','migrations','storage_buckets','storage_objects'])if(!Array.isArray(s[key]))throw new Error('Missing export section: '+key);
 if(s.mfa_factors.length)throw new Error('MFA requires a migration design');
 const fields={records:['id','owner_id','title','created_at','description'],documents:['id','owner_id','file_name','object_key','sha256','byte_length','created_at'],report_jobs:['id','owner_id','status','output','created_at','completed_at']};
 for(const [name,columns] of Object.entries(fields))for(const row of s[name])if(JSON.stringify(Object.keys(row).sort())!==JSON.stringify([...columns].sort()))throw new Error('Export mapping must be updated for '+name);
 const owners=new Set();
 for(const u of s.users){if(!/^\$2[aby]\$\d\d\$/.test(u.encrypted_password||'')||!u.email_confirmed_at||u.deleted_at||u.is_anonymous)throw new Error('Unsupported account state');
 const identities=s.identities.filter(i=>i.user_id===u.id);if(identities.some(i=>i.provider!=='email')||u.raw_app_meta_data?.providers?.some(p=>p!=='email'))throw new Error('External identity requires a migration design');owners.add(u.id);}
 for(const table of ['records','documents','report_jobs'])for(const r of s[table])if(!owners.has(r.owner_id))throw new Error('Unknown owner in '+table);
 for(const r of s.records)if(typeof r.description!=='string'||typeof r.title!=='string')throw new Error('Record mapping needs title and description');
 for(const j of s.report_jobs)if(!['PENDING','COMPLETED'].includes(j.status)||(j.status==='COMPLETED'&&(!j.completed_at||typeof j.output!=='string')))throw new Error('Unsupported job state');
 for(const d of s.documents){if(!/^[a-f0-9]{64}$/.test(d.sha256)||!d.object_key.startsWith(d.owner_id+'/'))throw new Error('Invalid document manifest');}
 if(s.cron_jobs.some(j=>j.active))throw new Error('Stop source cron before final export');
 if(s.cron_jobs.length!==1||s.cron_jobs[0].jobname!=='portal-minute-marker'||s.cron_jobs[0].schedule!=='* * * * *'||!/^insert into public\.schedule_occurrences\(occurrence_minute\) values\(date_trunc\('minute',now\(\)\)\) on conflict do nothing$/.test(s.cron_jobs[0].command))throw new Error('Schedule requires an explicit mapping');
 const nativeObjects=s.storage_objects.filter(x=>x.bucket_id==='documents').map(x=>x.name).sort();if(JSON.stringify(nativeObjects)!==JSON.stringify(s.documents.map(x=>x.object_key).sort()))throw new Error('Storage objects and document references differ');
 if(s.storage_buckets.some(b=>b.id!=='documents'||b.public))throw new Error('Bucket mapping must be reviewed');
}
export async function importSnapshot(snapshotFile,objectDir){const raw=await readFile(snapshotFile),s=JSON.parse(raw);validateSnapshot(s);const receipt=sha256(raw);
 await transaction(async c=>{
 await c.query("select pg_advisory_xact_lock(hashtext('supabase-exit-import'))");
 const {rows:[counts]}=await c.query('select (select count(*) from users)+(select count(*) from records)+(select count(*) from documents)+(select count(*) from report_jobs)+(select count(*) from import_receipts) as count');if(Number(counts.count))throw new Error('Import requires an empty destination');
 for(const d of s.documents){const path=resolve(objectDir,d.object_key);if(!relative(resolve(objectDir),path)||relative(resolve(objectDir),path).startsWith('..'+sep)||relative(resolve(objectDir),path)==='..')throw new Error('Unsafe object key');const bytes=await readFile(path);if(sha256(bytes)!==d.sha256||bytes.length!==Number(d.byte_length))throw new Error('Exported object integrity check failed');
 // Do not overwrite a different object if an earlier import reached storage before a database rollback.
 let existing;try{existing=await objectBytes(d.object_key);}catch(e){if(!['NoSuchKey','NotFound'].includes(e.name))throw e;}
 if(existing&&sha256(existing)!==d.sha256)throw new Error('Destination object differs');if(!existing)await putObject(d.object_key,bytes);
 if(sha256(await objectBytes(d.object_key))!==d.sha256)throw new Error('Uploaded object integrity check failed');}
 for(const u of s.users)await c.query('insert into users(id,email,password_hash,email_confirmed_at,banned_until,source_identity) values($1,$2,$3,$4,$5,$6)',[u.id,u.email,u.encrypted_password,u.email_confirmed_at,u.banned_until,JSON.stringify({issuer:'supabase',subject:u.id,identities:s.identities.filter(x=>x.user_id===u.id),app_metadata:u.raw_app_meta_data,user_metadata:u.raw_user_meta_data})]);
 for(const r of s.records)await c.query('insert into records(id,owner_id,title,created_at,description) values($1,$2,$3,$4,$5)',[r.id,r.owner_id,r.title,r.created_at,r.description]);
 for(const d of s.documents)await c.query('insert into documents(id,owner_id,file_name,object_key,sha256,byte_length,created_at) values($1,$2,$3,$4,$5,$6,$7)',[d.id,d.owner_id,d.file_name,d.object_key,d.sha256,d.byte_length,d.created_at]);
 for(const j of s.report_jobs)await c.query('insert into report_jobs(id,owner_id,status,output,created_at,completed_at) values($1,$2,$3,$4,$5,$6)',[j.id,j.owner_id,j.status,j.output,j.created_at,j.completed_at]);
 for(const o of s.schedule_occurrences)await c.query('insert into schedule_occurrences values($1,$2)',[o.occurrence_minute,o.ran_at]);
 for(const j of s.cron_jobs)await c.query('insert into source_schedules values($1,$2,$3,$4,$5)',[j.jobname,j.schedule,j.command,j.active,JSON.stringify(j)]);
 await c.query('insert into import_receipts(snapshot_sha256) values($1)',[receipt]);
 });return {users:s.users.length,records:s.records.length,documents:s.documents.length,report_jobs:s.report_jobs.length};}
export async function seedTestData() {
 requireSeedEnvironment();
 const args=process.argv.slice(3);
 if(args.length && (args.length!==2 || args[0]!=='--accounts' || !/^\d+$/.test(args[1]) || BigInt(args[1])<2n)) throw new Error('Usage: seed-test-data [--accounts N]; --accounts must be a whole number of at least 2');
 const accounts=args[1]||'2',password=process.env.FIXTURE_PASSWORD;
 if(!password) throw new Error('FIXTURE_PASSWORD is required');
 if(password.length<8 || Buffer.byteLength(password)>72) throw new Error('FIXTURE_PASSWORD must contain at least 8 characters and at most 72 UTF-8 bytes');
 const {default:bcrypt}=await import('bcryptjs'),{randomUUID}=await import('node:crypto');
 await transaction(async client=>{
  // Hold account writes until the ownership guard and all seed rows commit together.
  await client.query('LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE');
  const unrelated=await client.query(`SELECT 1 FROM users
   WHERE email NOT IN ('barbara@example.com','michael@example.com')
   AND NOT (email ~ '^test-account-[0-9]{6,}@example[.]com$'
    AND substring(email from '^test-account-([0-9]+)@')::numeric >= 3
    AND email = 'test-account-' || repeat('0',greatest(0,6-length(substring(email from '^test-account-([0-9]+)@')::numeric::text)))
     || substring(email from '^test-account-([0-9]+)@')::numeric::text || '@example.com') LIMIT 1`);
  if(unrelated.rowCount) throw new Error('seed-test-data refuses to run: the database contains accounts that are not test data');
  for(const [email,title,description,fileName,bytes] of [
   ['barbara@example.com','Barbara invoice','First synthetic record','barbara-note.txt','Barbara synthetic document\n'],
   ['michael@example.com','Michael invoice','Second synthetic record','michael-note.txt','Michael synthetic document\n']
  ]) {
   if((await client.query('SELECT 1 FROM users WHERE email=$1',[email])).rowCount) continue;
   const id=randomUUID();
   await client.query('INSERT INTO users(id,email,password_hash,email_confirmed_at) VALUES($1,$2,$3,now())',[id,email,await bcrypt.hash(password,12)]);
   await client.query('INSERT INTO records(owner_id,title,description) VALUES($1,$2,$3)',[id,title,description]);
   const documentId=randomUUID(),key=`${id}/${documentId}/${fileName}`,b=Buffer.from(bytes);
   await putObject(key,b);
   await client.query('INSERT INTO documents VALUES($1,$2,$3,$4,$5,$6,now())',[documentId,id,fileName,key,sha256(b),b.length]);
   await client.query('INSERT INTO report_jobs(owner_id) VALUES($1)',[id]);
  }
  if(BigInt(accounts)>2n) {
   const passwordHash=await bcrypt.hash(password,12);
   await client.query(`INSERT INTO users(id,email,password_hash,email_confirmed_at)
    SELECT gen_random_uuid(), 'test-account-' || lpad(n::text,greatest(6,length(n::text)),'0') || '@example.com', $2, now()
    FROM generate_series(3,$1::bigint) n ON CONFLICT (email) DO NOTHING`,[accounts,passwordHash]);
   await client.query(`INSERT INTO records(owner_id,title,description)
    SELECT u.id,'Test record ' || n,'Generated test record' FROM users u
    JOIN generate_series(3,$1::bigint) n ON u.email='test-account-' || lpad(n::text,greatest(6,length(n::text)),'0') || '@example.com'
    WHERE NOT EXISTS (SELECT 1 FROM records r WHERE r.owner_id=u.id)`,[accounts]);
  }
 });
}

async function main(){const command=process.argv[2];if(command==='migrate')await migrate(process.env.MIGRATION_LIMIT?Number(process.env.MIGRATION_LIMIT):Infinity);else if(command==='import'){if(!process.env.EXPORT_SNAPSHOT_FILE||!process.env.EXPORT_OBJECT_DIR)throw new Error('EXPORT_SNAPSHOT_FILE and EXPORT_OBJECT_DIR required');console.log(await importSnapshot(process.env.EXPORT_SNAPSHOT_FILE,process.env.EXPORT_OBJECT_DIR));}else if(command==='seed-test-data')await seedTestData();else if(command==='jobs'){let stopping=false;process.on('SIGTERM',()=>{stopping=true;});process.on('SIGINT',()=>{stopping=true;});while(!stopping){if(process.env.RUN_REPORT_JOBS==='true')await runJob();if(process.env.RUN_SCHEDULE==='true')await scheduledTask();await new Promise(r=>setTimeout(r,500));}}else throw new Error('Use migrate, import, jobs or seed-test-data');}
if(process.argv[1]&&resolve(process.argv[1])===resolve(new URL(import.meta.url).pathname)){try{await main();}finally{await pool.end();storage.destroy();}}
