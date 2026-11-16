// Run only against a disposable restored copy. This check creates and changes data.
import assert from 'node:assert/strict';
import {readFile,writeFile,open} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {setTimeout as wait} from 'node:timers/promises';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {pool,query,migrate} from '../app/database.mjs';
import {runJob} from '../app/jobs.mjs';
import {runSchedule} from '../app/cron.mjs';
import {databaseChecks,snapshotDatabase,sha256} from '../data-transfer.mjs';

assert.equal(process.env.ALLOW_DISPOSABLE_REHEARSAL,'true','Set ALLOW_DISPOSABLE_REHEARSAL=true for a disposable copy only');
assert.equal(process.env.NODE_ENV,'test','Rehearsal requires NODE_ENV=test');
const password=(await readFile(process.env.FIXTURE_PASSWORD_FILE,'utf8')).trim();
const exportDir=process.env.EXPORT_DIR;
const manifest=JSON.parse(await readFile(exportDir+'/manifest.json','utf8'));
const snapshot=JSON.parse(await readFile(exportDir+'/snapshot.json','utf8'));
const checks=[];const children=[];const logs=[];
const firstPort=Number(process.env.REHEARSAL_FIRST_PORT||18081);
const origins=[`http://127.0.0.1:${firstPort}`,`http://127.0.0.1:${firstPort+1}`];
async function request(server,path,{method='GET',body,cookie,raw=false,status=200}={}){
 const response=await fetch(origins[server]+path,{method,headers:{'X-Portal-Request':'true',...(cookie?{Cookie:cookie}:{}),...(body!==undefined?{'Content-Type':raw?'application/octet-stream':'application/json'}:{})},body:body===undefined?undefined:raw?body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
 assert.equal(response.status,status,`${method} ${path} returned ${response.status}, expected ${status}`);
 return response;
}
async function startWeb(index){
 const log=await open(`${exportDir}/web-${index}.log`,'w',0o600);logs.push(log);
 const child=spawn(process.execPath,['server.mjs'],{cwd:fileURLToPath(new URL('../app/',import.meta.url)),env:{...process.env,PORT:String(firstPort+index),WEB_CONCURRENCY:'2'},stdio:['ignore',log.fd,log.fd]});children.push(child);
 const deadline=Date.now()+30000;
 while(Date.now()<deadline){
  if(child.exitCode!==null)throw Error('Web process exited before readiness');
  try{const r=await fetch(origins[index]+'/healthz',{signal:AbortSignal.timeout(1000)});if(r.ok)return;}catch{}
  await wait(100);
 }
 throw Error('Web process did not become ready within 30 seconds');
}
async function login(index,email){
 const response=await request(index,'/api/login',{method:'POST',body:{email,password}});
 const cookie=response.headers.get('set-cookie').split(';')[0];
 assert.match(response.headers.get('set-cookie'),/HttpOnly/i);
 assert.match(response.headers.get('set-cookie'),/SameSite=Strict/i);
 return {cookie,user:await response.json()};
}
try{
 assert.deepEqual(databaseChecks(await snapshotDatabase(pool)),manifest.database);checks.push('exact restore: every row, password hash, UUID, owner, job output, receipt and migration checksum');
 await migrate();await migrate();
 assert.deepEqual(databaseChecks(await snapshotDatabase(pool)),manifest.database);checks.push('ordered migrations are unchanged and idempotent after restore');
 assert.equal((await query('SELECT current_setting(\'server_version\') AS version')).rows[0].version.split('.')[0],'17');
 await Promise.all([startWeb(0),startWeb(1)]);
 const users=[];
 for(const email of ['barbara@example.com','michael@example.com']){
  const account=await login(0,email);users.push(account);
  const old=snapshot.users.find(u=>u.email===email);assert.equal(account.user.id,old.id);
  const me=await(await request(1,'/api/me',{cookie:account.cookie})).json();assert.equal(me.id,old.id);
  const processes=new Set();for(let i=0;i<16;i++)processes.add((await(await request(0,'/api/me',{cookie:account.cookie})).json()).process_id);
  assert.equal(processes.size,2,'WEB_CONCURRENCY=2 must serve with two processes');
  const records=await(await request(1,'/api/records',{cookie:account.cookie})).json();assert.equal(records.length,1);assert.equal(records[0].id,snapshot.records.find(r=>r.owner_id===old.id).id);
  const documents=await(await request(1,'/api/documents',{cookie:account.cookie})).json();assert.equal(documents.length,1);
  const bytes=Buffer.from(await(await request(1,`/api/documents/${documents[0].id}/download`,{cookie:account.cookie})).arrayBuffer());assert.equal(sha256(bytes),documents[0].sha256);
 }
 checks.push('existing passwords log in with preserved account IDs; sessions cross two web servers and two processes each');
 const [barbara,michael]=users;
 const foreignRecord=snapshot.records.find(r=>r.owner_id===michael.user.id);
 const foreignDocument=snapshot.documents.find(r=>r.owner_id===michael.user.id);
 const foreignJob=snapshot.jobs.find(r=>r.owner_id===michael.user.id);
 for(const options of [
  {path:`/api/records/${foreignRecord.id}`},
  {path:`/api/records/${foreignRecord.id}`,method:'PUT',body:{title:'forbidden'}},
  {path:`/api/records/${foreignRecord.id}`,method:'DELETE'},
  {path:`/api/documents/${foreignDocument.id}/download`},
  {path:`/api/jobs/${foreignJob.id}`},
  {path:`/api/jobs/${foreignJob.id}/report`},
 ]){const {path,...rest}=options;await request(1,path,{...rest,cookie:barbara.cookie,status:404});}
 await request(1,'/api/worker',{method:'PUT',body:{worker_paused:false},cookie:michael.cookie,status:403});
 checks.push('ownership blocks foreign records, mutations, files, jobs and reports; worker control is admin-only');
 const created=await(await request(0,'/api/records',{method:'POST',body:{title:'temporary record',description:'temporary description'},cookie:barbara.cookie,status:201})).json();
 const edited=await(await request(1,`/api/records/${created.id}`,{method:'PUT',body:{title:'updated record',description:'updated description'},cookie:barbara.cookie})).json();assert.equal(edited.description,'updated description');
 await request(1,`/api/records/${created.id}`,{method:'DELETE',cookie:barbara.cookie,status:204});
 const uploadBytes=Buffer.from('Destination-only document\n');
 const uploaded=await(await request(0,'/api/documents?file_name=destination.txt',{method:'POST',body:uploadBytes,raw:true,cookie:barbara.cookie,status:201})).json();
 const downloaded=Buffer.from(await(await request(1,`/api/documents/${uploaded.id}/download`,{cookie:barbara.cookie})).arrayBuffer());assert.deepEqual(downloaded,uploadBytes);
 checks.push('CRUD and new destination uploads/downloads preserve bytes');
 await request(0,'/api/logout',{method:'POST',body:{},cookie:barbara.cookie,status:204});
 await request(1,'/api/me',{cookie:barbara.cookie,status:401});checks.push('logout revokes a session across web servers');
 const pending=snapshot.jobs.filter(j=>j.state==='PENDING');assert.equal(pending.length,2);
 assert.equal(await runJob(),null);assert.deepEqual(await runSchedule(),{paused:true});
 const beforeCompleted=snapshot.jobs.filter(j=>j.state==='COMPLETED');
 await query('UPDATE controls SET worker_paused=false WHERE id=1');
 // Hold the oldest row on a real independent connection while two workers compete.
 const held=await pool.connect();let locked;
 try{
  await held.query('BEGIN');locked=(await held.query("SELECT id FROM jobs WHERE state='PENDING' ORDER BY created_at FOR UPDATE LIMIT 1")).rows[0].id;
  await held.query("UPDATE jobs SET state='COMPLETED',output='uncommitted' WHERE id=$1",[locked]);
  const completed=await Promise.all([runJob(),runJob()]);
  assert.equal(completed.filter(Boolean).length,1);assert.ok(!completed.includes(locked));
 }finally{await held.connection.stream.destroy();held.release(true);}
 // The severed connection must roll back without an application recovery flag.
 let recovered;const deadline=Date.now()+10000;
 while(Date.now()<deadline){recovered=await runJob();if(recovered)break;await wait(50);}
 assert.equal(recovered,locked);assert.equal(await runJob(),null);
 for(const old of beforeCompleted){const row=(await query('SELECT * FROM jobs WHERE id=$1',[old.id])).rows[0];assert.equal(row.output,old.output);}
 for(const old of pending){const row=(await query('SELECT * FROM jobs WHERE id=$1',[old.id])).rows[0];assert.equal(row.output,'record_count=1\n');assert.equal(row.state,'COMPLETED');}
 checks.push('paused imported queue stays paused; SKIP LOCKED skips a held row; interrupted transaction is completed once; old outputs remain');
 const oldReport=randomUUID();await query("INSERT INTO jobs(id,owner_id,state,output,completed_at) VALUES($1,$2,'COMPLETED','record_count=1\n',now()-interval '31 days')",[oldReport,barbara.user.id]);
 const future=new Date(Date.now()+300000);
 const schedules=await Promise.all([runSchedule(future),runSchedule(future)]);
 assert.equal(schedules.filter(r=>r.duplicate).length,1);assert.equal(schedules.find(r=>!r.duplicate).archived_reports,1);
 assert.ok((await query('SELECT archived_at FROM jobs WHERE id=$1',[oldReport])).rows[0].archived_at);
 checks.push('two schedulers commit one five-minute UTC receipt and archive only an eligible report');
 // Run the actual long-lived jobs command, including its schedule loop and shutdown.
 const workerLog=await open(`${exportDir}/worker.log`,'w',0o600);logs.push(workerLog);
 const worker=spawn(process.execPath,['jobs.mjs'],{cwd:fileURLToPath(new URL('../app/',import.meta.url)),env:process.env,stdio:['ignore',workerLog.fd,workerLog.fd]});children.push(worker);
 const actualJob=await(await request(1,'/api/jobs',{method:'POST',body:{},cookie:michael.cookie,status:201})).json();
 let result;const workerDeadline=Date.now()+15000;
 while(Date.now()<workerDeadline){result=(await query('SELECT * FROM jobs WHERE id=$1',[actualJob.id])).rows[0];if(result.state==='COMPLETED')break;await wait(100);}
 assert.equal(result.output,'record_count=1\n');
 checks.push('actual Stack jobs process completes HTTP-enqueued work');
 // Registration uses invented credentials only.
 const freshEmail=`rehearsal-${randomUUID()}@example.com`;
 const registered=await request(1,'/api/register',{method:'POST',body:{email:freshEmail,password},status:201});assert.equal((await registered.json()).is_admin,false);
 await request(0,'/api/login',{method:'POST',body:{email:freshEmail,password:'incorrect-password-123'},status:401});
 checks.push('new account registration and wrong-password refusal');
 for(const child of children){child.kill('SIGTERM');}
 for(const child of children){if(child.exitCode===null)await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Graceful shutdown exceeded 15 seconds')),15000);child.once('exit',code=>{clearTimeout(timer);assert.equal(code,0);resolve();});});}
 checks.push('web clusters and jobs exit cleanly on SIGTERM');
 await writeFile(exportDir+'/rehearsal-result.json',JSON.stringify({checked_at:new Date().toISOString(),node:process.version,postgres:(await query('SHOW server_version')).rows[0].server_version,source_users:snapshot.users.length,source_pending_jobs:pending.length,source_completed_jobs:beforeCompleted.length,checks,limits:['No live Stack deployment, PgBouncer, R2 authorization, database primary switch or production cutover in this rehearsal.','Local HTTP uses NODE_ENV=test; production must use HTTPS and NODE_ENV=production.']},null,2)+'\n',{mode:0o600});
 console.log('REHEARSAL_PASS',checks.length,'behavior checks');
}catch(error){console.error('REHEARSAL_FAILED',error.message);process.exitCode=1;}
finally{
 for(const child of children){if(child.exitCode===null)child.kill('SIGTERM');}
 await pool.end();for(const log of logs)await log.close();
}
