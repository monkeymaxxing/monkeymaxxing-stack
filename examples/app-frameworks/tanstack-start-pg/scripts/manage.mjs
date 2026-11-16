import { readdir, readFile } from 'node:fs/promises'
import { setTimeout as pause } from 'node:timers/promises'
import { database, transaction, closeDatabase } from '../lib/database.mjs'
import { passwordHash, validPassword } from '../lib/accounts.mjs'
import { putDocument } from '../lib/storage.mjs'
import { runOneJob } from '../lib/jobs.mjs'

async function migrate() {
  await transaction(async client => {
    await client.query("SET LOCAL lock_timeout = '5s'")
    await client.query('SELECT pg_advisory_xact_lock(61409328)')
    await client.query('CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
    const directory = new URL('../migrations/', import.meta.url)
    for (const version of (await readdir(directory)).filter(name => /^\d{4}_.*\.sql$/.test(name)).sort()) {
      if ((await client.query('SELECT 1 FROM schema_migrations WHERE version=$1', [version])).rowCount) continue
      await client.query(await readFile(new URL(version, directory), 'utf8'))
      await client.query('INSERT INTO schema_migrations(version) VALUES($1)', [version])
    }
  })
  console.log('Migrations are current')
}

async function seed() {
  if (!['development','staging'].includes(process.env.APP_ENV)) throw new Error('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data')
  const args=process.argv.slice(3)
  const accounts=args.length===0 ? '2' : args.length===2 && args[0]==='--accounts' ? args[1] : ''
  if (!/^[0-9]+$/.test(accounts) || BigInt(accounts)<2n) throw new Error('Usage: seed-test-data [--accounts N], where N is a whole number of at least 2')
  if (!validPassword(process.env.FIXTURE_PASSWORD)) throw new Error('FIXTURE_PASSWORD must be 12 to 72 bytes')
  const hash=await passwordHash(process.env.FIXTURE_PASSWORD)
  await transaction(async client => {
    await client.query('SELECT pg_advisory_xact_lock(61409329)')
    for (const [name, description] of [['Barbara', 'First synthetic record'], ['Michael', 'Second synthetic record']]) {
      const email = `${name.toLowerCase()}@example.com`
      await client.query('INSERT INTO accounts(email,password_hash) VALUES($1,$2) ON CONFLICT(email) DO NOTHING', [email, hash])
      const account = (await client.query('SELECT id FROM accounts WHERE email=$1', [email])).rows[0]
      const title = `${name} invoice`
      await client.query('INSERT INTO records(account_id,title,description) SELECT $1,$2,$3 WHERE NOT EXISTS(SELECT 1 FROM records WHERE account_id=$1 AND title=$2)', [account.id, title, description])
      const fileName = `${name.toLowerCase()}-note.txt`
      const key = `fixtures/${fileName}`
      if (!(await client.query('SELECT 1 FROM documents WHERE object_key=$1', [key])).rowCount) {
        const doc = await putDocument(account.id, fileName, Buffer.from(`${name} synthetic document\n`), key)
        await client.query('INSERT INTO documents(account_id,object_key,file_name,sha256,byte_count) VALUES($1,$2,$3,$4,$5)', [account.id, key, fileName, doc.sha256, doc.byteCount])
      }
      await client.query('INSERT INTO report_jobs(account_id,fixture_key) VALUES($1,$2) ON CONFLICT(fixture_key) DO NOTHING', [account.id, email])
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
  console.log('Synthetic fixture is ready')
}

async function jobs() {
  let stopping = false
  const controller = new AbortController()
  function stop() { stopping = true; controller.abort() }
  process.once('SIGTERM', stop)
  process.once('SIGINT', stop)
  while (!stopping) {
    try {
      const worked = await runOneJob()
      if (worked) continue
    } catch (error) {
      // Each transaction has failed visibly. Only the next queue poll starts
      // fresh work; no request or uncertain transaction is replayed.
      console.error('Job transaction failed', error.code || error.name)
    }
    if (!stopping) await pause(250, undefined, { signal: controller.signal }).catch(() => {})
  }
}

try {
  const command = process.argv[2]
  if (command === 'migrate') await migrate()
  else if (command === 'seed-test-data') await seed()
  else if (command === 'jobs') await jobs()
  else throw new Error('Use migrate, jobs, or seed-test-data')
} catch (error) {
  console.error('Command failed', process.argv[2] === 'seed-test-data' ? error.message : error.code || error.name)
  process.exitCode = 1
} finally {
  await closeDatabase()
}
