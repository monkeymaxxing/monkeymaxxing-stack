import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { isDeepStrictEqual } from 'node:util';
import bcrypt from 'bcryptjs';
import { pool, migrate } from '../database.mjs';
import { getObject } from '../storage.mjs';

if(process.env.REHEARSAL_CONFIRM!=='disposable-destination')throw Error('Use a disposable empty database and bucket.');
const directory=new URL('../',import.meta.url),base='http://127.0.0.1:18021';
function seed(env={},args=[]){execFileSync(process.execPath,['seed-test-data.mjs',...args],{cwd:directory,env:{...process.env,APP_URL:base,APP_ENV:'staging',...env},stdio:['ignore','pipe','pipe']});}
async function rows(table){return (await pool.query(`SELECT * FROM ${table} ORDER BY id`)).rows;}
async function databaseRows(){
 const data={};
 for(const {tablename} of (await pool.query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).rows)
  data[tablename]=(await pool.query('SELECT to_jsonb(t) AS row FROM "'+tablename.replaceAll('"','""')+'" t ORDER BY to_jsonb(t)::text')).rows;
 return data;
}
test('test data works on laptops and staging, preserves fixtures and grows accounts in bulk',async()=>{
 let server;
 try{
  assert.throws(()=>seed({APP_ENV:'production'}),/APP_ENV must be development or staging/);
  assert.throws(()=>seed({APP_ENV:undefined}),/APP_ENV must be development or staging/);
  await migrate();
  server=spawn(process.execPath,['web.mjs'],{cwd:directory,env:{...process.env,PORT:'18021',WEB_CONCURRENCY:'1',COOKIE_SECURE:'false'},stdio:'ignore'});
  let ready=false;
  for(let i=0;i<100;i++){try{if((await fetch(base+'/healthz')).ok){ready=true;break;}}catch{}await new Promise(resolve=>setTimeout(resolve,50));}
  assert.ok(ready,'seed test web process is ready');
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
  seed();
  for(const table of Object.keys(fixture)){assert.equal(fixture[table].length,2);assert.ok(isDeepStrictEqual(await rows(table),fixture[table]),table+' fixture survives a second run');}
  assert.deepEqual(fixture.users.map(row=>row.email).sort(),['barbara@example.com','michael@example.com']);
  for(const user of fixture.users){
   const name=user.email.startsWith('barbara')?'Barbara':'Michael';
   assert.ok(await bcrypt.compare(process.env.FIXTURE_PASSWORD,user.password_hash));
   const record=fixture.records.find(row=>row.owner_id===user.id);
   assert.equal(record.title,name+' invoice');assert.equal(record.description,(name==='Barbara'?'First':'Second')+' synthetic record');
   const doc=fixture.documents.find(row=>row.owner_id===user.id);
   assert.equal((await getObject(doc.object_key)).toString(),name+' synthetic document\n');
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
 }finally{
  if(server&&server.exitCode===null){const ended=once(server,'exit');server.kill('SIGTERM');await ended;}
  await pool.end();
 }
});
