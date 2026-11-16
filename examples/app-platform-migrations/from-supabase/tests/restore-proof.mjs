import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {spawnSync,spawn} from 'node:child_process';
import S3rver from 's3rver';
import {CreateBucketCommand,PutObjectCommand,GetObjectCommand} from '@aws-sdk/client-s3';
import {pool,storage,bucket,sha256,login} from '../backend.mjs';
import {poolForDatabaseUrl,singleServerDatabaseUrl} from '../pg_with_multiple_database_servers.mjs';
const target=poolForDatabaseUrl(process.env.RESTORE_DATABASE_URL,{statement_timeout:10000,query_timeout:12000}),result={checks:[]};let child;
const s3=new S3rver({port:Number(new URL(process.env.S3_ENDPOINT).port),address:'127.0.0.1',silent:true,directory:process.env.REHEARSAL_S3_DIR});
const targetBucket=process.env.RESTORE_S3_BUCKET;
const ok=name=>{result.checks.push(name);console.log('PASS '+name);};
async function pgEnv(url){const x=new URL(await singleServerDatabaseUrl(url));return {...process.env,PGHOST:x.hostname,PGPORT:x.port||'5432',PGUSER:decodeURIComponent(x.username),PGPASSWORD:decodeURIComponent(x.password),PGDATABASE:x.pathname.slice(1)};}
try{
 await s3.run();await storage.send(new CreateBucketCommand({Bucket:targetBucket}));
 const u=(await pool.query('select * from users order by email')).rows[0];const password=await readFile(process.env.FIXTURE_PASSWORD_FILE,'utf8');const session=await login(u.email,password);const {rows:[pending]}=await pool.query('insert into report_jobs(owner_id) values($1) returning *',[u.id]);
 const dump=process.env.RESTORE_DUMP_FILE;let r=spawnSync('pg_dump',['--format=custom','--no-owner','--no-acl','--file='+dump],{env:await pgEnv(process.env.DATABASE_URL)});assert.equal(r.status,0,'Destination pg_dump failed');
 const restoreEnv=await pgEnv(process.env.RESTORE_DATABASE_URL);r=spawnSync('pg_restore',['--exit-on-error','--no-owner','--no-acl','--dbname='+restoreEnv.PGDATABASE,dump],{env:restoreEnv});assert.equal(r.status,0,'Destination pg_restore failed');
 const tables=['users','sessions','records','documents','report_jobs','schedule_occurrences','source_schedules','schema_migrations','import_receipts'];
 for(const name of tables){const q=`select to_jsonb(t) as value from ${name} t order by to_jsonb(t)::text`;assert.deepEqual((await target.query(q)).rows,(await pool.query(q)).rows);}ok('PostgreSQL archive restore preserves every app table including password hashes, active sessions, job outputs, pending work, schedules and migration checksums');
 const {rows:docs}=await pool.query('select * from documents');
 for(const d of docs){const bytes=Buffer.from(await (await storage.send(new GetObjectCommand({Bucket:bucket,Key:d.object_key}))).Body.transformToByteArray());assert.equal(sha256(bytes),d.sha256);await storage.send(new PutObjectCommand({Bucket:targetBucket,Key:d.object_key,Body:bytes}));const copied=Buffer.from(await (await storage.send(new GetObjectCommand({Bucket:targetBucket,Key:d.object_key}))).Body.transformToByteArray());assert.equal(sha256(copied),d.sha256);assert.equal(copied.length,Number(d.byte_length));}ok('Private file bytes are copied into a separate restore bucket and every referenced hash matches');
 const port=Number(process.env.PORT)+2;child=spawn(process.execPath,['web.mjs'],{cwd:new URL('../',import.meta.url),env:{...process.env,PORT:String(port),HOST:'127.0.0.1',DATABASE_URL:process.env.RESTORE_DATABASE_URL,S3_BUCKET:targetBucket},stdio:['ignore','ignore','inherit']});
 await new Promise((resolve,reject)=>{const start=Date.now();const tick=async()=>{try{if((await fetch(`http://127.0.0.1:${port}/healthz`)).ok)return resolve();}catch{}if(Date.now()-start>10000)return reject(Error('Restore web failed to become healthy'));setTimeout(tick,100);};tick();});
 let response=await fetch(`http://127.0.0.1:${port}/api/account`,{headers:{Cookie:'portal_session='+session.token}});assert.equal(response.status,200);assert.equal((await response.json()).id,u.id);
 response=await fetch(`http://127.0.0.1:${port}/api/login`,{method:'POST',headers:{Origin:process.env.PUBLIC_ORIGIN,'Content-Type':'application/json'},body:JSON.stringify({email:u.email,password})});assert.equal(response.status,200);ok('Restored app accepts an existing session and the original Supabase password');
 for(const d of docs.filter(d=>d.owner_id===u.id)){response=await fetch(`http://127.0.0.1:${port}/api/documents/${d.id}/download`,{headers:{Cookie:'portal_session='+session.token}});assert.equal(response.status,200);assert.equal(sha256(Buffer.from(await response.arrayBuffer())),d.sha256);}assert.equal((await target.query('select status from report_jobs where id=$1',[pending.id])).rows[0].status,'PENDING');ok('Restored HTTP file download matches bytes and pending job remains available');
 result.passed=true;
}finally{if(child){child.kill('SIGTERM');await new Promise(r=>child.once('exit',r));}await pool.end();await target.end();storage.destroy();await s3.close();await writeFile(process.env.RESTORE_RESULT_FILE,JSON.stringify(result,null,2)+'\n',{mode:0o600});}
