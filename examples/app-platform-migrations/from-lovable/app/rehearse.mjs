// Run only against a disposable empty database and a private rehearsal bucket.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { once } from 'node:events';
import { pool, api, sha256, objectBytes, runJob, transaction } from './backend.mjs';
import { migrate, importSnapshot } from './operations.mjs';
import bcrypt from 'bcryptjs';
const required=['REHEARSAL_SNAPSHOT','REHEARSAL_OBJECT_DIR','REHEARSAL_PASSWORD_FILE','REHEARSAL_RESULT_FILE'];
for(const name of required) if(!process.env[name]) throw new Error(name+' is required');
const snapshot=JSON.parse(await readFile(process.env.REHEARSAL_SNAPSHOT,'utf8'));
const password=(await readFile(process.env.REHEARSAL_PASSWORD_FILE,'utf8')).trim();
const result={scope:'Independent TanStack portal on PostgreSQL and S3-compatible storage; no source writes or Stack deployment',checks:[],versions:{node:process.version}};
const check=(name)=>result.checks.push({name,passed:true});
const workers=[];
async function save(){await writeFile(process.env.REHEARSAL_RESULT_FILE,JSON.stringify(result,null,2)+'\n',{mode:0o600});}
async function request(path,method='GET',body,token='',port=8001,extraHeaders={}) {
 const response=await fetch(`http://127.0.0.1:${port}${path}`,{method,
  headers:{Origin:process.env.PUBLIC_ORIGIN,...(token?{Cookie:token}:{}),...(body instanceof Buffer?{}:{'Content-Type':'application/json'}),...extraHeaders},
  body:body===undefined?undefined:body instanceof Buffer?body:JSON.stringify(body)});
 const text=await response.text();let data;try{data=JSON.parse(text)}catch{data=text}
 return {status:response.status,data,cookie:response.headers.get('set-cookie')?.split(';')[0]};
}
async function waitHealthy(port,child) {
 for(let i=0;i<100;i++) {
  if(child.exitCode!==null) throw new Error('App exited before health check');
  try {if((await fetch(`http://127.0.0.1:${port}/healthz`)).status===200)return;}catch{}
  await new Promise(r=>setTimeout(r,100));
 }
 throw new Error('App health check timed out');
}
try {
 result.versions.postgresql=(await pool.query('SHOW server_version')).rows[0].server_version;
 for(const user of snapshot.users) assert(await bcrypt.compare(password,user.encrypted_password));
 check('Exported bcrypt hashes accept each existing fixture password');
 await migrate('001');
 const imported=await importSnapshot(process.env.REHEARSAL_SNAPSHOT,process.env.REHEARSAL_OBJECT_DIR);
 assert.deepEqual(imported,{users:2,records:2,documents:2,report_jobs:2});
 check('Import preserves fixture counts in initial schema');
 await assert.rejects(importSnapshot(process.env.REHEARSAL_SNAPSHOT,process.env.REHEARSAL_OBJECT_DIR),/empty destination/);
 check('Repeat import refuses to overwrite destination data');
 const changed=structuredClone(snapshot);changed.records[0].description='New source value';
 const changedPath=process.env.REHEARSAL_RESULT_FILE+'.changed-source.json';
 await writeFile(changedPath,JSON.stringify(changed),{mode:0o600});
 await assert.rejects(importSnapshot(changedPath,process.env.REHEARSAL_OBJECT_DIR),/columns changed/);
 check('Unexpected source columns refuse conversion instead of silently losing new values');
 for(const table of ['records','documents','report_jobs']) {
  const actual=(await pool.query(`SELECT * FROM ${table} ORDER BY id`)).rows;
  for(const expected of snapshot[table]) {
   const row=actual.find(r=>r.id===expected.id);assert(row);
   for(const [key,value] of Object.entries(expected)) {
    if(row[key] instanceof Date)assert.equal(row[key].getTime(),new Date(value).getTime());
    else assert.equal(row[key]===null?null:String(row[key]),value);
   }
  }
 }
 const {rows:users}=await pool.query('SELECT id,email,password_hash FROM users');
 for(const user of snapshot.users){const actual=users.find(u=>u.id===user.id);assert.equal(actual.email,user.email);assert(actual.password_hash===user.encrypted_password,'Imported password hash differs');}
 for(const d of snapshot.documents)assert.equal(sha256(await objectBytes(d.object_key)),d.sha256);
 const schedules=(await pool.query('SELECT definition FROM imported_schedules')).rows;
 assert.deepEqual(schedules.map(s=>s.definition),snapshot.schedules);
 check('Exact rows, ownership, password hashes, object keys/bytes, queue states and paused schedules match export');
 for(const port of [8001,8002]) {
  const child=spawn(process.execPath,['start.mjs'],{env:{...process.env,HOST:'127.0.0.1',PORT:String(port),WEB_CONCURRENCY:'2'},stdio:['ignore','ignore','inherit']});
  workers.push(child);await waitHealthy(port,child);
 }
 check('Two web servers with WEB_CONCURRENCY=2 listen on assigned PORT and return healthz');
 const home=await request('/');assert.equal(home.status,200);assert(home.data.includes('records, documents and reports'));
 const sessions=[];
 for(const user of snapshot.users) {
  const bad=await request('/api/login','POST',{email:user.email,password:'incorrect-password'});assert.equal(bad.status,401);
  const login=await request('/api/login','POST',{email:user.email,password});assert.equal(login.status,200);assert.equal(login.data.user.id,user.id);assert(login.cookie);sessions.push(login.cookie);
  const account=await request('/api/account','GET',undefined,login.cookie,8002);assert.equal(account.status,200);assert.equal(account.data.userId,user.id);assert.deepEqual(account.data.counts,{records:1,documents:1,reports:1});
 }
 check('Existing passwords work; wrong passwords fail; original UUIDs and sessions work on second server');
 // Apply the additive migration while both previous-release servers stay running.
 await migrate();await migrate();
 assert.equal((await pool.query('SELECT count(*)::int n FROM schema_migrations')).rows[0].n,2);
 assert.equal((await pool.query("SELECT count(*)::int n FROM records WHERE description=''")).rows[0].n,2);
 check('Ordered migrations run once; additive description preserves rows with old servers running');
 for(let i=0;i<snapshot.users.length;i++) {
  const user=snapshot.users[i],other=snapshot.users[1-i],session=sessions[i];
  const ownedRecord=snapshot.records.find(r=>r.user_id===user.id),foreignRecord=snapshot.records.find(r=>r.user_id===other.id),foreignDocument=snapshot.documents.find(r=>r.user_id===other.id);
  const records=await request('/api/records','GET',undefined,session);assert.equal(records.data.length,1);assert.equal(records.data[0].id,ownedRecord.id);
  assert.equal((await request(`/api/records/${foreignRecord.id}`,'PATCH',{title:'stolen'},session)).status,404);
  assert.equal((await request(`/api/records/${foreignRecord.id}`,'DELETE',undefined,session)).status,404);
  assert.equal((await request(`/api/documents/${foreignDocument.id}/download`,'GET',undefined,session)).status,404);
  assert.equal((await request(`/api/documents/${foreignDocument.id}`,'DELETE',undefined,session)).status,404);
  const foreignAttach=await request('/api/documents','POST',Buffer.from('no'),session,8001,{'x-file-name':'refused.txt','x-record-id':foreignRecord.id});assert.equal(foreignAttach.status,404);
  const jobs=await request('/api/reports','GET',undefined,session);assert.equal(jobs.data.length,1);assert.equal(jobs.data[0].user_id,user.id);
  const created=await request('/api/records','POST',{title:'temporary',user_id:other.id},session);assert.equal(created.status,201);assert.equal(created.data.user_id,user.id);
  assert.equal((await request(`/api/records/${created.data.id}`,'PATCH',{title:'updated'},session)).status,200);
  assert.equal((await request(`/api/records/${created.data.id}`,'DELETE',undefined,session)).status,200);
  const bytes=Buffer.from('new private upload\n');
  const uploaded=await request('/api/documents','POST',bytes,session,8001,{'x-file-name':'new.txt','x-record-id':ownedRecord.id});assert.equal(uploaded.status,201);assert.equal(uploaded.data.sha256,sha256(bytes));
  const link=await request(`/api/documents/${uploaded.data.id}/download`,'GET',undefined,session);assert.equal(link.status,200);
  assert.equal(sha256(Buffer.from(await (await fetch(link.data.signedUrl)).arrayBuffer())),sha256(bytes));
  assert.equal((await request(`/api/documents/${uploaded.data.id}`,'DELETE',undefined,session)).status,200);
 }
 check('Two-way exact-ID ownership refusals, forged ownership ignored, CRUD and private S3 upload/download equality');
 const anonymous=await request('/api/records');assert.equal(anonymous.status,401);
 const crossSite=await fetch('http://127.0.0.1:8001/api/records',{method:'POST',headers:{Origin:'https://attacker.example.com',Cookie:sessions[0],'Content-Type':'application/json'},body:JSON.stringify({title:'forbidden'})});assert.equal(crossSite.status,403);
 check('Anonymous access and cross-site mutation refused');
 // Hold a real row lock. Another worker must skip the locked oldest job.
 const interrupted=await pool.connect();interrupted.on('error',()=>{});await interrupted.query('BEGIN');
 const backendPid=(await interrupted.query('SELECT pg_backend_pid() AS pid')).rows[0].pid;
 const {rows:[locked]}=await interrupted.query("SELECT id FROM report_jobs WHERE status='PENDING' ORDER BY requested_at,id LIMIT 1 FOR UPDATE SKIP LOCKED");
 const completed=await runJob();assert.equal(completed.processed,1);assert.notEqual(completed.job.id,locked.id);
 await interrupted.query("UPDATE report_jobs SET status='RUNNING',started_at=now() WHERE id=$1",[locked.id]);
 await pool.query('SELECT pg_terminate_backend($1)',[backendPid]);interrupted.release(true);
 const raced=await Promise.all([runJob(),runJob()]);assert.equal(raced.reduce((n,r)=>n+r.processed,0),1);
 const jobs=(await pool.query('SELECT * FROM report_jobs')).rows;assert.equal(jobs.length,2);
 for(const job of jobs){assert.equal(job.status,'COMPLETED');assert.equal(job.output,'record_count=1\n');assert.equal(job.attempts,1);}
 check('SKIP LOCKED skips a held job; terminated worker rolls back; concurrent workers complete each pending job once with owner-only count');
 const queued=await request('/api/reports','POST',{},sessions[0]);assert.equal(queued.status,201);
 const ownRun=await request('/api/reports/run','POST',{},sessions[0]);assert.equal(ownRun.status,200);assert.equal(ownRun.data.job.id,queued.data.id);
 check('Customer-triggered queue and report execution operate through independent backend');
 assert.equal((await request('/api/logout','POST',{},sessions[0])).status,200);
 assert.equal((await request('/api/account','GET',undefined,sessions[0],8002)).status,401);
 check('Logout revokes the shared session on second web server immediately');
 const registered=await request('/api/register','POST',{email:'new@example.com',password});assert.equal(registered.status,200);
 assert.equal((await request('/api/records','GET',undefined,registered.cookie)).data.length,0);
 check('New customer registration uses bcrypt and starts with no owned data');
 result.passed=true;
} catch(error) {result.passed=false;result.error=error.message;throw error;}
finally {
 let shutdownError;
 for(const worker of workers) {
  let timer;
  try {
   worker.kill('SIGTERM');
   const [code]=await Promise.race([once(worker,'exit'),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Graceful shutdown timed out')),10000)})]);
   assert.equal(code,0);
  } catch(error) { shutdownError=error;worker.kill('SIGKILL'); }
  finally { clearTimeout(timer); }
 }
 if(shutdownError){result.passed=false;result.shutdown_error=shutdownError.message;process.exitCode=1;}
 else check('All web worker processes exit gracefully on SIGTERM');
 await pool.end();await save();console.log(JSON.stringify({passed:result.passed,checks:result.checks.length}));
}
