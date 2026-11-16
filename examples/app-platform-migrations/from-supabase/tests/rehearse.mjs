import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import bcrypt from 'bcryptjs';
import S3rver from 's3rver';
import {pool,storage,bucket,ensureBucket,sha256,runJob,scheduledTask,objectBytes} from '../backend.mjs';
import {migrate,importSnapshot,validateSnapshot} from '../operations.mjs';
const result={checks:[],limits:['Single PostgreSQL server; no promotion/reconnection proof','S3rver proves S3 protocol and bytes; no live R2 policy proof','No complete Stack deployment or production cutover']};
const ok=(name)=>{result.checks.push(name);console.log('PASS '+name);};
const snapshotFile=process.env.EXPORT_SNAPSHOT_FILE,objectDir=process.env.EXPORT_OBJECT_DIR,password=await readFile(process.env.FIXTURE_PASSWORD_FILE,'utf8');
const snapshot=JSON.parse(await readFile(snapshotFile,'utf8'));
const a=Number(process.env.PORT||8001),b=a+1,origin=process.env.PUBLIC_ORIGIN;
const children=[];let s3;
async function http(port,path,method='GET',body,session,headers={}){const r=await fetch(`http://127.0.0.1:${port}/api/${path}`,{method,headers:{Origin:origin,...(session?{Cookie:session}:{}),...(body instanceof Buffer?{'Content-Type':'application/octet-stream'}:{'Content-Type':'application/json'}),...headers},body:body===undefined?undefined:body instanceof Buffer?body:JSON.stringify(body)});const data=r.headers.get('content-type')?.includes('json')?await r.json():Buffer.from(await r.arrayBuffer());return {status:r.status,data,cookie:r.headers.get('set-cookie')?.split(';')[0]};}
const signIn=async(port,email,p=password)=>{const r=await http(port,'login','POST',{email,password:p});assert.equal(r.status,200);return r;};
try{
 await mkdir(process.env.REHEARSAL_S3_DIR,{recursive:true,mode:0o700});
 const endpoint=new URL(process.env.S3_ENDPOINT);s3=new S3rver({port:Number(endpoint.port),address:endpoint.hostname,silent:true,directory:process.env.REHEARSAL_S3_DIR});await s3.run();await ensureBucket();
 await migrate(1);assert.equal((await pool.query("select count(*) from information_schema.columns where table_name='records' and column_name='description'")).rows[0].count,'0');ok('Initial migration alone creates working schema');
 const dummy=randomUUID();await pool.query('insert into users(id,email,password_hash,email_confirmed_at) values($1,$2,$3,now())',[dummy,'rollout@example.com',await bcrypt.hash(password,12)]);
 for(const port of [a,b]){const child=spawn(process.execPath,['web.mjs'],{cwd:new URL('../',import.meta.url),env:{...process.env,PORT:String(port),HOST:'127.0.0.1',WEB_CONCURRENCY:'2'},stdio:['ignore','pipe','pipe']});children.push(child);child.stdout.on('data',()=>{});child.stderr.on('data',d=>process.stderr.write(d));
  await new Promise((resolve,reject)=>{const start=Date.now();const tick=async()=>{try{const r=await fetch(`http://127.0.0.1:${port}/healthz`);if(r.ok)return resolve();}catch{}if(Date.now()-start>15000)return reject(Error('Web process did not become healthy'));setTimeout(tick,100);};tick();child.once('exit',code=>reject(Error('Web exited '+code)));});}
 for(const child of children){const workers=(await readFile(`/proc/${child.pid}/task/${child.pid}/children`,'utf8')).trim().split(/\s+/);assert.equal(workers.length,2);}ok('WEB_CONCURRENCY=2 starts two worker processes per web instance on the same PORT');
 const oldSession=(await signIn(a,'rollout@example.com')).cookie;const oldRecord=await http(a,'records','POST',{title:'Before additive migration'},oldSession);assert.equal(oldRecord.status,201);
 await migrate();await migrate();assert.equal((await http(b,'records/'+oldRecord.data.id,'GET',undefined,oldSession)).data.description,'');
 assert.equal((await http(a,'records','POST',{title:'After additive migration'},oldSession)).status,201);await pool.query('delete from records where owner_id=$1',[dummy]);await pool.query('delete from sessions where user_id=$1',[dummy]);await pool.query('delete from users where id=$1',[dummy]);
 assert.equal((await pool.query('select count(*) from schema_migrations')).rows[0].count,'2');ok('Additive migration preserves rows and existing sessions with two web processes running; rerun applies once');
 validateSnapshot(snapshot);
 for(const mutation of [s=>{s.mfa_factors=[{id:'unsupported'}];},s=>{s.users[0].encrypted_password='';},s=>{s.users[0].raw_app_meta_data.providers=['github'];},s=>{s.cron_jobs[0].active=true;},s=>{s.documents[0].object_key='../unsafe';}]){const s=structuredClone(snapshot);mutation(s);assert.throws(()=>validateSnapshot(s));}ok('Unsupported identity states, live source cron and unsafe file keys are refused');
 await importSnapshot(snapshotFile,objectDir);
 await assert.rejects(()=>importSnapshot(snapshotFile,objectDir),/empty destination/);ok('Verified export imports once; rerun refuses a populated destination');
 for(const u of snapshot.users){const saved=(await pool.query('select * from users where id=$1',[u.id])).rows[0];assert.equal(saved.password_hash,u.encrypted_password);assert.equal(saved.email,u.email);assert.equal(saved.source_identity.subject,u.id);}
 for(const r of snapshot.records){const saved=(await pool.query('select * from records where id=$1',[r.id])).rows[0];for(const k of ['id','owner_id','title','description'])assert.equal(saved[k],r[k]);}
 for(const d of snapshot.documents)assert.equal(sha256(await objectBytes(d.object_key)),d.sha256);
 assert.deepEqual((await pool.query('select id,owner_id,status,output from report_jobs order by id')).rows,snapshot.report_jobs.map(({id,owner_id,status,output})=>({id,owner_id,status,output})).sort((x,y)=>x.id.localeCompare(y.id)));ok('Original user UUIDs, hashes, identities, rows, descriptions, file keys/bytes and job outputs preserved');
 const sessions=[];
 for(const [i,u] of snapshot.users.entries()){
  const s=await signIn(a,u.email);sessions.push(s.cookie);assert.equal(s.data.id,u.id);assert.equal((await http(b,'account','GET',undefined,s.cookie)).data.id,u.id);assert.equal((await http(a,'login','POST',{email:u.email,password:'incorrect-password'})).status,401);
  const other=snapshot.users[1-i],record=snapshot.records.find(r=>r.owner_id===u.id),doc=snapshot.documents.find(d=>d.owner_id===u.id),otherRecord=snapshot.records.find(r=>r.owner_id===other.id),otherDoc=snapshot.documents.find(d=>d.owner_id===other.id),otherJob=snapshot.report_jobs.find(j=>j.owner_id===other.id);
  assert.deepEqual((await http(a,'records','GET',undefined,s.cookie)).data.map(r=>r.id),[record.id]);
  for(const [path,method,body] of [['records/'+otherRecord.id,'GET'],['records/'+otherRecord.id,'PATCH',{title:'Forbidden'}],['records/'+otherRecord.id,'DELETE'],['documents/'+otherDoc.id+'/download','GET'],['reports/'+otherJob.id,'GET']])assert.equal((await http(b,path,method,body,s.cookie)).status,404);
  const bytes=(await http(a,'documents/'+doc.id+'/download','GET',undefined,s.cookie)).data;assert.equal(sha256(bytes),doc.sha256);
  const r=await http(a,'records','POST',{title:'Temporary',description:'Test',owner_id:other.id},s.cookie);assert.equal(r.status,201);assert.equal(r.data.owner_id,u.id);
  assert.equal((await http(b,'records/'+r.data.id,'PATCH',{title:'Edited',description:'Changed'},s.cookie)).data.description,'Changed');assert.equal((await http(a,'records/'+r.data.id,'DELETE',undefined,s.cookie)).status,200);
  const uploaded=await http(a,'documents','POST',Buffer.from('Private upload check\n'),s.cookie,{'X-File-Name':'proof.txt'});assert.equal(uploaded.status,201);assert.equal((await http(b,'documents/'+uploaded.data.id+'/download','GET',undefined,s.cookie)).data.toString(),'Private upload check\n');
  // Keep the imported fixture exact after the API upload proof.
  await pool.query('delete from documents where id=$1',[uploaded.data.id]);
  assert.equal((await http(a,'records','POST',{title:''},s.cookie)).status,400);
  ok(u.email+': existing-password login, session on second server, owner refusals, CRUD, owner-spoof ignored and private upload/download');
 }
 const noOrigin=await fetch(`http://127.0.0.1:${a}/api/reports`,{method:'POST',headers:{Cookie:sessions[0],'Content-Type':'application/json'},body:'{}'});assert.equal(noOrigin.status,403);assert.equal((await http(b,'records')).status,401);ok('Unauthenticated reads and cross-origin mutations refused');
 const jobs=await Promise.all([runJob(),runJob()]);assert.equal(new Set(jobs.map(x=>x.id)).size,2);for(const j of jobs)assert.equal(j.output,'record_count=1\n');assert.equal(await runJob(),null);ok('Concurrent workers complete each imported pending job once with owner-only count');
 const uid=snapshot.users[0].id;const {rows:[crashJob]}=await pool.query('insert into report_jobs(owner_id) values($1) returning *',[uid]);const c=await pool.connect();c.on('error',()=>{});await c.query('begin');await c.query('select id from report_jobs where id=$1 for update',[crashJob.id]);await c.query("update report_jobs set status='COMPLETED',output='uncommitted' where id=$1",[crashJob.id]);assert.equal(await runJob(),null);const pid=(await c.query('select pg_backend_pid() as pid')).rows[0].pid;await pool.query('select pg_terminate_backend($1)',[pid]);c.release(true);const recovered=await runJob();assert.equal(recovered.id,crashJob.id);assert.equal(recovered.output,'record_count=1\n');ok('A killed open job transaction rolls back and another worker completes the pending job');
 await Promise.all([scheduledTask(),scheduledTask()]);const count=await pool.query("select count(*) from schedule_occurrences where occurrence_minute=date_trunc('minute',now())");assert.equal(count.rows[0].count,'1');assert.equal((await pool.query('select count(*) from source_schedules')).rows[0].count,'1');ok('Original schedule preserved; concurrent minute tasks produce one occurrence');
 for(const [i,u] of snapshot.users.entries()){assert.equal((await http(a,'logout','POST',{},sessions[i])).status,200);assert.equal((await http(b,'account','GET',undefined,sessions[i])).status,401);}ok('Logout on server A revokes the session on server B');
 const newAccount=await http(a,'register','POST',{email:'registration-proof@example.com',password});assert.equal(newAccount.status,200);assert.equal((await http(b,'account','GET',undefined,newAccount.cookie)).data.email,'registration-proof@example.com');await http(a,'logout','POST',{},newAccount.cookie);await pool.query('delete from users where email=$1',['registration-proof@example.com']);ok('New registration and cross-server login work after leaving Supabase');
 for(const child of children){child.kill('SIGTERM');assert.equal(await new Promise(r=>child.once('exit',r)),0);}ok('Both web processes shut down gracefully');
 result.database_version=(await pool.query('show server_version')).rows[0].server_version;result.node_version=process.version;result.passed=true;
}finally{
 for(const child of children)if(child.exitCode===null)child.kill('SIGTERM');
 await pool.end();storage.destroy();if(s3)await s3.close();
 await writeFile(process.env.REHEARSAL_RESULT_FILE||'rehearsal-result.json',JSON.stringify(result,null,2)+'\n',{mode:0o600});
}
