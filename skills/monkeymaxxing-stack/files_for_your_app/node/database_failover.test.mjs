// Tests of the three files beside this one, against a Postgres primary and a
// streaming standby that the tests start on this machine, on free ports of
// 127.0.0.1, and switch over as pg_auto_failover does: stop the primary,
// promote the standby, then start the old primary as a standby of the new
// one. They need Node 22.12 or later and Postgres's server programs on PATH
// (initdb, pg_ctl, pg_basebackup, pg_rewind; tested with Postgres 18):
//
//   npm ci
//   PATH="$(brew --prefix postgresql@18)/bin:$PATH" npm test        # macOS, Homebrew
//   PATH="/usr/lib/postgresql/18/bin:$PATH" npm test                # Debian, Ubuntu
//
// They take about 15 seconds, and remove their servers' directory at the
// end.
import { describe, it, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { execFile, spawn } from 'node:child_process'
import { mkdtemp, writeFile, appendFile, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { promisify } from 'node:util'
import net from 'node:net'
import pg from 'pg'
import { poolForDatabaseUrl, clientClassForDatabaseUrl, singleServerDatabaseUrl } from './pg_with_multiple_database_servers.mjs'

const runProgram = promisify(execFile)
const thisDirectory = import.meta.dirname
const superuserPassword = 'test_superuser_password'
const appPassword = 'test_shop_password'

let directory
let first // the primary at the start
let second // the standby at the start
let refusedPort // nothing listens there
let silentServer // accepts connections and never answers, as a server that hangs
let primary
let standby

async function freePort() {
  const server = net.createServer()
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const { port } = server.address()
  await new Promise((resolve) => server.close(resolve))
  return port
}

async function asSuperuser(server, sql) {
  const client = new pg.Client({ host: '127.0.0.1', port: server.port, user: 'postgres', password: superuserPassword, database: 'postgres' })
  await client.connect()
  try {
    return (await client.query(sql)).rows
  } finally {
    await client.end()
  }
}

async function startServer(server) {
  try {
    await runProgram('pg_ctl', ['--pgdata', server.dataDirectory, '--log', server.logFile, '--wait', '-o', `-p ${server.port}`, 'start'])
  } catch (error) {
    throw new Error(`Postgres didn't start on port ${server.port}:\n${await readFile(server.logFile, 'utf8')}`)
  }
}

async function stopServer(server) {
  await runProgram('pg_ctl', ['--pgdata', server.dataDirectory, '--mode', 'fast', '--wait', 'stop'])
}

async function waitUntil(description, condition) {
  const giveUpAt = Date.now() + 30_000
  while (!(await condition().catch(() => false))) {
    if (Date.now() > giveUpAt) throw new Error(`Gave up waiting until ${description}`)
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
}

async function waitUntilStreaming(from, to) {
  await waitUntil(`port ${to.port} streams from port ${from.port}`, async () =>
    (await asSuperuser(from, "select count(*) = 1 as streaming from pg_stat_replication where state = 'streaming'"))[0].streaming)
}

// As pg_auto_failover switches over: the primary stops, which ends its
// connections; for a moment no server is the primary; the standby is
// promoted; and the old primary comes back as a standby of the new one.
async function switchOver() {
  const [oldPrimary, newPrimary] = [primary, standby]
  await stopServer(oldPrimary)
  await new Promise((resolve) => setTimeout(resolve, 1000))
  await runProgram('pg_ctl', ['--pgdata', newPrimary.dataDirectory, '--wait', 'promote'])
  await asSuperuser(newPrimary, 'checkpoint')
  await runProgram('pg_rewind', ['--target-pgdata', oldPrimary.dataDirectory, '--write-recovery-conf',
    '--source-server', `host=127.0.0.1 port=${newPrimary.port} user=postgres password=${superuserPassword} dbname=postgres`])
  await startServer(oldPrimary)
  await waitUntilStreaming(newPrimary, oldPrimary)
  ;[primary, standby] = [newPrimary, oldPrimary]
}

function databaseUrl(ports, targetSessionAttrs, otherSettings = '') {
  const servers = ports.map((port) => `127.0.0.1:${port}`).join(',')
  return `postgresql://shop:${appPassword}@${servers}/shop?target_session_attrs=${targetSessionAttrs}&connect_timeout=1${otherSettings}`
}

// Which server a new connection reached, as that server itself says.
async function serverOfANewConnection(url) {
  const Client = clientClassForDatabaseUrl(url)
  const client = new Client()
  await client.connect()
  try {
    const { rows } = await client.query('select inet_server_port() as port, pg_is_in_recovery() as standby')
    return rows[0]
  } finally {
    await client.end()
  }
}

before(async () => {
  try {
    await runProgram('initdb', ['--version'])
  } catch {
    throw new Error("These tests need Postgres's server programs on PATH: initdb, pg_ctl, pg_basebackup, and pg_rewind")
  }
  directory = await mkdtemp(join(tmpdir(), 'pg-failover-test-'))
  first = { port: await freePort(), dataDirectory: join(directory, 'first'), logFile: join(directory, 'first.log') }
  second = { port: await freePort(), dataDirectory: join(directory, 'second'), logFile: join(directory, 'second.log') }
  refusedPort = await freePort()
  silentServer = net.createServer(() => {})
  await new Promise((resolve) => silentServer.listen(0, '127.0.0.1', resolve))

  const passwordFile = join(directory, 'superuser_password')
  await writeFile(passwordFile, superuserPassword)
  await runProgram('initdb', ['--pgdata', first.dataDirectory, '--username', 'postgres', '--pwfile', passwordFile,
    '--auth-local', 'trust', '--auth-host', 'scram-sha-256', '--data-checksums'])
  // TCP only, on the loopback address. pg_rewind needs the checksums.
  await appendFile(join(first.dataDirectory, 'postgresql.conf'), "listen_addresses = '127.0.0.1'\nunix_socket_directories = ''\n")
  await startServer(first)
  await asSuperuser(first, `create role shop login password '${appPassword}'`)
  await asSuperuser(first, 'create database shop owner shop')
  await runProgram('pg_basebackup', ['--host', '127.0.0.1', '--port', String(first.port), '--username', 'postgres',
    '--pgdata', second.dataDirectory, '--write-recovery-conf', '--wal-method', 'stream', '--checkpoint', 'fast'],
  { env: { ...process.env, PGPASSWORD: superuserPassword } })
  await startServer(second)
  await waitUntilStreaming(first, second)
  primary = first
  standby = second
})

after(async () => {
  for (const server of [first, second]) {
    if (server) await stopServer(server).catch(() => {})
  }
  silentServer?.close()
  if (directory) await rm(directory, { recursive: true, force: true })
})

describe('a new connection', () => {
  it('skips a read-only primary when the old database cannot be reached', async () => {
    await asSuperuser(primary, 'alter role shop set default_transaction_read_only = on')
    try {
      await assert.rejects(serverOfANewConnection(databaseUrl([refusedPort, primary.port, standby.port], 'read-write')),
        /No database server fits target_session_attrs=read-write/)
    } finally {
      await asSuperuser(primary, 'alter role shop reset default_transaction_read_only')
    }
  })

  it('goes to the primary for read-write, with the standby listed first', async () => {
    const server = await serverOfANewConnection(databaseUrl([standby.port, primary.port], 'read-write'))
    assert.deepEqual(server, { port: primary.port, standby: false })
  })

  it('goes to the standby for prefer-standby, with the primary listed first', async () => {
    const server = await serverOfANewConnection(databaseUrl([primary.port, standby.port], 'prefer-standby'))
    assert.deepEqual(server, { port: standby.port, standby: true })
  })

  it('goes to the primary for prefer-standby when no standby answers', async () => {
    const server = await serverOfANewConnection(databaseUrl([primary.port, refusedPort], 'prefer-standby'))
    assert.deepEqual(server, { port: primary.port, standby: false })
  })

  it('skips a server that refuses the connection', async () => {
    const server = await serverOfANewConnection(databaseUrl([refusedPort, primary.port], 'read-write'))
    assert.deepEqual(server, { port: primary.port, standby: false })
  })

  it('skips a server that never answers once connect_timeout has passed', { timeout: 10_000 }, async () => {
    const startedAt = Date.now()
    const server = await serverOfANewConnection(databaseUrl([silentServer.address().port, primary.port], 'read-write'))
    const seconds = (Date.now() - startedAt) / 1000
    assert.deepEqual(server, { port: primary.port, standby: false })
    assert.ok(seconds >= 1 && seconds < 3, `took ${seconds} s, with connect_timeout=1`)
  })

  it('fails when no server fits, and says why for each server', async () => {
    const pool = poolForDatabaseUrl(databaseUrl([refusedPort, standby.port], 'read-write'))
    try {
      await assert.rejects(pool.query('select 1'), (error) => {
        assert.match(error.message, /^No database server fits target_session_attrs=read-write/)
        assert.match(error.message, new RegExp(`127\\.0\\.0\\.1:${refusedPort}: .*ECONNREFUSED`))
        assert.match(error.message, new RegExp(`127\\.0\\.0\\.1:${standby.port} is a standby`))
        return true
      })
    } finally {
      await pool.end()
    }
  })
})

describe('a database URL', () => {
  it('with a setting the file does not apply is refused', () => {
    assert.throws(() => poolForDatabaseUrl(databaseUrl([primary.port], 'read-write', '&sslmode=require')), /the setting sslmode/)
  })

  it('never shows its password in an error', () => {
    assert.throws(() => poolForDatabaseUrl(`mysql://shop:${appPassword}@db01/shop`), (error) => !error.message.includes(appPassword))
  })

  it('narrowed to the primary keeps connect_timeout and drops target_session_attrs', async () => {
    const narrowed = await singleServerDatabaseUrl(databaseUrl([standby.port, primary.port], 'read-write'))
    assert.equal(narrowed, `postgresql://shop:${appPassword}@127.0.0.1:${primary.port}/shop?connect_timeout=1`)
  })
})

describe('run_with_the_primary_database_url.mjs', () => {
  it('runs the command with DATABASE_URL naming only the primary, and PGOPTIONS in its options', async () => {
    // The command, as a migration tool would, connects with DATABASE_URL as
    // a plain connection string, and leaves PGOPTIONS out of its own
    // environment, as Prisma's CLI ignores it.
    const command = `
      import pg from 'pg'
      delete process.env.PGOPTIONS
      const client = new pg.Client({ connectionString: process.env.DATABASE_URL })
      await client.connect()
      const { rows } = await client.query("select inet_server_port() as port, current_setting('lock_timeout') as lock_timeout")
      console.log(JSON.stringify(rows[0]))
      await client.end()`
    const { stdout } = await runProgram(process.execPath, ['run_with_the_primary_database_url.mjs', process.execPath, '--input-type=module', '-e', command], {
      cwd: thisDirectory,
      env: { ...process.env, DATABASE_URL: databaseUrl([standby.port, primary.port], 'read-write'), PGOPTIONS: '-c lock_timeout=5s' },
    })
    assert.deepEqual(JSON.parse(stdout), { port: primary.port, lock_timeout: '5s' })
  })

  it("exits with the command's exit status", async () => {
    await assert.rejects(
      runProgram(process.execPath, ['run_with_the_primary_database_url.mjs', process.execPath, '-e', 'process.exit(3)'], {
        cwd: thisDirectory,
        env: { ...process.env, DATABASE_URL: databaseUrl([primary.port], 'read-write') },
      }),
      (error) => error.code === 3)
  })
})

function startTheCheck(timeLimitSeconds) {
  const check = spawn(process.execPath, ['check_database_failover.mjs', '--time-limit-seconds', String(timeLimitSeconds)], {
    cwd: thisDirectory,
    env: {
      ...process.env,
      DATABASE_URL: databaseUrl([first.port, second.port], 'read-write'),
      DATABASE_READ_URL: databaseUrl([first.port, second.port], 'prefer-standby'),
    },
  })
  let output = ''
  check.stdout.on('data', (chunk) => { output += chunk })
  check.stderr.on('data', (chunk) => { output += chunk })
  const exited = new Promise((resolve) => check.on('exit', (code) => resolve({ code, output })))
  const firstWrite = new Promise((resolve) => check.stdout.on('data', () => { if (/write .*\(primary\)/.test(output)) resolve() }))
  return { exited, firstWrite }
}

describe('check_database_failover.mjs', () => {
  it('fails when the writes never move to another server', async () => {
    const { code, output } = await startTheCheck(3).exited
    assert.equal(code, 1, output)
    assert.match(output, /^FAILED: within 3 s, writes reached 127\.0\.0\.1:\d+;/m)
  })
})

describe('a switchover', () => {
  it('ends no process, and the pool finds the new primary', async (t) => {
    const warnings = []
    t.mock.method(console, 'warn', (text) => warnings.push(text))
    const oldPrimary = primary
    const pool = poolForDatabaseUrl(databaseUrl([first.port, second.port], 'read-write'), { max: 2 })
    try {
      // One connection waits idle in the pool, and one is held in a
      // transaction, as an ORM holds it between two statements.
      const held = await pool.connect()
      await held.query('begin')
      await pool.query('select 1')
      assert.equal(pool.idleCount, 1)

      await switchOver()

      await assert.rejects(held.query('select 1'))
      held.release(true)
      assert.ok(warnings.some((text) => text.startsWith(`An idle database connection to 127.0.0.1:${oldPrimary.port} closed`)), warnings.join('\n'))
      const { rows } = await pool.query('select inet_server_port() as port, pg_is_in_recovery() as standby')
      assert.deepEqual(rows[0], { port: primary.port, standby: false })
    } finally {
      await pool.end()
    }
  })

  it('back again passes check_database_failover.mjs', async () => {
    const check = startTheCheck(60)
    await check.firstWrite
    await switchOver()
    const { code, output } = await check.exited
    assert.equal(code, 0, output)
    assert.match(output, new RegExp(`^PASSED: writes moved from 127\\.0\\.0\\.1:${second.port} to 127\\.0\\.0\\.1:${first.port}, and a new read connection went to the standby 127\\.0\\.0\\.1:${second.port}$`, 'm'))
  })
})
