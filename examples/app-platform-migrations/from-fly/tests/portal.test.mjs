import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import { pathToFileURL } from 'node:url';
const appDir=process.env.APP_DIR||'/app';
const {pool}=await import(pathToFileURL(appDir+'/database.mjs'));
const base=process.env.APP_URL||'http://127.0.0.1:18001',second=process.env.SECOND_APP_URL||'http://127.0.0.1:18002';
const digest=b=>createHash('sha256').update(b).digest('hex');
const audit=JSON.parse(await readFile((process.env.EXPORT_DIR||'/export')+'/table-audit.json','utf8'));
async function request(path,{method='GET',body,cookie,url=base,raw,status=200}={}){
 const headers={};if(cookie)headers.cookie=cookie;if(body!==undefined){headers['content-type']='application/json';raw=JSON.stringify(body);}else if(raw!==undefined)headers['content-type']='application/octet-stream';
 const r=await fetch(url+path,{method,headers,body:raw});assert.equal(r.status,status,method+' '+path);const bytes=Buffer.from(await r.arrayBuffer());let value;try{value=JSON.parse(bytes);}catch{value=bytes;}return {value,bytes,cookie:r.headers.get('set-cookie')?.split(';')[0]};
}
async function login(email,url=base){return request('/api/login',{url,method:'POST',body:{email,password:process.env.FIXTURE_PASSWORD}});}
const run=(file,args=[])=>spawn(process.execPath,[appDir+'/'+file,...args],{env:process.env,stdio:['ignore','pipe','pipe']});
async function exited(child){const [code]=await once(child,'exit');assert.equal(code,0,'Child command completed');}
let cookies=[];
test('restored passwords, stable owners, private bytes, shared sessions, CRUD and revocation',async()=>{
 await pool.query('UPDATE controls SET maintenance=false WHERE id=1');
 for(const user of audit.users){
  const r=await login(user.email);assert.equal(r.value.id,user.id);cookies.push(r.cookie);
  const me=await request('/api/me',{cookie:r.cookie,url:second});assert.equal(me.value.id,user.id);
  const records=(await request('/api/records',{cookie:r.cookie})).value;assert.equal(records.length,1);assert.equal(records[0].owner_id,user.id);
  const expected=audit.records.find(x=>x.owner_id===user.id);assert.equal(records[0].id,expected.id);assert.equal(records[0].description,expected.description);
  const docs=(await request('/api/documents',{cookie:r.cookie})).value;assert.equal(docs.length,1);
  const bytes=(await request('/api/documents/'+docs[0].id,{cookie:r.cookie})).bytes;
  const person=user.email.startsWith('barbara')?'Barbara':'Michael';assert.equal(bytes.toString(),person+' synthetic document\n');assert.equal(digest(bytes),docs[0].sha256);
 }
 const other=audit.users[1].id,record=audit.records.find(r=>r.owner_id===other),document=audit.documents.find(r=>r.owner_id===other),job=audit.report_jobs.find(r=>r.owner_id===other);
 for(const path of ['/api/records/'+record.id,'/api/documents/'+document.id,'/api/reports/'+job.id])await request(path,{cookie:cookies[0],status:404});
 await request('/api/records/'+record.id,{method:'PATCH',body:{title:'Forbidden'},cookie:cookies[0],status:404});
 await request('/api/records/'+record.id,{method:'DELETE',cookie:cookies[0],status:404});
 const temporary=(await request('/api/records',{method:'POST',body:{title:'Temporary'},cookie:cookies[0],status:201})).value;
 await request('/api/records/'+temporary.id,{method:'PATCH',body:{title:'Edited',description:'Destination only'},cookie:cookies[0]});
 await request('/api/records/'+temporary.id,{method:'DELETE',cookie:cookies[0],status:204});
 const newDoc=(await request('/api/documents?file_name=destination.txt',{method:'POST',raw:'Destination document\n',cookie:cookies[0],status:201})).value;
 assert.equal((await request('/api/documents/'+newDoc.id,{cookie:cookies[0]})).bytes.toString(),'Destination document\n');
 await request('/api/login',{method:'POST',body:{email:audit.users[0].email,password:'incorrect fixture password'},status:401});
 await request('/api/logout',{method:'POST',cookie:cookies[0]});await request('/api/me',{url:second,cookie:cookies[0],status:401});
 cookies[0]=(await login(audit.users[0].email)).cookie;
});
test('actual worker rolls back a killed transaction, concurrent workers complete each report once',async()=>{
 // A test-only trigger holds the real worker after its UPDATE and before COMMIT.
 await pool.query("CREATE FUNCTION hold_report_test() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock(20261105); PERFORM pg_sleep(30); RETURN NEW; END $$");
 await pool.query('CREATE TRIGGER hold_report_test AFTER UPDATE ON report_jobs FOR EACH ROW EXECUTE FUNCTION hold_report_test()');
 await pool.query('UPDATE controls SET jobs_paused=false WHERE id=1');
 const child=run('jobs.mjs',['--once']);
 let locked=false;
 for(let i=0;i<100;i++){const r=await pool.query("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND objid=20261105 AND granted) AS locked");if(r.rows[0].locked){locked=true;break;}await delay(50);}
 assert.ok(locked,'Actual worker reached the uncommitted update');child.kill('SIGKILL');await once(child,'exit');
 await pool.query('DROP TRIGGER hold_report_test ON report_jobs');await pool.query('DROP FUNCTION hold_report_test()');
 const pending=await pool.query("SELECT count(*)::integer AS n FROM report_jobs WHERE state='PENDING'");assert.equal(pending.rows[0].n,2);
 const a=run('jobs.mjs',['--once']),b=run('jobs.mjs',['--once']);await Promise.all([exited(a),exited(b)]);
 const jobs=(await pool.query('SELECT * FROM report_jobs ORDER BY id')).rows;assert.equal(jobs.length,2);
 for(const job of jobs){assert.equal(job.state,'COMPLETED');assert.equal(job.output,'record_count=1\n');}
 // The authenticated report route returns the persisted owner-specific output.
 for(let i=0;i<audit.users.length;i++){const rows=(await request('/api/reports',{cookie:cookies[i]})).value;assert.equal(rows.length,1);assert.equal(rows[0].owner_id,audit.users[i].id);assert.equal(rows[0].output,'record_count=1\n');}
});
test('hourly task is idempotent, migrations rerun and database reconnection keeps sessions',async()=>{
 await pool.query("DELETE FROM scheduled_runs WHERE occurrence_at=date_trunc('hour',now())");
 await pool.query("INSERT INTO sessions(token_hash,owner_id,expires_at) VALUES('expired-session-test',$1,now()-interval '1 day')",[audit.users[0].id]);
 const before=(await pool.query('SELECT count(*)::integer AS n FROM scheduled_runs')).rows[0].n;
 const a=run('schedule.mjs'),b=run('schedule.mjs');await Promise.all([exited(a),exited(b)]);
 const after=(await pool.query('SELECT count(*)::integer AS n FROM scheduled_runs')).rows[0].n;assert.equal(after,before+1);
 assert.equal((await pool.query("SELECT count(*)::integer AS n FROM sessions WHERE token_hash='expired-session-test'")).rows[0].n,0);
 await exited(run('database.mjs'));await exited(run('database.mjs'));
 assert.equal((await pool.query('SELECT count(*)::integer AS n FROM schema_migrations')).rows[0].n,2);
 // The previous release's title-only SQL still works after the additive migration.
 await pool.query('UPDATE records SET title=title WHERE owner_id=$1',[audit.users[0].id]);
 await pool.query('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename=current_user AND datname=current_database() AND pid<>pg_backend_pid()');
 let success=false;for(let i=0;i<30;i++){try{await request('/api/me',{cookie:cookies[0],url:second});success=true;break;}catch{await delay(100);}}
 assert.ok(success,'Session works after old database connections terminate');
 await request('/api/records',{method:'POST',body:{title:'After reconnection'},cookie:cookies[0],status:201});
});
test('malformed inputs, private unauthenticated access, and production seeds are refused',async()=>{
 const registered=await request('/api/register',{method:'POST',body:{email:'cynthia@example.com',password:process.env.FIXTURE_PASSWORD},status:201});assert.ok(registered.value.id);
 await request('/api/register',{method:'POST',body:{email:'cynthia@example.com',password:process.env.FIXTURE_PASSWORD},status:409});
 await request('/api/records',{status:401});await request('/api/documents/'+audit.documents[0].id,{status:401});
 await request('/api/records/not-a-uuid',{cookie:cookies[0],status:400});
 const response=await fetch(base+'/api/records',{method:'POST',headers:{cookie:cookies[0],'content-type':'application/json'},body:'{bad json'});assert.equal(response.status,400);assert.equal(response.headers.get('cache-control'),'no-store');
 const child=spawn(process.execPath,[appDir+'/seed-test-data.mjs'],{env:{...process.env,APP_ENV:'production'},stdio:['ignore','pipe','pipe']});const [code]=await once(child,'exit');assert.notEqual(code,0,'Production seed is refused');
});
test.after(async()=>{await pool.end();});
