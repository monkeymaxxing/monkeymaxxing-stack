// Run only against an empty, assigned test database and private test bucket.
// This script starts and stops only its own child processes. It retains data.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { setTimeout as pause } from 'node:timers/promises'
import { randomBytes } from 'node:crypto'
import { database, closeDatabase } from '../lib/database.mjs'

const origin = process.env.APP_ORIGIN
const ports = (process.env.TEST_WEB_PORTS || '').split(',').map(Number)
assert.equal(ports.length, 2, 'Set TEST_WEB_PORTS to two assigned ports')
assert.ok(ports.every(port => port > 0))
assert.ok(process.env.FIXTURE_PASSWORD)
const bases = ports.map(port => `http://127.0.0.1:${port}`)
const children = new Set()
const results = []
let lock
function pass(name, detail) { results.push({ name, detail }); console.log('PASS:', name, detail || '') }
async function until(action, message, timeout = 15000) {
  const end = Date.now() + timeout
  while (Date.now() < end) {
    const result = await action()
    if (result) return result
    await pause(50)
  }
  throw new Error(message)
}
function launch(script, args = [], env = {}) {
  const child = spawn(process.execPath, [script, ...args], { env: { ...process.env, ...env }, stdio: ['ignore', 'inherit', 'inherit'] })
  children.add(child)
  child.completion = once(child, 'exit').then(([code, signal]) => { children.delete(child); return { code, signal } })
  return child
}
async function command(name, env, args = []) {
  const result = await launch('scripts/manage.mjs', [name, ...args], env).completion
  return result.code
}
async function stop(child, signal = 'SIGTERM') {
  child.kill(signal)
  let timer
  try {
    return await Promise.race([child.completion, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Child failed to stop')), 15000) })])
  } finally { clearTimeout(timer) }
}
async function api(server, path, { cookie, fields, body, expected = 200, requestOrigin = origin } = {}) {
  const headers = { Origin: requestOrigin }
  if (cookie) headers.Cookie = cookie
  if (fields) body = new URLSearchParams(fields)
  const response = await fetch(bases[server] + path, { method: body !== undefined ? 'POST' : 'GET', headers, body, signal: AbortSignal.timeout(18000) })
  assert.equal(response.status, expected, `${path}: HTTP ${response.status}`)
  assert.equal(response.headers.get('cache-control'), 'no-store')
  return response
}
async function login(email, server = 0) {
  const response = await api(server, '/login', { fields: { email, password: process.env.FIXTURE_PASSWORD } })
  const cookie = response.headers.get('set-cookie')
  for (const flag of ['Secure', 'HttpOnly', 'SameSite=Lax', 'Path=/']) assert.ok(cookie.includes(flag))
  return cookie.split(';')[0]
}
async function waitingOn(prefix) {
  return until(async () => (await database().query("SELECT pid FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE $1", [prefix + '%'])).rowCount > 0, 'No transaction reached the expected lock')
}
async function holdRecords() {
  lock = await database().connect()
  await lock.query('BEGIN')
  await lock.query('LOCK TABLE records IN ACCESS EXCLUSIVE MODE')
}
async function unlock() {
  if (!lock) return
  await lock.query('ROLLBACK')
  lock.release(); lock = null
}

try {
  assert.equal((await database().query("SELECT to_regclass('accounts') AS table_name")).rows[0].table_name, null, 'Use a fresh database')
  const webA = launch('scripts/web.mjs', [], { PORT: String(ports[0]), WEB_CONCURRENCY: '2' })
  await until(async () => { try { return (await fetch(bases[0] + '/healthz')).status === 503 } catch { return false } }, 'Unmigrated database did not refuse health')
  pass('empty-database health refusal')
  assert.equal(await command('migrate'), 0)
  assert.equal(await command('migrate'), 0)
  assert.equal((await database().query('SELECT count(*)::int AS count FROM schema_migrations')).rows[0].count, 2)
  pass('ordered migration idempotence')
  // Exercise the previous title-only SQL shape across the additive migration.
  await database().query('ALTER TABLE records DROP COLUMN description')
  await database().query("DELETE FROM schema_migrations WHERE version='0002_record_descriptions.sql'")
  await database().query("INSERT INTO accounts(email,password_hash) VALUES('old-release@example.com','not-a-login')")
  await database().query("INSERT INTO records(account_id,title) SELECT id,'Old release record' FROM accounts WHERE email='old-release@example.com'")
  assert.equal(await command('migrate'), 0)
  assert.equal((await database().query("SELECT description FROM records WHERE title='Old release record'")).rows[0].description, '')
  await database().query("INSERT INTO records(account_id,title) SELECT id,'Old release after migration' FROM accounts WHERE email='old-release@example.com'")
  pass('additive migration preserves title-only reader/writer SQL')
  for (const APP_ENV of ['production', undefined]) assert.equal(await command('seed-test-data', { APP_ENV }), 1)
  for (const count of ['1','2.5']) assert.equal(await command('seed-test-data', undefined, ['--accounts',count]), 1)
  assert.equal(await command('seed-test-data', {APP_ENV:'development'}), 0)
  const fixedRows = {}
  for (const table of ['accounts','records','documents','report_jobs']) fixedRows[table] = (await database().query(`SELECT to_jsonb(t) AS row FROM ${table} t ORDER BY id`)).rows
  async function assertFixedRows() {
    for (const [table,rows] of Object.entries(fixedRows)) assert.deepEqual((await database().query(`SELECT to_jsonb(t) AS row FROM ${table} t WHERE id = ANY($1) ORDER BY id`, [rows.map(value=>value.row.id)])).rows, rows, table+' fixed rows remain exact')
  }
  assert.equal(await command('seed-test-data'), 0)
  await assertFixedRows()
  assert.equal(await command('seed-test-data', {FIXTURE_PASSWORD:process.env.FIXTURE_PASSWORD+'changed'}), 0)
  await assertFixedRows()
  for (const table of ['documents', 'report_jobs']) assert.equal((await database().query(`SELECT count(*)::int AS count FROM ${table}`)).rows[0].count, 2)
  const fixture = (await database().query("SELECT a.email,r.title,r.description,d.file_name,d.sha256 FROM accounts a JOIN records r ON r.account_id=a.id JOIN documents d ON d.account_id=a.id ORDER BY a.email")).rows
  const { createHash } = await import('node:crypto')
  assert.deepEqual(fixture, ['Barbara','Michael'].map((name,index) => ({email:name.toLowerCase()+'@example.com',title:name+' invoice',description:['First','Second'][index]+' synthetic record',file_name:name.toLowerCase()+'-note.txt',sha256:createHash('sha256').update(name+' synthetic document\n').digest('hex')})))
  for (const count of ['1000','1000','2']) {
    assert.equal(await command('seed-test-data', undefined, ['--accounts',count]), 0)
    await assertFixedRows()
  }
  for (const [table,count] of [['accounts',1001],['records',1002],['documents',2],['report_jobs',2]]) assert.equal((await database().query(`SELECT count(*)::int AS count FROM ${table}`)).rows[0].count,count)
  assert.equal((await database().query("SELECT count(*)::int AS count FROM records r JOIN accounts a ON a.id=r.account_id WHERE a.email LIKE 'test-account-%@example.com' AND r.description='Generated test record' AND r.title='Test record ' || substring(a.email from '[0-9]+')::bigint::text")).rows[0].count,998)
  assert.equal((await database().query("SELECT count(DISTINCT password_hash)::int AS count FROM accounts WHERE email LIKE 'test-account-%@example.com'")).rows[0].count,1)
  pass('staging seed idempotence, password preservation, production refusal')
  const webB = launch('scripts/web.mjs', [], { PORT: String(ports[1]), WEB_CONCURRENCY: '2' })
  for (const base of bases) await until(async () => { try { return (await fetch(base + '/healthz')).ok } catch { return false } }, 'Web server failed to start')
  const home = await fetch(bases[0])
  assert.ok((await home.text()).includes('Private customer portal'))
  pass('TanStack Start Node server, configured ports, clustered workers')
  const barbara = await login('barbara@example.com')
  const michael = await login('michael@example.com', 1)
  await api(1, '/records', { cookie: barbara })
  await api(1, '/login', { fields: { email: 'barbara@example.com', password: 'wrong-password-value' }, expected: 401 })
  await api(0, '/records', { expected: 401 })
  const suffix = randomBytes(8).toString('hex')
  await api(0, '/register', { fields: { email: `register-${suffix}@example.com`, password: process.env.FIXTURE_PASSWORD } })
  await api(0, '/records', { cookie: barbara, fields: { title: 'CSRF' }, requestOrigin: 'https://evil.example.com', expected: 403 })
  const original = (await (await api(0, '/records', { cookie: barbara })).json())[0]
  for (const action of ['update', 'delete']) await api(1, `/records/${original.id}/${action}`, { cookie: michael, fields: { title: 'stolen' }, expected: 404 })
  const added = await (await api(0, '/records', { cookie: barbara, fields: { title: 'Temporary', description: 'Synthetic' }, expected: 201 })).json()
  await api(1, `/records/${added.id}/update`, { cookie: barbara, fields: { title: 'Changed', description: 'Retained' } })
  assert.ok((await (await api(0, '/records', { cookie: barbara })).json()).some(row => row.title === 'Changed' && row.description === 'Retained'))
  await api(0, `/records/${added.id}/delete`, { cookie: barbara, body: '' })
  pass('login, registration, ownership, origin checks, two-process sessions, CRUD')
  const fixtureDocuments = await (await api(0, '/documents', { cookie: barbara })).json()
  assert.equal(await (await api(1, `/documents/${fixtureDocuments[0].id}`, { cookie: barbara })).text(), 'Barbara synthetic document\n')
  const bytes = Buffer.from([0, 1, 2, 255, 13, 10, ...Buffer.from('Synthetic private bytes')])
  const upload = new FormData(); upload.set('file', new Blob([bytes]), 'binary-note.bin')
  const document = await (await api(0, '/documents', { cookie: barbara, body: upload, expected: 201 })).json()
  assert.deepEqual(Buffer.from(await (await api(1, `/documents/${document.id}`, { cookie: barbara })).arrayBuffer()), bytes)
  await api(1, `/documents/${document.id}`, { cookie: michael, expected: 404 })
  pass('private S3 upload/download byte equality and ownership refusal')
  const firstWorker = launch('scripts/manage.mjs', ['jobs'])
  const secondWorker = launch('scripts/manage.mjs', ['jobs'])
  await until(async () => (await database().query('SELECT 1 FROM report_jobs WHERE finished_at IS NULL')).rowCount === 0, 'Fixture jobs did not complete')
  assert.ok((await database().query('SELECT output FROM report_jobs')).rows.every(row => row.output === 'record_count=1\n'))
  await database().query("INSERT INTO report_jobs(account_id) SELECT a.id FROM accounts a CROSS JOIN generate_series(1,10) WHERE email IN ('barbara@example.com','michael@example.com')")
  await until(async () => (await database().query('SELECT 1 FROM report_jobs WHERE finished_at IS NULL')).rowCount === 0, 'Concurrent jobs did not complete')
  assert.equal((await database().query("SELECT count(*)::int AS count FROM report_jobs WHERE output=E'record_count=1\n'")).rows[0].count, 22)
  assert.equal((await stop(firstWorker)).code, 0)
  assert.equal((await stop(secondWorker)).code, 0)
  pass('two workers finish 22 owned reports with committed output')
  await holdRecords()
  const interruptedJob = (await database().query("INSERT INTO report_jobs(account_id) SELECT id FROM accounts WHERE email='barbara@example.com' RETURNING id")).rows[0].id
  const interruptedWorker = launch('scripts/manage.mjs', ['jobs'])
  await waitingOn('SELECT count(*) AS count FROM records')
  await stop(interruptedWorker, 'SIGKILL')
  const recoveryWorker = launch('scripts/manage.mjs', ['jobs'])
  await unlock()
  await until(async () => (await database().query('SELECT output FROM report_jobs WHERE id=$1', [interruptedJob])).rows[0].output === 'record_count=1\n', 'Interrupted job was lost')
  assert.equal((await stop(recoveryWorker)).code, 0)
  pass('killed worker rolls back and another worker completes the waiting job')
  await holdRecords()
  const gracefulJob = (await database().query("INSERT INTO report_jobs(account_id) SELECT id FROM accounts WHERE email='barbara@example.com' RETURNING id")).rows[0].id
  const gracefulWorker = launch('scripts/manage.mjs', ['jobs'])
  await waitingOn('SELECT count(*) AS count FROM records')
  gracefulWorker.kill('SIGTERM')
  await unlock()
  assert.equal((await gracefulWorker.completion).code, 0)
  assert.equal((await database().query('SELECT output FROM report_jobs WHERE id=$1', [gracefulJob])).rows[0].output, 'record_count=1\n')
  pass('job SIGTERM completes the active transaction')
  const healthLock = await database().connect()
  await healthLock.query('BEGIN'); await healthLock.query('LOCK TABLE schema_migrations IN ACCESS EXCLUSIVE MODE')
  const healthStart = performance.now()
  await api(1, '/healthz', { expected: 503 })
  const healthMs = performance.now() - healthStart
  assert.ok(healthMs < 2500)
  await healthLock.query('ROLLBACK'); healthLock.release()
  pass('health SQL deadline', Math.round(healthMs) + 'ms')
  if (process.env.TEST_DATABASE_RESTART_ARGV) {
    const restartArgv = JSON.parse(process.env.TEST_DATABASE_RESTART_ARGV)
    const before = [webA.pid, webB.pid]
    const start = performance.now()
    const restart = spawn(restartArgv[0], restartArgv.slice(1), { stdio: 'inherit' })
    const [code] = await once(restart, 'exit'); assert.equal(code, 0)
    await until(async () => { try { return (await fetch(bases[0] + '/healthz')).ok } catch { return false } }, 'Database reconnection failed')
    await api(1, '/records', { cookie: barbara, fields: { title: 'After database restart' }, expected: 201 })
    await api(0, `/records/${original.id}/delete`, { cookie: michael, body: '', expected: 404 })
    assert.deepEqual([webA.pid, webB.pid], before)
    assert.ok(webA.exitCode === null && webB.exitCode === null)
    pass('database restart reconnects without changing URLs or web processes', Math.round(performance.now() - start) + 'ms including restart')
  }
  await api(0, '/logout', { cookie: michael, body: '' })
  await api(1, '/records', { cookie: michael, expected: 401 })
  await login('michael@example.com', 1)
  pass('cross-process logout revocation and fresh login')
  await holdRecords()
  const pendingWrite = api(0, '/records', { cookie: barbara, fields: { title: 'Write drained during shutdown' }, expected: 201 })
  await waitingOn('INSERT INTO records')
  webA.kill('SIGTERM')
  await unlock()
  await pendingWrite
  assert.equal((await webA.completion).code, 0)
  assert.equal((await stop(webB)).code, 0)
  pass('cluster SIGTERM drains an in-flight HTTP mutation')
  console.log('SERVICE_RESULTS', JSON.stringify(results))
} finally {
  await unlock().catch(() => {})
  for (const child of [...children]) await stop(child).catch(() => { child.kill('SIGKILL') })
  await closeDatabase()
}
