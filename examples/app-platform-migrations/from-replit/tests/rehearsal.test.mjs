// Requires a disposable restored database, dedicated S3 bucket, EXPORT_DIR,
// FIXTURE_PASSWORD and REHEARSAL_CONFIRM=disposable-destination.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { randomUUID, createHash } from 'node:crypto';
import bcrypt from 'bcryptjs';
import { pool, migrate } from '../database.mjs';
import { runReport, runSchedule } from '../jobs.mjs';

if (process.env.REHEARSAL_CONFIRM !== 'disposable-destination') throw new Error('Tests mutate a disposable restored database. Set REHEARSAL_CONFIRM=disposable-destination.');
const directory=resolve(process.env.EXPORT_DIR);
const source=JSON.parse(await readFile(join(directory,'tables.json'),'utf8'));
const password=process.env.FIXTURE_PASSWORD;
assert.ok(password,'FIXTURE_PASSWORD is required.');
const children=new Set();
const appDirectory=new URL('../',import.meta.url);
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function waitFor(description,check) {
  const deadline=Date.now()+15000;
  while(Date.now()<deadline){if(await check())return;await delay(100);}
  throw new Error('Timed out: '+description);
}
function start(file,env={},args=[]) {
  const child=spawn(process.execPath,[file,...args],{cwd:appDirectory,env:{...process.env,...env},stdio:['ignore','pipe','pipe']});
  children.add(child);
  // Never forward environment variables, passwords, session cookies or SQL rows.
  child.stdout.resume();child.stderr.resume();
  return child;
}
async function stop(child,signal='SIGTERM') {
  if(child.exitCode!==null||child.signalCode!==null)return;
  const ended=once(child,'exit');child.kill(signal);await ended;
  children.delete(child);
}
const normalize=value=>JSON.parse(JSON.stringify(value));
const sorted=rows=>rows.map(row=>JSON.stringify(normalize(row))).sort();
async function request(port,path,{cookie,body,method='GET',expected=200}={}) {
  const response=await fetch(`http://127.0.0.1:${port}${path}`,{method,headers:{...(cookie?{cookie}:{}),...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  assert.equal(response.status,expected,method+' '+path);
  assert.equal(response.headers.get('cache-control'),'no-store');
  return response;
}

test('restore, returning users, ownership, shared sessions, private files and durable jobs', {timeout:120000}, async t=>{
  try {
    await t.test('every restored row equals the source snapshot, including password hashes and migration ledger',async()=>{
      for(const [table,rows] of Object.entries(source)) {
        assert.match(table,/^[a-z_]+$/);
        assert.deepEqual(sorted((await pool.query(`SELECT * FROM "${table}"`)).rows),sorted(rows),'restored table '+table);
      }
      for(const user of source.users) assert.ok(await bcrypt.compare(password,user.password_hash));
      await migrate();await migrate();
      assert.deepEqual(sorted((await pool.query('SELECT * FROM schema_migrations')).rows),sorted(source.schema_migrations));
    });
    const first=start('web.mjs',{PORT:'18001',WEB_CONCURRENCY:'2'});
    const second=start('web.mjs',{PORT:'18002',WEB_CONCURRENCY:'2'});
    for(const port of [18001,18002]) await waitFor('web '+port,async()=>{try{return(await fetch(`http://127.0.0.1:${port}/healthz`)).ok;}catch{return false;}});
    const cookies={};
    await t.test('returning users retain passwords, stable IDs and cookies across two app processes',async()=>{
      for(const user of source.users){
        const response=await request(18001,'/api/auth/login',{method:'POST',body:{email:user.email,password}});
        cookies[user.id]=response.headers.get('set-cookie').split(';')[0];
        assert.equal((await response.json()).id,user.id);
        assert.equal((await(await request(18002,'/api/me',{cookie:cookies[user.id]})).json()).id,user.id);
      }
      await request(18001,'/api/auth/login',{method:'POST',body:{email:source.users[0].email,password:password+'wrong'},expected:401});
    });
    await t.test('each owner can read exported data and cannot guess another owner IDs',async()=>{
      for(const user of source.users){
        const cookie=cookies[user.id];
        const own=source.records.find(row=>row.owner_id===user.id);
        const foreign=source.records.find(row=>row.owner_id!==user.id);
        assert.equal((await(await request(18002,'/api/records/'+own.id,{cookie})).json()).title,own.title);
        for(const method of ['GET','PATCH','DELETE'])await request(18001,'/api/records/'+foreign.id,{cookie,method,...(method==='PATCH'?{body:{title:'blocked'}}:{}),expected:404});
        const foreignFile=source.documents.find(row=>row.owner_id!==user.id);
        const foreignJob=source.jobs.find(row=>row.owner_id!==user.id);
        await request(18001,'/api/documents/'+foreignFile.id+'/download',{cookie,expected:404});
        await request(18001,'/api/jobs/'+foreignJob.id,{cookie,expected:404});
        const doc=source.documents.find(row=>row.owner_id===user.id);
        const bytes=Buffer.from(await(await request(18002,'/api/documents/'+doc.id+'/download',{cookie})).arrayBuffer());
        assert.equal(bytes.length,doc.byte_length);
        assert.equal(createHash('sha256').update(bytes).digest('hex'),doc.sha256);
      }
      const member=source.users.find(row=>!row.is_admin);
      await request(18001,'/api/operations',{cookie:cookies[member.id],method:'PUT',body:{worker_paused:false},expected:403});
    });
    await t.test('CRUD, new private upload/download, registration, and logout revocation across app processes',async()=>{
      const user=source.users[0],cookie=cookies[user.id];
      const created=await(await request(18001,'/api/records',{cookie,method:'POST',body:{title:'Rehearsal temporary'},expected:201})).json();
      assert.equal(created.description,'');
      const edited=await(await request(18002,'/api/records/'+created.id,{cookie,method:'PATCH',body:{title:'Rehearsal edited',description:'updated'}})).json();
      assert.equal(edited.description,'updated');
      await request(18001,'/api/records/'+created.id,{cookie,method:'DELETE'});
      await request(18002,'/api/records/'+created.id,{cookie,expected:404});
      const bytes=Buffer.from('New destination-only document\n');
      const doc=await(await request(18001,'/api/documents',{cookie,method:'POST',body:{filename:'destination.txt',content_base64:bytes.toString('base64')},expected:201})).json();
      assert.deepEqual(Buffer.from(await(await request(18002,'/api/documents/'+doc.id+'/download',{cookie})).arrayBuffer()),bytes);
      await request(18001,'/api/documents',{cookie,method:'POST',body:{filename:'bad.txt',content_base64:'???'},expected:400});
      const credentials={email:'claire@example.com',password};
      const registered=await request(18001,'/api/auth/register',{method:'POST',body:credentials,expected:201});
      const newCookie=registered.headers.get('set-cookie').split(';')[0];
      await request(18002,'/api/me',{cookie:newCookie});
      await request(18002,'/api/auth/register',{method:'POST',body:credentials,expected:409});
      await request(18001,'/api/auth/logout',{method:'POST',cookie:newCookie});
      await request(18002,'/api/me',{cookie:newCookie,expected:401});
      await request(18001,'/api/auth/logout',{method:'POST',cookie});
      await request(18002,'/api/me',{cookie,expected:401});
    });
    await t.test('killed worker rolls back a locked pending job and another worker completes it',async()=>{
      await pool.query('UPDATE controls SET worker_paused=false WHERE id=1');
      const pending=source.jobs.filter(row=>row.state==='PENDING');
      const script=`import {pool} from './database.mjs';const c=await pool.connect();await c.query('BEGIN');await c.query("UPDATE jobs SET state='RUNNING' WHERE id=$1",['${pending[0].id}']);console.log('LOCKED');await new Promise(()=>{});`;
      const locked=spawn(process.execPath,['--input-type=module','-e',script],{cwd:appDirectory,env:process.env,stdio:['ignore','pipe','pipe']});children.add(locked);locked.stderr.resume();
      await new Promise((resolve,reject)=>{locked.stdout.once('data',resolve);locked.once('exit',()=>reject(new Error('Lock worker exited early.')));});
      assert.equal(await runReport(),pending[1].id);
      assert.equal(await runReport(),null);
      await stop(locked,'SIGKILL');
      assert.equal(await runReport(),pending[0].id);
      const results=await pool.query("SELECT id,state,output FROM jobs WHERE id=ANY($1::uuid[])",[pending.map(row=>row.id)]);
      for(const row of results.rows){assert.equal(row.state,'COMPLETED');assert.equal(row.output,'record_count=1\n');}
    });
    await t.test('concurrent claims complete each job once and real jobs command handles pending work',async()=>{
      const ids=[randomUUID(),randomUUID()];
      for(const id of ids)await pool.query('INSERT INTO jobs(id,owner_id) VALUES($1,$2)',[id,source.users[0].id]);
      const completed=await Promise.all([runReport(),runReport(),runReport()]);
      assert.deepEqual(completed.filter(Boolean).sort(),ids.sort());
      const id=randomUUID();await pool.query('INSERT INTO jobs(id,owner_id) VALUES($1,$2)',[id,source.users[0].id]);
      const runner=start('jobs_runner.mjs');
      await waitFor('background jobs',async()=>(await pool.query('SELECT state FROM jobs WHERE id=$1',[id])).rows[0].state==='COMPLETED');
      await stop(runner);
    });
    await t.test('persisted schedule catches up once under concurrent workers',async()=>{
      const occurrence=new Date(Date.now()-60000);
      await pool.query('UPDATE controls SET scheduler_paused=false WHERE id=1');
      await pool.query("UPDATE schedules SET next_run_at=$1 WHERE id='archive_old_reports'",[occurrence]);
      await Promise.all([runSchedule(),runSchedule()]);
      assert.equal((await pool.query('SELECT count(*)::int AS n FROM scheduled_runs WHERE occurrence_at=$1',[occurrence])).rows[0].n,1);
      assert.ok((await pool.query("SELECT next_run_at FROM schedules WHERE id='archive_old_reports'")).rows[0].next_run_at>new Date());
    });
    await t.test('connections reconnect after PostgreSQL drops existing connections, without restarting web processes',async()=>{
      const before=[first.pid,second.pid];
      await pool.query('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()');
      await request(18001,'/healthz');await request(18002,'/healthz');
      assert.deepEqual([first.pid,second.pid],before);
      const response=await request(18001,'/api/auth/login',{method:'POST',body:{email:source.users[1].email,password}});
      const cookie=response.headers.get('set-cookie').split(';')[0];
      await request(18002,'/api/records',{cookie,method:'POST',body:{title:'After connection termination'},expected:201});
    });
    await stop(first);await stop(second);
  } finally {
    for(const child of children)await stop(child);
    await pool.end();
  }
});
