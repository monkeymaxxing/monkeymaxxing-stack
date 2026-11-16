import { readFile, readdir } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
if (process.argv[2] === 'seed-test-data' && !['development', 'staging'].includes(process.env.APP_ENV)) {
  throw new Error('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data');
}
const { pool, transaction, sha256, putObject, objectBytes, runJob, maintenance } = await import('./backend.mjs');
const root = dirname(fileURLToPath(import.meta.url));
export async function migrate(through = '999') {
  // A session lock serializes deployment migrations; do not run this through transaction pooling.
  const client = await pool.connect();
  try {
    await client.query('SELECT pg_advisory_lock(87126352)');
    await client.query('CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY,sha256 text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now())');
    for (const name of (await readdir(resolve(root,'migrations'))).filter(n=>n.endsWith('.sql')).sort()) {
      if (name.slice(0,3) > through) continue;
      const sql = await readFile(resolve(root,'migrations',name),'utf8'), hash = sha256(sql);
      const {rows:[prior]} = await client.query('SELECT sha256 FROM schema_migrations WHERE name=$1',[name]);
      if (prior) { if (prior.sha256 !== hash) throw new Error('Applied migration changed: '+name); continue; }
      try {
        await client.query('BEGIN');
        await client.query(sql);
        await client.query('INSERT INTO schema_migrations(name,sha256) VALUES($1,$2)',[name,hash]);
        await client.query('COMMIT');
      } catch(error) { await client.query('ROLLBACK'); throw error; }
    }
  } finally { await client.query('SELECT pg_advisory_unlock(87126352)').catch(()=>{});client.release(); }
}
export async function importSnapshot(snapshotPath, objectDir) {
  const snapshot = JSON.parse(await readFile(snapshotPath,'utf8'));
  if (snapshot.format_version !== 1) throw new Error('Unsupported export format');
  if (snapshot.report_jobs.some(job=>job.status==='RUNNING')) throw new Error('Reconcile source RUNNING jobs before import');
  const columns={records:['id','user_id','title','created_at','updated_at'],
      documents:['id','user_id','record_id','file_name','object_key','sha256','byte_count','created_at'],
      report_jobs:['id','user_id','status','requested_at','started_at','completed_at','output','attempts','archived_at']};
  for(const [table,fields] of Object.entries(columns)) for(const row of snapshot[table]) {
    if (Object.keys(row).length !== fields.length || Object.keys(row).some(key=>!fields.includes(key))) throw new Error('Exported '+table+' columns changed; update the import mapping before conversion');
  }
  // Validate every file before uploading anything. Object keys must stay inside the export directory.
  const files=[];
  for (const document of snapshot.documents) {
    const path=resolve(objectDir,document.object_key);
    if (!path.startsWith(resolve(objectDir)+'/')) throw new Error('Object key leaves the export directory');
    const bytes=await readFile(path);
    if (sha256(bytes)!==document.sha256 || bytes.length!==Number(document.byte_count)) throw new Error('Exported file hash or byte count differs');
    files.push({key:document.object_key,bytes});
  }
  return transaction(async client => {
    await client.query('LOCK TABLE users,records,documents,report_jobs IN EXCLUSIVE MODE');
    const {rows:[count]}=await client.query('SELECT (SELECT count(*) FROM users)+(SELECT count(*) FROM records)+(SELECT count(*) FROM documents)+(SELECT count(*) FROM report_jobs) AS total');
    if (Number(count.total)!==0) throw new Error('Import requires a new empty destination');
    for (const user of snapshot.users) {
      if (!/^\$2[aby]\$/.test(user.encrypted_password||'')) throw new Error('Password reset design required for this hash');
      await client.query('INSERT INTO users VALUES($1,$2,$3,$4,$5)',[user.id,user.email,user.encrypted_password,user.email_confirmed_at,user.banned_until]);
    }
    for (const [table,fields] of Object.entries(columns)) for (const row of snapshot[table]) {
      await client.query(`INSERT INTO ${table}(${fields.join(',')}) VALUES(${fields.map((_,i)=>'$'+(i+1)).join(',')})`,fields.map(f=>row[f]));
    }
    for(const schedule of snapshot.schedules) await client.query('INSERT INTO imported_schedules VALUES($1,$2)',[schedule.jobname,JSON.stringify(schedule)]);
    for(const row of snapshot.source_migrations) await client.query('INSERT INTO source_migrations VALUES($1)',[JSON.stringify(row)]);
    for(const file of files) {
      await putObject(file.key,file.bytes);
      if(sha256(await objectBytes(file.key))!==sha256(file.bytes)) throw new Error('Destination file hash differs');
    }
    return {users:snapshot.users.length,records:snapshot.records.length,documents:files.length,report_jobs:snapshot.report_jobs.length};
  });
}
async function seedTestData() {
  const args = process.argv.slice(3);
  if (args.length && (args.length !== 2 || args[0] !== '--accounts' || !/^\d+$/.test(args[1]) || BigInt(args[1]) < 2n)) {
    throw new Error('Usage: seed-test-data [--accounts N]; --accounts must be a whole number of at least 2');
  }
  const accounts = args[1] || '2';

  const password=process.env.FIXTURE_PASSWORD;
  if (!password) throw new Error('FIXTURE_PASSWORD is required');
  // Seeds invented data only. Never reads an export or production credentials.
  const bcrypt=await import('bcryptjs'),{randomUUID}=await import('node:crypto');
  for (const [email,title,text] of [['barbara@example.com','Barbara invoice','Barbara synthetic document\n'],['michael@example.com','Michael invoice','Michael synthetic document\n']]) {
    await transaction(async client=>{
      const {rows:[user]}=await client.query('INSERT INTO users VALUES($1,$2,$3,now(),NULL) ON CONFLICT(email) DO NOTHING RETURNING id',[randomUUID(),email,await bcrypt.hash(password,12)]);
      if (!user) return;
      const {rows:[record]}=await client.query('INSERT INTO records(user_id,title) VALUES($1,$2) RETURNING id',[user.id,title]);
      const name=email.split('@')[0]+'-note.txt',key=`${user.id}/${randomUUID()}/${name}`,bytes=Buffer.from(text);
      await putObject(key,bytes);
      await client.query('INSERT INTO documents(user_id,record_id,file_name,object_key,sha256,byte_count) VALUES($1,$2,$3,$4,$5,$6)',[user.id,record.id,name,key,sha256(bytes),bytes.length]);
      await client.query('INSERT INTO report_jobs(user_id) VALUES($1)',[user.id]);
    });
  }
  if (BigInt(accounts) > 2n) {
    const passwordHash = await bcrypt.hash(password, 12);
    await transaction(async client => {
      await client.query(`INSERT INTO users(id,email,password_hash,email_confirmed_at)
        SELECT gen_random_uuid(), 'test-account-' || lpad(n::text,greatest(6,length(n::text)),'0') || '@example.com', $2, now()
        FROM generate_series(3,$1::bigint) n ON CONFLICT (email) DO NOTHING`, [accounts,passwordHash]);
      await client.query(`INSERT INTO records(user_id,title,description)
        SELECT u.id, 'Test record ' || n, 'Generated test record' FROM users u
        JOIN generate_series(3,$1::bigint) n ON u.email='test-account-' || lpad(n::text,greatest(6,length(n::text)),'0') || '@example.com'
        WHERE NOT EXISTS (SELECT 1 FROM records r WHERE r.user_id=u.id)`, [accounts]);
    });
  }
}
async function main() {
  switch(process.argv[2]) {
    case 'migrate': await migrate(process.argv[3]); console.log('Migrations applied'); break;
    case 'import': console.log(JSON.stringify(await importSnapshot(process.argv[3],process.argv[4]))); break;
    case 'seed-test-data': await seedTestData(); console.log('Test data ready'); break;
    case 'maintenance': console.log(JSON.stringify({archived:(await maintenance()).rowCount})); break;
    case 'jobs': {
      let stopping=false;for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{stopping=true});
      while(!stopping) {const result=await runJob();if(!result.processed) await new Promise(r=>setTimeout(r,1000));}
      break;
    }
    default: throw new Error('Use migrate, import, seed-test-data, maintenance, or jobs');
  }
}
if(process.argv[1]===fileURLToPath(import.meta.url)) {
  try { await main(); } catch(error) { console.error('Operation failed:',error.code || error.message);process.exitCode=1; }
  finally {await pool.end();}
}
