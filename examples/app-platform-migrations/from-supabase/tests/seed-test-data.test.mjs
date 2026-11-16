import test from 'node:test';
import { randomUUID } from 'node:crypto';
import { ListObjectsV2Command } from '@aws-sdk/client-s3';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { isDeepStrictEqual } from 'node:util';
import bcrypt from 'bcryptjs';
import { pool, objectBytes, storage, bucket } from '../backend.mjs';
import { migrate } from '../operations.mjs';

if(process.env.REHEARSAL_CONFIRM!=='disposable-destination')throw Error('Use a disposable empty database and bucket.');
const directory=new URL('../',import.meta.url);
function seed(env={},args=[]){execFileSync(process.execPath,['operations.mjs','seed-test-data',...args],{cwd:directory,env:{...process.env,APP_ENV:'staging',...env},stdio:['ignore','pipe','pipe']});}
async function objects(){return (await storage.send(new ListObjectsV2Command({Bucket:bucket}))).Contents?.map(row=>[row.Key,row.ETag]).sort()||[];}
async function snapshot(){const data={};for(const table of ['users','sessions','records','documents','report_jobs','schedule_occurrences','source_schedules','import_receipts','schema_migrations'])data[table]=(await pool.query(`SELECT to_jsonb(t) AS row FROM ${table} t ORDER BY to_jsonb(t)::text`)).rows;return data;}
async function rows(table){return (await pool.query(`SELECT * FROM ${table} ORDER BY id`)).rows;}
async function databaseRows(){
 const data={};
 for(const {tablename} of (await pool.query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).rows)
  data[tablename]=(await pool.query('SELECT to_jsonb(t) AS row FROM "'+tablename.replaceAll('"','""')+'" t ORDER BY to_jsonb(t)::text')).rows;
 return data;
}
test('test data works on laptops and staging, preserves fixtures and grows accounts in bulk',async()=>{
 try{
  assert.throws(()=>seed({APP_ENV:'production'}),/APP_ENV must be development or staging/);
  assert.throws(()=>seed({APP_ENV:undefined}),/APP_ENV must be development or staging/);
  assert.throws(()=>seed({FIXTURE_PASSWORD:'short'}),/FIXTURE_PASSWORD/);
  assert.throws(()=>seed({FIXTURE_PASSWORD:'é'.repeat(37)}),/FIXTURE_PASSWORD/);
  await migrate();
  const unrelated=randomUUID();
  await pool.query('INSERT INTO users(id,email,password_hash,email_confirmed_at) VALUES($1,$2,$3,now())',[unrelated,'other-data@example.com','not-a-login']);
  let before=await snapshot(),files=await objects();
  assert.throws(()=>seed({},['--accounts','1000']),/contains accounts that are not test data/);
  assert.ok(isDeepStrictEqual(await snapshot(),before),'refusal leaves all database rows unchanged');
  assert.deepEqual(await objects(),files,'refusal uploads no objects');
  await pool.query('DELETE FROM users WHERE id=$1',[unrelated]);
  await pool.query('INSERT INTO users(id,email,password_hash,email_confirmed_at) VALUES($1,$2,$3,now())',[unrelated,'test-account-0000003@example.com','not-a-login']);
  before=await snapshot();files=await objects();
  assert.throws(()=>seed({},['--accounts','1000']),/contains accounts that are not test data/);
  assert.ok(isDeepStrictEqual(await snapshot(),before),'non-canonical account refusal leaves all rows unchanged');
  assert.deepEqual(await objects(),files,'non-canonical account refusal uploads no objects');
  await pool.query('DELETE FROM users WHERE id=$1',[unrelated]);
  seed({APP_ENV:'development'});
  const fixture={};for(const table of ['users','records','documents','report_jobs'])fixture[table]=await rows(table);
  for(const count of ['1','2.5']){
   const beforeInvalid=await databaseRows();
   assert.throws(()=>seed({},['--accounts',count]),error=>{
    assert.ok(error.stderr?.toString().includes('Usage: seed-test-data [--accounts N]; --accounts must be a whole number of at least 2'),'invalid accounts reports the specific usage message on stderr');
    return true;
   });
   assert.ok(isDeepStrictEqual(await databaseRows(),beforeInvalid),'invalid accounts leaves every database row unchanged');
  }
  seed({FIXTURE_PASSWORD:process.env.FIXTURE_PASSWORD+'changed'});
  for(const table of Object.keys(fixture)){assert.equal(fixture[table].length,2);assert.ok(isDeepStrictEqual(await rows(table),fixture[table]),table+' fixture survives a second run');}
  assert.deepEqual(fixture.users.map(row=>row.email).sort(),['barbara@example.com','michael@example.com']);
  for(const user of fixture.users){
   const name=user.email.startsWith('barbara')?'Barbara':'Michael';
   assert.ok(await bcrypt.compare(process.env.FIXTURE_PASSWORD,user.password_hash));
   const record=fixture.records.find(row=>row.owner_id===user.id);
   assert.equal(record.title,name+' invoice');assert.equal(record.description,(name==='Barbara'?'First':'Second')+' synthetic record');
   const doc=fixture.documents.find(row=>row.owner_id===user.id);
   assert.equal((await objectBytes(doc.object_key)).toString(),name+' synthetic document\n');
  }
  seed({},['--accounts','1000']);seed({APP_ENV:'development'},['--accounts','1000']);
  const users=await rows('users'),records=await rows('records');
  assert.equal(users.length,1000);assert.equal(records.length,1000);
  const generated=users.filter(row=>row.email.startsWith('test-account-')).sort((a,b)=>a.email.localeCompare(b.email));
  assert.equal(generated.length,998);assert.equal(new Set(generated.map(row=>row.password_hash)).size,1);
  assert.ok(await bcrypt.compare(process.env.FIXTURE_PASSWORD,generated[0].password_hash));
  for(const [index,user] of generated.entries()){
   assert.equal(user.email,'test-account-'+String(index+3).padStart(6,'0')+'@example.com');
   const owned=records.filter(row=>row.owner_id===user.id);assert.equal(owned.length,1);
   assert.equal(owned[0].title,'Test record '+(index+3));assert.equal(owned[0].description,'Generated test record');
  }
  seed({},['--accounts','3']);
  assert.ok(isDeepStrictEqual(await rows('users'),users));assert.ok(isDeepStrictEqual(await rows('records'),records));
  for(const table of ['documents','report_jobs'])assert.ok(isDeepStrictEqual(await rows(table),fixture[table]),table+' remain exact');
  for(const table of ['users','records'])assert.ok(isDeepStrictEqual((await rows(table)).filter(row=>fixture[table].some(old=>old.id===row.id)),fixture[table]),table+' fixed rows remain exact');
  seed({},['--accounts','1200']);
  assert.equal((await rows('users')).length,1200);assert.equal((await rows('records')).length,1200);
  for(const table of ['users','records'])assert.ok(isDeepStrictEqual((await rows(table)).filter(row=>(table==='users'?users:records).some(old=>old.id===row.id)),table==='users'?users:records),'growth preserves existing test rows');
  for(const table of ['documents','report_jobs'])assert.ok(isDeepStrictEqual(await rows(table),fixture[table]));
  await pool.query('INSERT INTO users(id,email,password_hash,email_confirmed_at) VALUES($1,$2,$3,now())',[unrelated,'other-data@example.com','not-a-login']);
  before=await snapshot();files=await objects();
  assert.throws(()=>seed({},['--accounts','1500']),/contains accounts that are not test data/);
  assert.ok(isDeepStrictEqual(await snapshot(),before),'populated refusal leaves all rows unchanged');
  assert.deepEqual(await objects(),files,'populated refusal uploads no objects');
 }finally{
  await pool.end();storage.destroy();
 }
});
