import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import bcrypt from 'bcryptjs';
import { pool, migrate, transaction } from '../database.mjs';
import { download } from '../storage.mjs';
if (process.env.REHEARSAL_CONFIRM !== 'disposable-destination' || process.env.APP_ENV !== 'staging') throw new Error('Use a separate empty disposable staging database.');
const appDirectory=new URL('../',import.meta.url);
function seed(env={},args=[]) {execFileSync(process.execPath,['seed_test_data.mjs',...args],{cwd:appDirectory,env:{...process.env,...env},stdio:['ignore','pipe','pipe']});}
test('additive migration, transactional rollback, seed idempotence and production refusal',async()=>{
  try {
    const sql=await readFile(new URL('../migrations/001_initial.sql',import.meta.url),'utf8');
    await pool.query(sql);
    await pool.query('CREATE TABLE schema_migrations(name text PRIMARY KEY,sha256 text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now())');
    await pool.query('INSERT INTO schema_migrations(name,sha256) VALUES($1,$2)',['001_initial.sql',createHash('sha256').update(sql).digest('hex')]);
    const owner=randomUUID(),record=randomUUID();
    await pool.query('INSERT INTO users(id,email,password_hash) VALUES($1,$2,$3)',[owner,'previous-release@example.com',await bcrypt.hash(process.env.FIXTURE_PASSWORD,12)]);
    await pool.query('INSERT INTO records(id,owner_id,title) VALUES($1,$2,$3)',[record,owner,'Existing release record']);
    await migrate();await migrate();
    const row=(await pool.query('SELECT id,owner_id,title,description FROM records WHERE id=$1',[record])).rows[0];
    assert.equal(row.owner_id,owner);assert.equal(row.title,'Existing release record');assert.equal(row.description,'');
    await pool.query('UPDATE records SET title=$2 WHERE id=$1',[record,'Old column query still writes']);
    // Remove only destination test rows before seeding the exact synthetic fixture.
    await pool.query('DELETE FROM records WHERE id=$1',[record]);await pool.query('DELETE FROM users WHERE id=$1',[owner]);
    const rolledBack = randomUUID();
    await assert.rejects(transaction(async client => {
      await client.query('INSERT INTO users(id,email,password_hash) VALUES($1,$2,$3)', [rolledBack,'rollback@example.com','synthetic-unusable-verifier']);
      throw new Error('Deliberate transaction failure.');
    }));
    assert.equal((await pool.query('SELECT id FROM users WHERE id=$1',[rolledBack])).rowCount,0);
    assert.throws(()=>seed({APP_ENV:'production'}), /APP_ENV must be development or staging/);
    assert.throws(()=>seed({APP_ENV:undefined}), /APP_ENV must be development or staging/);
    assert.throws(()=>seed({},['--accounts','1']), /--accounts/);
    assert.throws(()=>seed({},['--accounts','2.5']), /--accounts/);
    seed({APP_ENV:'development'});
    const first={};for(const table of ['users','identities','records','documents','jobs'])first[table]=(await pool.query(`SELECT * FROM ${table} ORDER BY 1`)).rows;
    seed({FIXTURE_PASSWORD:process.env.FIXTURE_PASSWORD+'different'});
    for(const table of Object.keys(first))assert.deepEqual((await pool.query(`SELECT * FROM ${table} ORDER BY 1`)).rows,first[table],table+' seed is idempotent');
    assert.equal(first.users.length,2);assert.equal(first.records.length,2);assert.equal(first.documents.length,2);assert.equal(first.jobs.length,2);
    assert.deepEqual(first.users.map(row=>row.email).sort(),['barbara@example.com','michael@example.com']);
    for(const user of first.users){
      const name=user.email.startsWith('barbara')?'Barbara':'Michael';
      const record=first.records.find(row=>row.owner_id===user.id);
      assert.equal(record.title,name+' invoice');
      assert.equal(record.description,name==='Barbara'?'First synthetic record':'Second synthetic record');
      assert.equal(user.is_admin,name==='Barbara');
    }
    for(const user of first.users)assert.ok(await bcrypt.compare(process.env.FIXTURE_PASSWORD,user.password_hash));
    for(const doc of first.documents){const bytes=await download(doc.object_key);assert.equal(createHash('sha256').update(bytes).digest('hex'),doc.sha256);assert.equal(bytes.length,27);}
    seed({},['--accounts','1000']);
    seed({APP_ENV:'development'},['--accounts','1000']);
    assert.equal((await pool.query('SELECT count(*)::int AS n FROM users')).rows[0].n,1000);
    assert.equal((await pool.query('SELECT count(*)::int AS n FROM records')).rows[0].n,1000);
    assert.equal((await pool.query('SELECT count(*)::int AS n FROM identities')).rows[0].n,1000);
    const generated=(await pool.query("SELECT u.email,u.password_hash,r.title,r.description FROM users u JOIN records r ON r.owner_id=u.id WHERE u.email LIKE 'test-account-%' ORDER BY u.email")).rows;
    assert.equal(generated.length,998);
    assert.equal(generated[0].email,'test-account-000003@example.com');
    assert.equal(generated.at(-1).email,'test-account-001000@example.com');
    assert.equal(new Set(generated.map(row=>row.password_hash)).size,1);
    assert.ok(await bcrypt.compare(process.env.FIXTURE_PASSWORD,generated[0].password_hash));
    for(const [index,row] of generated.entries()){assert.equal(row.title,'Test record '+(index+3));assert.equal(row.description,'Generated test record');}
    seed({},['--accounts','3']);
    for(const table of ['documents','jobs']) assert.deepEqual((await pool.query(`SELECT * FROM ${table} ORDER BY 1`)).rows,first[table]);
    for(const table of ['users','records']) assert.deepEqual((await pool.query(`SELECT * FROM ${table} WHERE ${table==='users'?'id':'owner_id'}=ANY($1::uuid[]) ORDER BY 1`,[first.users.map(row=>row.id)])).rows,first[table]);
    assert.equal((await pool.query('SELECT count(*)::int AS n FROM users')).rows[0].n,1000);
    assert.equal((await pool.query('SELECT count(*)::int AS n FROM schema_migrations')).rows[0].n,2);
  } finally {await pool.end();}
});
