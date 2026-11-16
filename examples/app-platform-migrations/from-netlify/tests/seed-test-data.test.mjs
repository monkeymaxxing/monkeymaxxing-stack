import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { isDeepStrictEqual } from 'node:util';
import bcrypt from 'bcryptjs';
import { pool, migrate } from '../database.mjs';
import { download } from '../storage.mjs';

if(process.env.REHEARSAL_CONFIRM!=='disposable-destination')throw Error('Use a disposable empty database and bucket.');
const directory=new URL('../',import.meta.url);
function seed(env={},args=[]){execFileSync(process.execPath,['seed_test_data.mjs',...args],{cwd:directory,env:{...process.env,APP_ENV:'staging',...env},stdio:['ignore','pipe','pipe']});}
async function rows(table){return (await pool.query(`SELECT * FROM ${table} ORDER BY ${table==='identities'?'issuer,subject':'id'}`)).rows;}
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
  await migrate();
  seed({APP_ENV:'development'});
  const fixture={};for(const table of ['users','identities','records','documents','jobs'])fixture[table]=await rows(table);
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
   assert.equal(user.password_hash,null);
   const record=fixture.records.find(row=>row.owner_id===user.id);
   assert.equal(record.title,name+' invoice');assert.equal(record.description,(name==='Barbara'?'First':'Second')+' synthetic record');
   const doc=fixture.documents.find(row=>row.owner_id===user.id);
   assert.equal((await download(doc.object_key)).toString(),name+' synthetic document\n');
  }
  seed({},['--accounts','1000']);seed({APP_ENV:'development'},['--accounts','1000']);
  const users=await rows('users'),records=await rows('records');
  assert.equal(users.length,1000);assert.equal(records.length,1000);
  assert.equal((await pool.query('SELECT count(*)::int AS n FROM identities')).rows[0].n,1000);
  const generated=users.filter(row=>row.email.startsWith('test-account-')).sort((a,b)=>a.email.localeCompare(b.email));
  assert.equal(generated.length,998);assert.equal(new Set(generated.map(row=>row.password_hash)).size,1);
  for(const user of generated)assert.equal(user.password_hash,null);
  for(const [index,user] of generated.entries()){
   assert.equal(user.email,'test-account-'+String(index+3).padStart(6,'0')+'@example.com');
   const owned=records.filter(row=>row.owner_id===user.id);assert.equal(owned.length,1);
   assert.equal(owned[0].title,'Test record '+(index+3));assert.equal(owned[0].description,'Generated test record');
  }
  seed({},['--accounts','3']);
  assert.ok(isDeepStrictEqual(await rows('users'),users));assert.ok(isDeepStrictEqual(await rows('records'),records));
  for(const table of ['documents','jobs'])assert.ok(isDeepStrictEqual(await rows(table),fixture[table]),table+' remain exact');
  for(const table of ['users','records'])assert.ok(isDeepStrictEqual((await rows(table)).filter(row=>fixture[table].some(old=>old.id===row.id)),fixture[table]),table+' fixed rows remain exact');
  const chosenHash=await bcrypt.hash('Chosen-test-password-for-reset',12);
  await pool.query('UPDATE users SET password_hash=$2 WHERE id=$1',[fixture.users[0].id,chosenHash]);
  seed({APP_ENV:'development'});
  assert.equal((await pool.query('SELECT password_hash FROM users WHERE id=$1',[fixture.users[0].id])).rows[0].password_hash,chosenHash,'rerun preserves a chosen password');
 }finally{
  await pool.end();
 }
});
