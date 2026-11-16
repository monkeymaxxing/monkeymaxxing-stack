import bcrypt from 'bcryptjs';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir,mkdir,writeFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {randomBytes,randomUUID,createHash} from 'node:crypto';
import {pool,migrate,transaction} from '../database.mjs';
import {importNetlify} from '../scripts/import_netlify.mjs';
import {deliverPasswordReset} from '../password_resets.mjs';
import {runReport,runSchedule} from '../jobs.mjs';
if(process.env.REHEARSAL_CONFIRM!=='disposable-destination')throw Error('Set REHEARSAL_CONFIRM=disposable-destination for this mutating test.');
const directory=resolve(process.env.NETLIFY_EXPORT_DIR);
const audit=JSON.parse(await readFile(join(directory,'table_audit.json'),'utf8'));
const users=audit.application_users;
const mailDirectory=process.env.PASSWORD_RESET_EMAIL_DIR;
const children=new Set();
const sha=value=>createHash('sha256').update(value).digest('hex');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(check){for(let i=0;i<100;i++){if(await check())return;await pause(100);}throw Error('Condition did not become ready.');}
function start(file,env={}){const child=spawn(process.execPath,[file],{env:{...process.env,...env},cwd:new URL('../',import.meta.url),stdio:['ignore','pipe','pipe']});children.add(child);child.stdout.resume();child.stderr.resume();return child;}
async function stop(child){if(child.exitCode!==null||child.signalCode!==null)return;const ended=once(child,'exit');child.kill('SIGTERM');await ended;children.delete(child);}
async function request(port,path,{method='GET',body,cookie,expected=200,origin}={}){
 const response=await fetch(`http://127.0.0.1:${port}${path}`,{method,headers:{...(body?{'Content-Type':'application/json'}:{}),...(cookie?{cookie}:{}),...(origin?{origin}:{})},body:body?JSON.stringify(body):undefined});
 if(Array.isArray(expected))assert.ok(expected.includes(response.status),`${method} ${path}`);else assert.equal(response.status,expected,`${method} ${path}`);assert.equal(response.headers.get('cache-control'),'no-store');return response;
}
async function json(port,path,options){return(await request(port,path,options)).json();}
function cookie(response){return response.headers.get('set-cookie').split(';')[0];}
async function drainMail(){for(let i=0;i<10;i++){if(!await deliverPasswordReset())return;}throw Error('Unexpected reset queue length.');}
async function requestToken(email,port=18001){
 await pool.query("UPDATE password_reset_requests SET requested_at=now()-interval '2 minutes' WHERE email=$1",[email]);
 const before=new Set(await readdir(mailDirectory));
 const response=await json(port,'/api/auth/password-reset/request',{method:'POST',body:{email},expected:202});assert.ok(response.message);
 await drainMail();
 const files=(await readdir(mailDirectory)).filter(x=>!before.has(x));assert.equal(files.length,1);
 const raw=await readFile(join(mailDirectory,files[0]),'utf8');const split=raw.search(/\r?\n\r?\n/);const headers=raw.slice(0,split);let text=raw.slice(split).trim();
 if(/content-transfer-encoding:\s*base64/i.test(headers))text=Buffer.from(text.replace(/\s/g,''),'base64').toString();
 else text=text.replace(/=\r?\n/g,'').replace(/=([0-9A-F]{2})/g,(_,v)=>String.fromCharCode(parseInt(v,16)));
 const url=new URL(text.match(/https?:\/\/[^\s]+/)[0]);assert.equal(url.origin,new URL(process.env.PUBLIC_APP_URL).origin);
 return new URLSearchParams(url.hash.slice(1)).get('token');
}
async function redeem(token,password,expected=200,port=18001){return request(port,'/api/auth/password-reset/complete',{method:'POST',body:{token,password,password_confirmation:password},expected});}
const passwords=new Map(users.map(u=>[u.id,'Reset-'+randomBytes(24).toString('base64url')]));
const cookies=new Map();
test('Netlify reset migration and destination portal', {timeout:180000},async t=>{
 try{
 await mkdir(mailDirectory,{recursive:true,mode:0o700});
 await t.test('import retains accounts, IDs, emails, owners, files, output, and schema history with no passwords or source sessions',async()=>{
  assert.equal((await pool.query('SELECT count(*)::int AS n FROM sessions')).rows[0].n,0);
  for(const u of users){const row=(await pool.query('SELECT * FROM users WHERE id=$1',[u.id])).rows[0];assert.equal(row.email,u.email);assert.equal(row.password_hash,null);assert.equal(row.is_admin,u.is_admin);const identity=(await pool.query('SELECT * FROM identities WHERE user_id=$1',[u.id])).rows[0];assert.equal(identity.subject,u.id);}
  for(const r of audit.records){const row=(await pool.query('SELECT * FROM records WHERE id=$1',[r.id])).rows[0];for(const k of ['owner_id','title','description'])assert.equal(row[k],r[k]);}
  for(const d of audit.documents){const row=(await pool.query('SELECT * FROM documents WHERE id=$1',[d.id])).rows[0];for(const k of ['owner_id','object_key','sha256','byte_length'])assert.equal(row[k],d[k]);assert.equal(row.filename,d.file_name);}
  for(const j of audit.report_jobs){const row=(await pool.query('SELECT * FROM jobs WHERE id=$1',[j.id])).rows[0];for(const k of ['owner_id','state','output','archived'])assert.equal(row[k],j[k]);}
  assert.equal((await pool.query('SELECT count(*)::int AS n FROM source_schema_migrations')).rows[0].n,2);
  assert.equal((await pool.query('SELECT count(*)::int AS n FROM scheduled_runs')).rows[0].n,audit.scheduled_runs.length);
  await migrate();await migrate();assert.equal((await importNetlify(directory)).already_imported,true);
 });
 const first=start('web.mjs',{PORT:'18001',WEB_CONCURRENCY:'2'});const second=start('web.mjs',{PORT:'18002',WEB_CONCURRENCY:'2'});
 for(const port of [18001,18002])await waitFor(async()=>{try{return(await fetch(`http://127.0.0.1:${port}/healthz`)).ok;}catch{return false;}});
 await t.test('reset links are private, generic, throttled, expiring, single-use, and preserve both users',async()=>{
  const resetPage=await(await request(18001,'/reset-password')).text();assert.ok(resetPage.includes('history.replaceState'));assert.ok(resetPage.includes('password_confirmation'));
  const home=await(await request(18001,'/')).text();assert.ok(home.includes('Customer portal'));
  const unknown=await json(18001,'/api/auth/password-reset/request',{method:'POST',body:{email:'missing@example.com'},expected:202});
  const known=await json(18001,'/api/auth/password-reset/request',{method:'POST',body:{email:users[0].email},expected:202});assert.deepEqual(known,unknown);
  const timestamp=(await pool.query('SELECT requested_at FROM password_reset_requests WHERE email=$1',[users[0].email])).rows[0].requested_at;
  await json(18002,'/api/auth/password-reset/request',{method:'POST',body:{email:users[0].email},expected:202});assert.equal((await pool.query('SELECT requested_at FROM password_reset_requests WHERE email=$1',[users[0].email])).rows[0].requested_at.toISOString(),timestamp.toISOString());await drainMail();
  await request(18001,'/api/auth/password-reset/request',{method:'POST',body:{email:users[0].email},origin:'https://attacker.example',expected:403});
  const worker=start('jobs_runner.mjs');
  const before=new Set(await readdir(mailDirectory));
  await pool.query("UPDATE password_reset_requests SET requested_at=now()-interval '2 minutes' WHERE email=$1",[users[0].email]);
  await json(18001,'/api/auth/password-reset/request',{method:'POST',body:{email:users[0].email},expected:202});
  await waitFor(async()=>(await readdir(mailDirectory)).some(x=>!before.has(x)));await stop(worker);
  for(const u of users){
   await request(18001,'/api/auth/register',{method:'POST',body:{email:u.email,password:passwords.get(u.id)},expected:503});
   await request(18001,'/api/auth/login',{method:'POST',body:{email:u.email,password:'Old-native-password-cannot-authenticate'},expected:401});
   let token=await requestToken(u.email);
   assert.equal(token.length,43);
   const stored=(await pool.query('SELECT * FROM password_reset_tokens WHERE token_hash=$1',[sha(token)])).rows[0];assert.equal(stored.owner_id,u.id);assert.notEqual(stored.token_hash,token);assert.ok(new Date(stored.expires_at)>new Date(Date.now()+29*60000));
   await redeem('x'.repeat(43),passwords.get(u.id),400);
   await pool.query("UPDATE password_reset_tokens SET expires_at=now()-interval '1 second' WHERE token_hash=$1",[sha(token)]);await redeem(token,passwords.get(u.id),400);
   token=await requestToken(u.email);const replacement=await requestToken(u.email);await redeem(token,passwords.get(u.id),400);
   await request(18001,'/api/auth/password-reset/complete',{method:'POST',body:{token:replacement,password:passwords.get(u.id),password_confirmation:'different'},expected:400});
   const results=await Promise.all([redeem(replacement,passwords.get(u.id),[200,400]),request(18002,'/api/auth/password-reset/complete',{method:'POST',body:{token:replacement,password:passwords.get(u.id),password_confirmation:passwords.get(u.id)},expected:[200,400]})]);assert.deepEqual(results.map(r=>r.status).sort(),[200,400]);
   await redeem(replacement,passwords.get(u.id),400);
   const login=await request(18001,'/api/auth/login',{method:'POST',body:{email:u.email,password:passwords.get(u.id)}});assert.equal((await login.json()).id,u.id);cookies.set(u.id,cookie(login));
   assert.equal((await json(18002,'/api/me',{cookie:cookies.get(u.id)})).id,u.id);
  }
 });
 await t.test('later reset revokes old sessions across processes and reimport never resets the new password',async()=>{
  const u=users[0];const oldCookie=cookies.get(u.id);const oldHash=(await pool.query('SELECT password_hash FROM users WHERE id=$1',[u.id])).rows[0].password_hash;
  const token=await requestToken(u.email);assert.equal((await json(18002,'/api/me',{cookie:oldCookie})).id,u.id);assert.equal((await pool.query('SELECT password_hash FROM users WHERE id=$1',[u.id])).rows[0].password_hash,oldHash);
  const newPassword='Second-reset-'+randomBytes(24).toString('base64url');await redeem(token,newPassword);passwords.set(u.id,newPassword);
  await request(18002,'/api/me',{cookie:oldCookie,expected:401});await request(18001,'/api/auth/login',{method:'POST',body:{email:u.email,password:'wrong'},expected:401});
  const hash=(await pool.query('SELECT password_hash FROM users WHERE id=$1',[u.id])).rows[0].password_hash;await importNetlify(directory);assert.equal((await pool.query('SELECT password_hash FROM users WHERE id=$1',[u.id])).rows[0].password_hash,hash);
  cookies.set(u.id,cookie(await request(18001,'/api/auth/login',{method:'POST',body:{email:u.email,password:newPassword}})));
 });
 await t.test('a login racing password replacement cannot create a session from the superseded password',async()=>{
  const u=users[0];const previousPassword=passwords.get(u.id);const nextPassword='Racing-reset-'+randomBytes(24).toString('base64url');
  const reset=await pool.connect();let committed=false;
  try{
   await reset.query('BEGIN');await reset.query('SELECT id FROM users WHERE id=$1 FOR UPDATE',[u.id]);
   const login=fetch('http://127.0.0.1:18001/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:u.email,password:previousPassword})});
   await waitFor(async()=>(await pool.query("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND (query LIKE 'INSERT INTO sessions%' OR query LIKE 'SELECT id,email,is_admin,password_hash FROM users%')) AS blocked")).rows[0].blocked);
   await reset.query('UPDATE users SET password_hash=$2 WHERE id=$1',[u.id,await bcrypt.hash(nextPassword,12)]);
   await reset.query('UPDATE sessions SET revoked_at=now() WHERE owner_id=$1 AND revoked_at IS NULL',[u.id]);
   await reset.query('COMMIT');committed=true;
   assert.equal((await login).status,401);
  }finally{if(!committed)await reset.query('ROLLBACK');reset.release();}
  passwords.set(u.id,nextPassword);cookies.set(u.id,cookie(await request(18002,'/api/auth/login',{method:'POST',body:{email:u.email,password:nextPassword}})));
 });
 await t.test('test-data seed refuses production and reruns preserve migrated accounts and new password hashes',async()=>{
  const before=(await pool.query('SELECT id,email,password_hash FROM users ORDER BY id')).rows;
  async function seed(appEnv){const child=start('seed_test_data.mjs',{APP_ENV:appEnv});const [code]=await once(child,'exit');children.delete(child);return code;}
  assert.equal(await seed('production'),1);assert.equal(await seed('staging'),0);assert.equal(await seed('staging'),0);
  assert.deepEqual((await pool.query('SELECT id,email,password_hash FROM users ORDER BY id')).rows,before);
 });
 await t.test('owned CRUD, private bytes, cross-owner refusals, report ownership, and logout work',async()=>{
  const admin=users.find(u=>u.is_admin);await request(18001,'/api/operations',{method:'PUT',cookie:cookies.get(admin.id),body:{maintenance_enabled:false}});
  for(let i=0;i<users.length;i++){
   const u=users[i],other=users[1-i],session=cookies.get(u.id);
   await request(18001,'/api/auth/register',{method:'POST',body:{email:u.email,password:'Do-not-overwrite-an-existing-user'},expected:409});
   assert.deepEqual((await json(18001,'/api/records',{cookie:session})).map(r=>r.id).sort(),audit.records.filter(r=>r.owner_id===u.id).map(r=>r.id).sort());
   const foreign=audit.records.find(r=>r.owner_id===other.id);for(const method of ['GET','PATCH','DELETE'])await request(18002,'/api/records/'+foreign.id,{cookie:session,method,body:method==='PATCH'?{title:'forbidden'}:undefined,expected:404});
   const foreignDoc=audit.documents.find(d=>d.owner_id===other.id);await request(18001,'/api/documents/'+foreignDoc.id+'/download',{cookie:session,expected:404});
   const foreignJob=audit.report_jobs.find(j=>j.owner_id===other.id);await request(18001,'/api/jobs/'+foreignJob.id,{cookie:session,expected:404});
   for(const d of audit.documents.filter(d=>d.owner_id===u.id)){const bytes=Buffer.from(await(await request(18002,'/api/documents/'+d.id+'/download',{cookie:session})).arrayBuffer());assert.equal(bytes.length,d.byte_length);assert.equal(sha(bytes),d.sha256);}
   const temp=await json(18001,'/api/records',{cookie:session,method:'POST',body:{title:'temporary'},expected:201});assert.equal(temp.description,'');await request(18001,'/api/records/'+temp.id,{cookie:session,method:'PATCH',body:{title:'updated',description:'updated'}});await request(18001,'/api/records/'+temp.id,{cookie:session,method:'DELETE'});
   const bytes=Buffer.from('Owned upload\n');const uploaded=await json(18001,'/api/documents',{cookie:session,method:'POST',body:{filename:'proof.txt',content_base64:bytes.toString('base64')},expected:201});assert.deepEqual(Buffer.from(await(await request(18002,'/api/documents/'+uploaded.id+'/download',{cookie:session})).arrayBuffer()),bytes);
   const queued=await json(18001,'/api/jobs',{cookie:session,method:'POST',body:{},expected:201});assert.equal(queued.owner_id,u.id);
   if(!u.is_admin)await request(18001,'/api/operations',{cookie:session,method:'PUT',body:{worker_paused:false},expected:403});
  }
 });
 await t.test('concurrent workers complete reports once, rollback retains work, and scheduled archival deduplicates',async()=>{
  await pool.query('UPDATE controls SET worker_paused=false,scheduler_paused=false WHERE id=1');
  const pending=(await pool.query("SELECT id FROM jobs WHERE state='PENDING'")).rows;
  const claimed=[];for(let i=0;i<10;i++){const ids=await Promise.all([runReport(),runReport()]);claimed.push(...ids.filter(Boolean));if(ids.every(x=>!x))break;}
  assert.equal(new Set(claimed).size,claimed.length);assert.deepEqual(claimed.sort(),pending.map(j=>j.id).sort());
  for(const j of (await pool.query('SELECT * FROM jobs')).rows)assert.equal(j.output,'record_count=1\n');
  const id=randomUUID();await pool.query('INSERT INTO jobs(id,owner_id) VALUES($1,$2)',[id,users[0].id]);
  const interrupted=spawn(process.execPath,['--input-type=module','-e',`import {pool} from './database.mjs';const c=await pool.connect();await c.query('BEGIN');await c.query("UPDATE jobs SET state='RUNNING' WHERE id=$1",[process.env.TEST_JOB_ID]);console.log('LOCKED');setInterval(()=>{},1000);`],{cwd:new URL('../',import.meta.url),env:{...process.env,TEST_JOB_ID:id},stdio:['ignore','pipe','pipe']});children.add(interrupted);interrupted.stderr.resume();
  await once(interrupted.stdout,'data');assert.equal(await runReport(),null);const ended=once(interrupted,'exit');interrupted.kill('SIGKILL');await ended;children.delete(interrupted);assert.equal(await runReport(),id);
  await pool.query("UPDATE jobs SET completed_at=now()-interval '31 days' WHERE id=$1",[id]);
  await pool.query("UPDATE schedules SET next_run_at=now()-interval '1 second' WHERE id='archive_old_reports'");const results=await Promise.all([runSchedule(),runSchedule()]);assert.equal(results.filter(Boolean).length,1);assert.equal(await runSchedule(),null);assert.equal((await pool.query('SELECT archived FROM jobs WHERE id=$1',[id])).rows[0].archived,true);
 });
 await t.test('logout revokes shared cookies and web processes stop cleanly',async()=>{
  for(const u of users){const c=cookies.get(u.id);await request(18001,'/api/auth/logout',{method:'POST',cookie:c,body:{}});await request(18002,'/api/me',{cookie:c,expected:401});}
  await stop(first);await stop(second);
 });
 }finally{for(const child of children)await stop(child);await pool.end();}
});
