// Requires a disposable restored database, dedicated S3 bucket, EXPORT_DIR,
// FIXTURE_PASSWORD and REHEARSAL_CONFIRM=disposable-destination.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { isDeepStrictEqual } from 'node:util';
import { randomUUID, createHash } from 'node:crypto';
import { verifyFirebasePassword } from '../firebase_password.mjs';
import { pool, migrate } from '../database.mjs';
import { runReport, runSchedule } from '../jobs.mjs';
import { upload, download, remove } from '../storage.mjs';
import { S3Client, ListObjectsV2Command } from '@aws-sdk/client-s3';

if (process.env.REHEARSAL_CONFIRM !== 'disposable-destination') throw new Error('Tests mutate a disposable restored database. Set REHEARSAL_CONFIRM=disposable-destination.');
const directory=resolve(process.env.EXPORT_DIR);
const native=JSON.parse(await readFile(join(directory,'firestore.json'),'utf8')).collections;
const exportedUsers=JSON.parse(await readFile(join(directory,'users.json'),'utf8')).users;
const source={users:exportedUsers.map(user=>({...user,id:user.localId,is_admin:JSON.parse(user.customAttributes||'{}').admin===true})),...Object.fromEntries(['records','documents','jobs'].map(name=>[name,native[name].map(row=>({id:row.id,...row.data}))]))};
const hashConfig=JSON.parse(await readFile(join(directory,'auth-config.json'),'utf8')).signIn.hashConfig;
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
    await t.test('restored identities, password verifiers, ownership and raw Firestore documents match the export',async()=>{
      const users=(await pool.query('SELECT * FROM users')).rows;
      assert.equal(users.length,source.users.length);
      for(const original of source.users) {
        const row=users.find(row=>row.id===original.localId);
        assert.ok(row); assert.equal(row.email,original.email.toLowerCase());
        assert.equal(row.password_algorithm,'firebase_scrypt');
        assert.ok(row.firebase_password_hash===original.passwordHash,'Imported password verifier differs from export.');
        assert.ok(row.firebase_password_salt===original.salt,'Imported password salt differs from export.');
        assert.equal(row.disabled,original.disabled===true);
        assert.equal(row.is_admin,original.is_admin);
        assert.ok(isDeepStrictEqual((await pool.query('SELECT data FROM source_auth_users WHERE firebase_uid=$1',[original.localId])).rows[0]?.data,exportedUsers.find(user=>user.localId===original.localId)),'Raw Auth export differs from imported audit row.');
        assert.ok(await verifyFirebasePassword(password,row.firebase_password_hash,row.firebase_password_salt,hashConfig));
        assert.equal((await pool.query('SELECT subject FROM identities WHERE user_id=$1',[row.id])).rows[0].subject,original.localId);
      }
      const preserved=(await pool.query('SELECT * FROM source_documents')).rows;
      assert.equal(preserved.length,Object.values(native).reduce((n,rows)=>n+rows.length,0));
      for(const [collection,rows] of Object.entries(native)) for(const row of rows) {
        assert.deepEqual(preserved.find(item=>item.collection_name===collection&&item.source_document_id===row.id)?.data,row.data);
      }
      for(const original of source.records) {
        const row=(await pool.query('SELECT * FROM records WHERE id=$1',[original.id])).rows[0];
        for(const key of ['owner_id','title','description'])assert.equal(row[key],original[key]);
      }
      assert.equal((await pool.query('SELECT count(*)::int AS n FROM records')).rows[0].n,source.records.length);
      assert.equal((await pool.query('SELECT count(*)::int AS n FROM documents')).rows[0].n,source.documents.length);
      assert.equal((await pool.query('SELECT count(*)::int AS n FROM jobs')).rows[0].n,source.jobs.length);
      for(const original of source.documents) {
        const row=(await pool.query('SELECT * FROM documents WHERE id=$1',[original.id])).rows[0];
        for(const key of ['owner_id','object_key','sha256','byte_length'])assert.equal(row[key],original[key]);
        assert.equal(row.filename,original.name);
      }
      for(const original of source.jobs) {
        const row=(await pool.query('SELECT * FROM jobs WHERE id=$1',[original.id])).rows[0];
        assert.equal(row.owner_id,original.owner_id);assert.equal(row.state,original.state==='ARCHIVED'?'COMPLETED':original.state);assert.equal(row.archived,original.state==='ARCHIVED'||original.archived===true);assert.equal(row.output,original.output??null);
        if(original.completed_at)assert.equal(row.completed_at.toISOString(),new Date(original.completed_at).toISOString());
      }
      const before=normalize((await pool.query('SELECT * FROM schema_migrations ORDER BY name')).rows);
      assert.equal(before.length,2);await migrate();await migrate();
      assert.deepEqual(normalize((await pool.query('SELECT * FROM schema_migrations ORDER BY name')).rows),before);
      const controls=(await pool.query('SELECT * FROM controls WHERE id=1')).rows[0];
      assert.equal(controls.worker_paused,true);assert.equal(controls.scheduler_paused,true);assert.equal(controls.maintenance_enabled,native.controls.find(row=>row.id==='runtime').data.maintenance);
      const schedule=(await pool.query("SELECT * FROM schedules WHERE id='archive_reports'")).rows[0];
      assert.equal(schedule.next_run_at.toISOString(),new Date(native.schedules.find(row=>row.id==='archive_reports').data.next_run_at).toISOString());
      await pool.query('UPDATE controls SET maintenance_enabled=false WHERE id=1');
    });
    execFileSync(process.execPath,['scripts/import_objects.mjs'],{cwd:appDirectory,env:process.env,stdio:['ignore','pipe','pipe']});
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
        await assert.rejects(upload(doc.object_key,Buffer.from('Must not replace imported bytes.')),error=>error.$metadata?.httpStatusCode===412);
        const bytes=Buffer.from(await(await request(18002,'/api/documents/'+doc.id+'/download',{cookie})).arrayBuffer());
        assert.equal(bytes.length,doc.byte_length);
        assert.equal(createHash('sha256').update(bytes).digest('hex'),doc.sha256);
      }
      const member=source.users.find(row=>!row.is_admin);
      await request(18001,'/api/operations',{cookie:cookies[member.id],method:'PUT',body:{worker_paused:false},expected:403});
    });
    await t.test('metadata insert failure keeps private uploaded bytes and leaves other metadata unchanged',async()=>{
      const user=source.users[0],cookie=cookies[user.id],prefix=`private/${user.id}/`;
      const client=new S3Client({endpoint:process.env.S3_ENDPOINT,region:process.env.S3_REGION||'auto',forcePathStyle:true,credentials:{accessKeyId:process.env.S3_ACCESS_KEY_ID,secretAccessKey:process.env.S3_SECRET_ACCESS_KEY}});
      const keys=async()=>new Set((await client.send(new ListObjectsV2Command({Bucket:process.env.S3_BUCKET,Prefix:prefix}))).Contents?.map(object=>object.Key)||[]);
      const beforeKeys=await keys();
      const beforeRows=(await pool.query('SELECT * FROM documents ORDER BY id')).rows;
      const bytes=Buffer.from('Private bytes must survive a metadata insert error.\n');
      let orphanKey;
      try {
        await pool.query(`CREATE FUNCTION fixture_reject_document_metadata() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN
            IF NEW.filename='metadata-error-proof.txt' THEN RAISE EXCEPTION 'Synthetic metadata insert failure' USING ERRCODE='23514'; END IF;
            RETURN NEW;
          END; $$`);
        await pool.query('CREATE TRIGGER fixture_reject_document_metadata BEFORE INSERT ON documents FOR EACH ROW EXECUTE FUNCTION fixture_reject_document_metadata()');
        await request(18001,'/api/documents',{cookie,method:'POST',body:{filename:'metadata-error-proof.txt',content_base64:bytes.toString('base64')},expected:500});
        const added=[...await keys()].filter(key=>!beforeKeys.has(key));
        assert.equal(added.length,1,'The failed metadata request must retain exactly its newly uploaded private object.');
        orphanKey=added[0];
        assert.deepEqual(await download(orphanKey),bytes);
        assert.ok(isDeepStrictEqual((await pool.query('SELECT * FROM documents ORDER BY id')).rows,beforeRows),'Metadata failure must leave every existing document row unchanged.');
      } finally {
        await pool.query('DROP TRIGGER IF EXISTS fixture_reject_document_metadata ON documents');
        await pool.query('DROP FUNCTION IF EXISTS fixture_reject_document_metadata()');
        if(orphanKey)await remove(orphanKey);
        client.destroy();
      }
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
      const pending=source.jobs.filter(row=>row.state==='PENDING').sort((a,b)=>new Date(a.created_at)-new Date(b.created_at)||a.id.localeCompare(b.id));
      const script=`import {pool} from './database.mjs';const c=await pool.connect();await c.query('BEGIN');await c.query("UPDATE jobs SET state='RUNNING' WHERE id=$1",[process.env.LOCK_JOB_ID]);console.log('LOCKED');await new Promise(()=>{});`;
      const locked=spawn(process.execPath,['--input-type=module','-e',script],{cwd:appDirectory,env:{...process.env,LOCK_JOB_ID:pending[0].id},stdio:['ignore','pipe','pipe']});children.add(locked);locked.stderr.resume();
      await new Promise((resolve,reject)=>{locked.stdout.once('data',resolve);locked.once('exit',()=>reject(new Error('Lock worker exited early.')));});
      assert.equal(await runReport(),pending[1].id);
      assert.equal(await runReport(),null);
      await stop(locked,'SIGKILL');
      assert.equal(await runReport(),pending[0].id);
      const results=await pool.query("SELECT id,state,output FROM jobs WHERE id=ANY($1::text[])",[pending.map(row=>row.id)]);
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
      const archivedJob=randomUUID();
      await pool.query("INSERT INTO jobs(id,owner_id,state,output,completed_at) VALUES($1,$2,'COMPLETED','record_count=1'||chr(10),now()-interval '31 days')",[archivedJob,source.users[0].id]);
      await pool.query('UPDATE controls SET scheduler_paused=false WHERE id=1');
      await pool.query("UPDATE schedules SET next_run_at=$1 WHERE id='archive_reports'",[occurrence]);
      await Promise.all([runSchedule(),runSchedule()]);
      assert.equal((await pool.query('SELECT count(*)::int AS n FROM scheduled_runs WHERE occurrence_at=$1',[occurrence])).rows[0].n,1);
      assert.equal((await pool.query('SELECT archived FROM jobs WHERE id=$1',[archivedJob])).rows[0].archived,true);
      assert.equal((await pool.query('SELECT archived_count FROM scheduled_runs WHERE occurrence_at=$1',[occurrence])).rows[0].archived_count,1);
      assert.ok((await pool.query("SELECT next_run_at FROM schedules WHERE id='archive_reports'")).rows[0].next_run_at>new Date());
    });
    await t.test('connections reconnect after PostgreSQL drops existing connections, without restarting web processes',async()=>{
      const before=[first.pid,second.pid],retainedUser=source.users[1],retainedCookie=cookies[retainedUser.id];
      await pool.query('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()');
      const recoveryStarted=Date.now(),observations=[];
      // Termination can reach a stale idle connection on its next request. Observe
      // the error, then poll only read-only health checks within the existing 15s bound.
      await waitFor('database connections recover on both unchanged web processes',async()=>{
        let healthy=true;
        for(const port of [18001,18002]) {
          try {
            const response=await fetch(`http://127.0.0.1:${port}/healthz`);
            observations.push({port,http_status_code:response.status,elapsed_ms:Date.now()-recoveryStarted});
            if(!response.ok)healthy=false;
          } catch {
            observations.push({port,network_error:true,elapsed_ms:Date.now()-recoveryStarted});healthy=false;
          }
        }
        return healthy;
      });
      console.log('Connection recovery evidence: '+JSON.stringify({elapsed_ms:Date.now()-recoveryStarted,observations,web_process_ids_unchanged:[first.pid,second.pid].every((pid,index)=>pid===before[index])}));
      assert.deepEqual([first.pid,second.pid],before);
      for(const port of [18001,18002])assert.equal((await(await request(port,'/api/me',{cookie:retainedCookie})).json()).id,retainedUser.id);
      const foreign=source.records.find(row=>row.owner_id!==retainedUser.id);
      await request(18001,'/api/records/'+foreign.id,{cookie:retainedCookie,expected:404});
      await request(18001,'/api/auth/login',{method:'POST',body:{email:retainedUser.email,password}});
      // One fresh mutation after recovery; no interrupted or uncertain write is replayed.
      const created=await(await request(18002,'/api/records',{cookie:retainedCookie,method:'POST',body:{title:'After connection termination'},expected:201})).json();
      assert.equal(created.owner_id,retainedUser.id);
      assert.equal((await(await request(18001,'/api/records/'+created.id,{cookie:retainedCookie})).json()).id,created.id);
    });
    await stop(first);await stop(second);
  } finally {
    for(const child of children)await stop(child);
    await pool.end();
  }
});
