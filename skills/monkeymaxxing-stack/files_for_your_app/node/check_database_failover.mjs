// The check that a Node app follows a database switchover. Start it on an
// app server just before switch_database_primary, in a Node container with
// the app's env file; the systems repository's operating_procedures/test_a_nodejs_app_during_a_database_switchover.md, "A Node app
// through a switchover", has the command. It connects as a Node app does,
// through pg_with_multiple_database_servers.mjs beside it: it writes through
// DATABASE_URL and reads through DATABASE_READ_URL. Twice a second it writes
// on four pooled connections at once and reads on a new connection, and it
// prints each change of where they land.
//
// It passes, and exits 0, once
//   - the writes have moved to a second server, the new primary;
//   - since then, 10 rounds in a row wrote on all four connections; and
//   - the newest read went to a standby: prefer-standby found the old
//     primary once it was back as a replica.
// It fails, and exits 1, when that hasn't happened within
// --time-limit-seconds, 600 unless given, because switch_database_primary
// waits at most 5 minutes for a settled formation before the switch and 5
// minutes after it.
//
// A write is select pg_current_xact_id(): only the primary can run it, and
// it changes no table. Each round hands its connections back to the pool as
// if nothing had failed, as some ORMs do, so a connection left on a standby,
// such as one through a PgBouncer that didn't restart, keeps failing, and so
// does the check.
import { parseArgs } from 'node:util'
import { poolForDatabaseUrl } from './pg_with_multiple_database_servers.mjs'

const { values: options } = parseArgs({ options: { 'time-limit-seconds': { type: 'string', default: '600' } } })
const timeLimitSeconds = Number(options['time-limit-seconds'])
if (!(timeLimitSeconds > 0)) {
  console.error('--time-limit-seconds takes a number of seconds, such as 600')
  process.exit(2)
}
const connectionsAtOnce = 4
const goodRoundsNeeded = 10
const writes = poolForDatabaseUrl(process.env.DATABASE_URL, { max: connectionsAtOnce })
// maxUses: 1 gives each read a new connection, so each read shows where
// prefer-standby sends a new connection at that moment.
const reads = poolForDatabaseUrl(process.env.DATABASE_READ_URL, { max: 1, maxUses: 1 })

const started = Date.now()
const secondsSinceTheStart = () => `${((Date.now() - started) / 1000).toFixed(1).padStart(6)} s`
const lastPrinted = {}
const writeServers = new Set()
let firstWriteServer = null
let goodRoundsSinceTheSwitch = 0
let writesFailingSince = null
let write = null
let read = null

async function ask(pool, sql) {
  let client = null
  try {
    client = await pool.connect()
    const { rows } = await client.query(sql)
    return { ok: true, server: `${client.host}:${client.port}`, standby: rows[0].standby }
  } catch (error) {
    return { ok: false, error: String(error.message).split('\n')[0].slice(0, 120) }
  } finally {
    // Without the error, on purpose: see the top of this file.
    client?.release()
  }
}

function printWhenChanged(what, outcome) {
  const text = outcome.ok ? `${outcome.server} (${outcome.standby ? 'standby' : 'primary'})` : `fails: ${outcome.error}`
  if (lastPrinted[what] !== text) console.log(`${secondsSinceTheStart()} ${what.padEnd(5)} ${text}`)
  lastPrinted[what] = text
}

async function finish(passed, text) {
  console.log(`${passed ? 'PASSED' : 'FAILED'}: ${text}`)
  await Promise.all([writes.end(), reads.end()])
  process.exit(passed ? 0 : 1)
}

while (Date.now() - started < timeLimitSeconds * 1000) {
  const roundStarted = Date.now()
  let writeRound
  ;[read, ...writeRound] = await Promise.all([
    ask(reads, 'select pg_is_in_recovery() as standby'),
    ...Array.from({ length: connectionsAtOnce }, () =>
      ask(writes, 'select pg_current_xact_id() is not null as written, pg_is_in_recovery() as standby')),
  ])
  write = writeRound.find((outcome) => !outcome.ok) ?? writeRound[0]
  if (write.ok) {
    if (writesFailingSince !== null) {
      console.log(`${secondsSinceTheStart()} writes failed for ${((roundStarted - writesFailingSince) / 1000).toFixed(1)} s`)
    }
    writesFailingSince = null
    firstWriteServer ??= write.server
    for (const outcome of writeRound) writeServers.add(outcome.server)
  } else {
    writesFailingSince ??= roundStarted
  }
  printWhenChanged('write', write)
  printWhenChanged('read', read)
  const switched = writeServers.size >= 2
  goodRoundsSinceTheSwitch = switched && write.ok ? goodRoundsSinceTheSwitch + 1 : 0
  if (goodRoundsSinceTheSwitch >= goodRoundsNeeded && read.ok && read.standby) {
    await finish(true, `writes moved from ${firstWriteServer} to ${write.server}, and a new read connection went to the standby ${read.server}`)
  }
  await new Promise((resolve) => setTimeout(resolve, Math.max(0, 500 - (Date.now() - roundStarted))))
}
await finish(false, `within ${timeLimitSeconds} s, writes reached ${[...writeServers].join(', ') || 'no server'}; `
  + `the newest writes ${write?.ok ? 'worked' : `failed: ${write?.error}`}; `
  + `the newest read ${read?.ok ? `went to ${read.server}, ${read.standby ? 'a standby' : 'the primary'}` : `failed: ${read?.error}`}`)
