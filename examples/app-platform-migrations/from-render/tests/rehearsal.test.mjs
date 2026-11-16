import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {createHash,randomUUID} from 'node:crypto';
import bcrypt from 'bcryptjs';
import {pool,migrate} from '../database.mjs';
import {runReport,runSchedule} from '../jobs.mjs';
if(process.env.REHEARSAL_CONFIRM!=='disposable-destination')throw Error('Set REHEARSAL_CONFIRM=disposable-destination only for an isolated restored database and bucket');
const source=JSON.parse(await readFile(resolve(process.env.EXPORT_DIR,'tables.json'),'utf8'));
const password=process.env.FIXTURE_PASSWORD;assert.ok(password,'FIXTURE_PASSWORD is required');
const fingerprint=rows=>createHash('sha256').update(JSON.stringify(rows.map(r=>JSON.stringify(JSON.parse(JSON.stringify(r)))).sort())).digest('hex');
const children=new Set(),root=new URL('../',import.meta.url),delay=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(description,check){const end=Date.now()+20000;while(Date.now()<end){if(await check())return;await delay(100);}throw Error('Timed out: '+description);}
function start(file,args=[],env={}){const c=spawn(process.execPath,[file,...args],{cwd:root,env:{...process.env,...env},stdio:['ignore','pipe','pipe']});c.stdout.resume();c.stderr.resume();children.add(c);return c;}
async function stop(c,signal='SIGTERM'){if(c.exitCode!==null||c.signalCode!==null)return;const done=once(c,'exit');c.kill(signal);await done;children.delete(c);}
async function request(port,path,{method='GET',body,cookie,expected=200}={}){const r=await fetch(`http://127.0.0.1:${port}/api${path}`,{method,headers:{...(cookie?{cookie}:{}),...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});assert.equal(r.status,expected,method+' '+path);assert.equal(r.headers.get('cache-control'),'no-store');return r;}
const ports=(process.env.TEST_WEB_PORTS||'18081,18082').split(',').map(Number);
test('Render export restores into PostgreSQL 17 and S3 with retained identities and owned behavior',{timeout:120000},async t=>{
try{
 await t.test('all restored rows equal source, including password hashes, sessions, schedules and migration ledger',async()=>{
  assert.match((await pool.query('SHOW server_version')).rows[0].server_version,/^17\./);
  for(const [table,rows] of Object.entries(source)){assert.match(table,/^[a-z_]+$/);assert.equal(fingerprint((await pool.query(`SELECT * FROM "${table}"`)).rows),fingerprint(rows),'restored table '+table);}
  for(const user of source.users)assert.ok(await bcrypt.compare(password,user.password_hash),'retained password verifier');
  await migrate();await migrate();assert.equal(fingerprint((await pool.query('SELECT * FROM schema_migrations')).rows),fingerprint(source.schema_migrations));
 });
 await pool.query('UPDATE controls SET maintenance=false,worker_paused=true,scheduler_paused=true WHERE id=1');
 const servers=ports.map(PORT=>start('app.mjs',['web'],{PORT:String(PORT),WEB_CONCURRENCY:'2'}));
 for(const port of ports)await wait('web ready',async()=>{try{return(await fetch(`http://127.0.0.1:${port}/healthz`)).ok;}catch{return false;}});
 await t.test('test-data seed reruns preserve existing passwords and do not duplicate fixtures',async()=>{
  for(let attempt=0;attempt<2;attempt++){const seed=start('seed_test_data.mjs',[],{APP_ENV:'staging',APP_URL:`http://127.0.0.1:${ports[0]}`});const [code]=await once(seed,'exit');children.delete(seed);assert.equal(code,0,'test-data seed exit status');}
  for(const table of ['users','identities','records','documents','jobs'])assert.equal(fingerprint((await pool.query(`SELECT * FROM "${table}"`)).rows),fingerprint(source[table]),'idempotent test data '+table);
 });
 const cookies={};
 await t.test('existing passwords and stable user IDs work across separate web processes',async()=>{
  for(const user of source.users){const r=await request(ports[0],'/auth/login',{method:'POST',body:{email:user.email,password}});cookies[user.id]=r.headers.get('set-cookie').split(';')[0];assert.equal((await r.json()).id,user.id);assert.equal((await(await request(ports[1],'/me',{cookie:cookies[user.id]})).json()).id,user.id);}
  await request(ports[0],'/auth/login',{method:'POST',body:{email:source.users[0].email,password:password+'x'},expected:401});
 });
 await t.test('owned records, description values, private file hashes and cross-owner refusals survive',async()=>{
  for(const user of source.users){const cookie=cookies[user.id];
   const records=await(await request(ports[1],'/records',{cookie})).json();assert.equal(records.length,1);assert.equal(records[0].description,source.records.find(r=>r.owner_id===user.id).description);
   for(const row of source.records.filter(r=>r.owner_id!==user.id))for(const method of ['GET','PATCH','DELETE'])await request(ports[0],'/records/'+row.id,{method,cookie,...(method==='PATCH'?{body:{title:'blocked'}}:{}),expected:404});
   for(const doc of source.documents){const response=await request(ports[1],'/documents/'+doc.id+'/download',{cookie,expected:doc.owner_id===user.id?200:404});if(doc.owner_id===user.id){const bytes=Buffer.from(await response.arrayBuffer());assert.equal(bytes.length,doc.byte_length);assert.equal(createHash('sha256').update(bytes).digest('hex'),doc.sha256);}}
   for(const job of source.jobs.filter(j=>j.owner_id!==user.id))await request(ports[0],'/jobs/'+job.id,{cookie,expected:404});
  }
  const member=source.users.find(u=>!u.is_admin);await request(ports[0],'/operations',{cookie:cookies[member.id],method:'PUT',body:{worker_paused:false},expected:403});
 });
 await t.test('destination CRUD, new S3 upload, registration, origin refusal and logout revocation work',async()=>{
  const cookie=cookies[source.users[0].id];const row=await(await request(ports[0],'/records',{cookie,method:'POST',body:{title:'Destination temporary'},expected:201})).json();assert.equal(row.description,'');
  const edited=await(await request(ports[1],'/records/'+row.id,{cookie,method:'PATCH',body:{title:'Updated',description:'Destination'}})).json();assert.equal(edited.description,'Destination');await request(ports[0],'/records/'+row.id,{cookie,method:'DELETE'});
  const bytes=Buffer.from('Destination-only private bytes\n');const doc=await(await request(ports[0],'/documents',{cookie,method:'POST',body:{filename:'destination.txt',content_base64:bytes.toString('base64')},expected:201})).json();assert.deepEqual(Buffer.from(await(await request(ports[1],'/documents/'+doc.id+'/download',{cookie})).arrayBuffer()),bytes);
  await request(ports[0],'/documents',{cookie,method:'POST',body:{filename:'bad.txt',content_base64:'???'},expected:400});
  const bad=await fetch(`http://127.0.0.1:${ports[0]}/api/records`,{method:'POST',headers:{cookie,Origin:'https://other.example.com','Content-Type':'application/json'},body:JSON.stringify({title:'blocked'})});assert.equal(bad.status,403);
  const creds={email:'claire@example.com',password};const registered=await request(ports[0],'/auth/register',{method:'POST',body:creds,expected:201});const fresh=registered.headers.get('set-cookie').split(';')[0];await request(ports[1],'/me',{cookie:fresh});await request(ports[0],'/auth/register',{method:'POST',body:creds,expected:409});await request(ports[0],'/auth/logout',{method:'POST',body:{},cookie:fresh});await request(ports[1],'/me',{cookie:fresh,expected:401});
 });
 await t.test('concurrent and interrupted claims preserve queued jobs and atomic owner-only output',async()=>{
  await pool.query('UPDATE controls SET worker_paused=false WHERE id=1');const pending=source.jobs.filter(j=>j.state==='PENDING');assert.equal(pending.length,2);
  const code=`import {pool} from './database.mjs';const c=await pool.connect();await c.query('BEGIN');await c.query('SELECT id FROM jobs WHERE id=$1 FOR UPDATE',['${pending[0].id}']);console.log('LOCKED');await new Promise(()=>{});`;
  const locked=spawn(process.execPath,['--input-type=module','-e',code],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});children.add(locked);locked.stderr.resume();await new Promise((ok,bad)=>{locked.stdout.once('data',ok);locked.once('exit',()=>bad(Error('Lock holder exited early')));});
  assert.equal(await runReport(),pending[1].id);assert.equal(await runReport(),null);await stop(locked,'SIGKILL');assert.equal(await runReport(),pending[0].id);
  for(const id of pending.map(j=>j.id)){const j=(await pool.query('SELECT state,output FROM jobs WHERE id=$1',[id])).rows[0];assert.equal(j.state,'COMPLETED');assert.equal(j.output,'record_count=1\n');}
  const ids=[randomUUID(),randomUUID()];for(const id of ids)await pool.query('INSERT INTO jobs(id,owner_id) VALUES($1,$2)',[id,source.users[1].id]);const claims=await Promise.all([runReport(),runReport(),runReport()]);assert.deepEqual(claims.filter(Boolean).sort(),ids.sort());
  const id=randomUUID();await pool.query('INSERT INTO jobs(id,owner_id) VALUES($1,$2)',[id,source.users[1].id]);const jobs=start('app.mjs',['jobs']);await wait('real jobs command',async()=>(await pool.query('SELECT state FROM jobs WHERE id=$1',[id])).rows[0].state==='COMPLETED');await stop(jobs);
 });
 await t.test('schedule state is preserved and a new due occurrence executes once',async()=>{
  await pool.query('UPDATE controls SET scheduler_paused=false WHERE id=1');
  // Move this disposable copy's occurrence to yesterday, then claim today's occurrence twice.
  await pool.query("UPDATE scheduled_runs SET occurrence_date=occurrence_date-1 WHERE schedule_id='archive_old_reports'");
  const before=(await pool.query('SELECT count(*)::int n FROM scheduled_runs')).rows[0].n;const outcomes=await Promise.all([runSchedule(),runSchedule()]);assert.equal(outcomes.filter(Boolean).length,1);assert.equal((await pool.query('SELECT count(*)::int n FROM scheduled_runs')).rows[0].n,before+1);
 });
 await t.test('sessions survive app restart and logout revokes across web processes',async()=>{
  await stop(servers[0]);const replacement=start('app.mjs',['web'],{PORT:String(ports[0]),WEB_CONCURRENCY:'2'});await wait('replacement web',async()=>{try{return(await fetch(`http://127.0.0.1:${ports[0]}/healthz`)).ok;}catch{return false;}});
  for(const cookie of Object.values(cookies)){await request(ports[0],'/me',{cookie});await request(ports[0],'/auth/logout',{cookie,method:'POST',body:{}});await request(ports[1],'/me',{cookie,expected:401});}await stop(replacement);
 });
}finally{for(const c of children)await stop(c);await pool.end();}
});
