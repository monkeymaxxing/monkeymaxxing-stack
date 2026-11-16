import { readFile, readdir } from 'node:fs/promises'
import { setTimeout as delay } from 'node:timers/promises'
import { transaction, closeDatabase } from '../lib/database.mjs'
import { credentials, passwordHash } from '../lib/accounts.mjs'
import { putDocument } from '../lib/storage.mjs'
import { runOneJob } from '../lib/jobs.mjs'

const command=process.argv[2]
try {
  if(command==='migrate') {
    const through=process.argv[3]==='--through' ? Number(process.argv[4]) : 2
    if(![1,2].includes(through)) throw new Error('--through must be 1 or 2')
    await transaction(async client=>{
      await client.query('SELECT pg_advisory_xact_lock(20261104)')
      await client.query('CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY)')
      const dir=new URL('../migrations/',import.meta.url)
      for(const name of (await readdir(dir)).filter(n=>/^\d{4}_.+\.sql$/.test(n)).sort()) {
        if(Number(name.slice(0,4))>through) continue
        if((await client.query('SELECT 1 FROM schema_migrations WHERE version=$1',[name])).rows.length) continue
        await client.query(await readFile(new URL(name,dir),'utf8'))
        await client.query('INSERT INTO schema_migrations VALUES($1)',[name])
        console.log('Applied '+name)
      }
    })
  } else if(command==='seed-test-data') {
    if(!['development','staging'].includes(process.env.APP_ENV)) throw new Error('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data')
    const args=process.argv.slice(3)
    const accounts=args.length===0 ? '2' : args.length===2 && args[0]==='--accounts' ? args[1] : ''
    if(!/^[0-9]+$/.test(accounts) || BigInt(accounts)<2n) throw new Error('Usage: seed-test-data [--accounts N], where N is a whole number of at least 2')
    const {password}=credentials({email:'fixture@example.com',password:process.env.FIXTURE_PASSWORD})
    const hash=await passwordHash(password)
    await transaction(async client=>{
      await client.query('SELECT pg_advisory_xact_lock(20261105)')
      for(const [slug,name,ordinal] of [['barbara','Barbara','First'],['michael','Michael','Second']]) {
        await client.query('INSERT INTO accounts(email,password_hash) VALUES($1,$2) ON CONFLICT(email) DO NOTHING',[slug+'@example.com',hash])
        const owner=(await client.query('SELECT id FROM accounts WHERE email=$1',[slug+'@example.com'])).rows[0].id
        if(!(await client.query('SELECT 1 FROM records WHERE account_id=$1',[owner])).rows.length) await client.query('INSERT INTO records(account_id,title,description) VALUES($1,$2,$3)',[owner,name+' invoice',ordinal+' synthetic record'])
        const key='fixture/'+slug+'-note.txt'
        if(!(await client.query('SELECT 1 FROM documents WHERE object_key=$1',[key])).rows.length) {
          const document=await putDocument(owner,slug+'-note.txt',Buffer.from(name+' synthetic document\n'),key)
          await client.query('INSERT INTO documents(account_id,object_key,filename,sha256,byte_count) VALUES($1,$2,$3,$4,$5)',[owner,key,document.filename,document.sha256,document.byteCount])
        }
        await client.query('INSERT INTO report_jobs(account_id,fixture_key) VALUES($1,$2) ON CONFLICT(fixture_key) DO NOTHING',[owner,slug])
      }
      await client.query(`INSERT INTO accounts(email,password_hash)
        SELECT 'test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com',$2
        FROM generate_series(3,$1::bigint) AS n ON CONFLICT(email) DO NOTHING`,[accounts,hash])
      await client.query(`INSERT INTO records(account_id,title,description)
        SELECT a.id,'Test record ' || n::text,'Generated test record'
        FROM generate_series(3,$1::bigint) AS n
        JOIN accounts a ON a.email='test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com'
        WHERE NOT EXISTS(SELECT 1 FROM records r WHERE r.account_id=a.id)`,[accounts])
    })
    console.log('Synthetic fixture ready')
  } else if(command==='jobs') {
    let stopping=false
    const stop=()=>{stopping=true}
    process.on('SIGTERM',stop);process.on('SIGINT',stop)
    while(!stopping) {
      try { if(!await runOneJob()) await delay(200) }
      catch { console.error('Job database unavailable; unfinished transactions remain queued');await delay(500) }
    }
  } else throw new Error('Usage: bin/portal web|migrate|jobs|seed-test-data')
} finally { await closeDatabase() }
