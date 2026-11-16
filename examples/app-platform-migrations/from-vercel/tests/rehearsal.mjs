// Synthetic two-account source rehearsal. Use an empty assigned database/bucket.
import assert from 'node:assert/strict'
import { readFile, mkdtemp, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { setTimeout as pause } from 'node:timers/promises'
import { database, closeDatabase } from '../lib/database.mjs'
import { sha256 } from '../lib/storage.mjs'
import { runDueSchedule } from '../lib/jobs.mjs'

const snapshot=JSON.parse(await readFile(join(process.env.PRIVATE_EXPORT_DIR,'snapshot.json')))
const ports=process.env.TEST_WEB_PORTS.split(',').map(Number)
assert.ok(ports.length===2 && ports.every(p=>p>0))
assert.ok(process.env.FIXTURE_PASSWORD)
assert.equal(snapshot.accounts.length,2,'Use the exported two-account synthetic fixture')
const children=new Set()
const results=[]
function pass(name){results.push(name);console.log('PASS:',name)}
function launch(script,args=[],env={}){
 const child=spawn(process.execPath,[script,...args],{env:{...process.env,...env},stdio:['ignore','inherit','inherit']})
 children.add(child)
 child.completion=once(child,'exit').then(([code,signal])=>{children.delete(child);return {code,signal}})
 return child
}
async function command(script,args=[],env={}) {return (await launch(script,args,env).completion).code}
async function until(fn){const end=Date.now()+20000;while(Date.now()<end){if(await fn())return;await pause(50)}throw new Error('Rehearsal deadline exceeded')}
async function stop(child){child.kill('SIGTERM');const timer=setTimeout(()=>child.kill('SIGKILL'),15000);try{return await child.completion}finally{clearTimeout(timer)}}
async function api(server,path,{cookie,fields,body,status=200}={}){
 const headers={Origin:process.env.APP_ORIGIN};if(cookie)headers.Cookie=cookie
 if(fields)body=new URLSearchParams(fields)
 const r=await fetch(`http://127.0.0.1:${ports[server]}${path}`,{method:body===undefined?'GET':'POST',headers,body,signal:AbortSignal.timeout(18000)})
 assert.equal(r.status,status,`Unexpected HTTP status for ${path}`)
 return r
}
try{
 assert.equal((await database().query("SELECT to_regclass('accounts') AS name")).rows[0].name,null,'Use a fresh database')
 for(let i=0;i<2;i++)assert.equal(await command('scripts/manage.mjs',['migrate']),0)
 assert.equal(await command('scripts/import-snapshot.mjs'),0)
 assert.equal(await command('scripts/import-snapshot.mjs'),0)
 const accountRows=(await database().query('SELECT id,email,password_hash,created_at FROM accounts ORDER BY id')).rows
 // Never let assertion failures print credential values.
 assert.ok(JSON.stringify(accountRows)===JSON.stringify(snapshot.accounts),'Imported identities or native password hashes differ')
 assert.equal((await database().query('SELECT count(*)::int AS n FROM sessions')).rows[0].n,0)
 for(const [table,expected] of [['records',snapshot.records],['documents',snapshot.documents],['report_jobs',snapshot.jobs]]){
  const rows=(await database().query(`SELECT id,account_id FROM ${table} ORDER BY id`)).rows
  assert.ok(rows.length===expected.length && rows.every((r,i)=>r.id===expected[i].id && r.account_id===expected[i].owner_id),'Stable IDs or ownership differ')
 }
 for(const source of snapshot.jobs){
  const row=(await database().query('SELECT output,finished_at,archived_at,created_at FROM report_jobs WHERE id=$1',[source.id])).rows[0]
  assert.ok(row.output===source.output && String(row.finished_at)===String(source.completed_at===null?null:new Date(source.completed_at)),'Job output or completion changed')
  assert.equal(new Date(row.created_at).toISOString(),new Date(source.created_at).toISOString())
 }
 const wrong=await mkdtemp(join(tmpdir(),'different-snapshot-'))
 await writeFile(join(wrong,'snapshot.json'),JSON.stringify({...snapshot,format_version:1,extra:'different snapshot'}),{mode:0o600})
 assert.equal(await command('scripts/import-snapshot.mjs',[],{PRIVATE_EXPORT_DIR:wrong}),1)
 pass('native identities, password hashes, stable IDs, ownership, job state/output, revoked native sessions, safe identical rerun and different-snapshot refusal')
 const webs=ports.map(port=>launch('.next/standalone/scripts/web.mjs',[],{PORT:String(port),WEB_CONCURRENCY:'2'}))
 for(let i=0;i<2;i++)await until(async()=>{try{return(await api(i,'/healthz')).ok}catch{return false}})
 const cookies={}
 for(const a of snapshot.accounts){
  const login=await api(0,'/login',{fields:{email:a.email,password:process.env.FIXTURE_PASSWORD}})
  const cookie=login.headers.get('set-cookie').split(';')[0];cookies[a.id]=cookie
  const records=await(await api(1,'/records',{cookie})).json()
  const expected=snapshot.records.filter(r=>r.owner_id===a.id)
  assert.equal(records.length,expected.length)
  for(const record of expected)assert.ok(records.some(r=>r.id===record.id&&r.title===record.title&&r.description===record.description))
  const reports=await(await api(1,'/reports',{cookie})).json()
  assert.equal(reports.length,snapshot.jobs.filter(j=>j.owner_id===a.id).length)
  for(const d of snapshot.documents.filter(d=>d.owner_id===a.id)){
   const bytes=Buffer.from(await(await api(1,`/documents/${d.id}`,{cookie})).arrayBuffer())
   assert.ok(bytes.length===d.byte_size&&sha256(bytes)===d.sha256,'Downloaded source bytes differ')
  }
 }
 for(const a of snapshot.accounts){
  const foreign=snapshot.records.find(r=>r.owner_id!==a.id)
  const file=snapshot.documents.find(d=>d.owner_id!==a.id)
  for(const action of ['update','delete'])await api(1,`/records/${foreign.id}/${action}`,{cookie:cookies[a.id],fields:{title:'Refused'},status:404})
  await api(1,`/documents/${file.id}`,{cookie:cookies[a.id],status:404})
 }
 pass('existing passwords log in, cross-server sessions, exact source records/downloads and foreign-owner refusals')
 const workers=[launch('scripts/manage.mjs',['jobs']),launch('scripts/manage.mjs',['jobs'])]
 await until(async()=>!(await database().query('SELECT 1 FROM report_jobs WHERE finished_at IS NULL')).rowCount)
 for(const job of snapshot.jobs){
  const row=(await database().query('SELECT output FROM report_jobs WHERE id=$1',[job.id])).rows[0]
  assert.equal(row.output,job.state==='PENDING'?'record_count=1\n':job.output)
 }
 for(const worker of workers)assert.equal((await stop(worker)).code,0)
 pass('two destination workers retain completed output and finish imported pending reports')
 const owner=snapshot.accounts[0]
 const old=(await database().query("INSERT INTO report_jobs(account_id,output,finished_at) VALUES($1,'retained historic output',now()-interval '32 days') RETURNING id",[owner.id])).rows[0]
 assert.equal(await command('scripts/manage.mjs',['archive-reports']),0)
 assert.ok((await database().query('SELECT archived_at FROM report_jobs WHERE id=$1',[old.id])).rows[0].archived_at)
 const before=(await database().query('SELECT count(*)::int AS n FROM scheduled_task_runs WHERE scheduled_for IS NOT NULL')).rows[0].n
 await Promise.all([runDueSchedule(),runDueSchedule()])
 const after=(await database().query('SELECT count(*)::int AS n FROM scheduled_task_runs WHERE scheduled_for IS NOT NULL')).rows[0].n
 assert.ok(after-before<=1)
 pass('replacement archive task preserves output; concurrent UTC scheduler calls produce at most one daily run')
 const cookie=cookies[owner.id]
 const added=await(await api(0,'/records',{cookie,fields:{title:'Rehearsal temporary record'},status:201})).json()
 await api(1,`/records/${added.id}/update`,{cookie,fields:{title:'Rehearsal changed',description:'New destination write'}})
 await api(1,`/records/${added.id}/delete`,{cookie,body:''})
 await api(0,'/logout',{cookie,body:''})
 await api(1,'/records',{cookie,status:401})
 pass('destination CRUD and immediate cross-server logout revocation')
 for(const web of webs)assert.equal((await stop(web)).code,0)
 console.log('REHEARSAL_RESULTS',JSON.stringify(results))
}finally{
 for(const child of [...children])await stop(child)
 await closeDatabase()
}
