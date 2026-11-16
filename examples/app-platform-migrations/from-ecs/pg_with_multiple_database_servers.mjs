// node-postgres (pg 8) for the database URLs that the Monkeymaxxing Stack
// gives every app, which list every database server:
//
//   DATABASE_URL=postgresql://shop:PASSWORD@db01:5432,db02:5432/shop?target_session_attrs=read-write&connect_timeout=3
//   DATABASE_READ_URL=postgresql://shop:PASSWORD@db01:5432,db02:5432/shop?target_session_attrs=prefer-standby&connect_timeout=3
//
// pg can't read a URL that lists several servers (pg 8.23.1 throws "Invalid
// URL"), and it has no target_session_attrs. Copy this file into the app
// unchanged, and make every database pool with one of the three functions
// at the end of it. Never give either URL to pg, an ORM, or a tool as a
// connection string.
//
// How a new connection finds its server: first it asks the servers, in the
// URL's order, each over a short connection of its own, whether they are a
// standby and whether this login can write. Then it connects to the first server
// that fits target_session_attrs:
//   read-write      the first server where this login can write
//   prefer-standby  the first standby that answers; when none does, the
//                   first server that answers, the primary
//   any             the first server that answers; it's what a URL without
//                   the setting gets, such as one for a laptop's database
// It asks Postgres itself, with a query, so a PgBouncer in front can't
// answer for it with what its Postgres was when PgBouncer first reached it.
// connect_timeout, in seconds, applies to each server in turn, as in libpq:
// a server that is switched off costs that long, then the next one is tried.
//
// It asks only when the pool opens a connection, never for a query: an open
// connection stays on its server until it ends. A switchover stops the old
// primary's Postgres, which ends its connections at once. A server that
// loses power or drops off the network sends nothing, so its connections end
// only when TCP gives up on them: within about a minute on the stack's
// servers, which set the kernel's keepalive and retransmission limits
// (net.ipv4.tcp_keepalive_*, tcp_retries2), for connections that have TCP
// keepalive on, as this file's have. Either way the pool drops the ended
// connections, and the connections it opens next find the new primary.
import pg from 'pg'

const targetSessionAttrsThisFileApplies = ['read-write', 'prefer-standby', 'any']
const urlSettingsThisFileApplies = ['target_session_attrs', 'connect_timeout']

function readDatabaseUrl(databaseUrl) {
  if (!databaseUrl) {
    throw new Error('No database URL was given, such as process.env.DATABASE_URL')
  }
  // Never put the URL into an error message: it holds the password.
  const parts = /^postgres(?:ql)?:\/\/(?:([^:@/]*)(?::([^@/]*))?@)?([^/?#]+)\/([^/?#]+)(?:\?([^#]*))?$/.exec(databaseUrl)
  if (!parts) {
    throw new Error('The database URL must look like postgresql://USER:PASSWORD@db01:5432,db02:5432/DATABASE?target_session_attrs=read-write&connect_timeout=3')
  }
  const [, user = '', password = '', serverList, database, query = ''] = parts
  const servers = serverList.split(',').map((hostAndPort) => {
    const [, host, port = '5432'] = /^([^:]+)(?::(\d+))?$/.exec(hostAndPort) || []
    if (!host) throw new Error(`The database URL lists a server this file can't read: ${hostAndPort}`)
    return { host, port: Number(port) }
  })
  const settings = new URLSearchParams(query)
  for (const name of settings.keys()) {
    // A setting that this file left out without a word, such as sslmode,
    // would change how the app connects, so it refuses the URL instead.
    if (!urlSettingsThisFileApplies.includes(name)) {
      throw new Error(`The database URL has the setting ${name}, which pg_with_multiple_database_servers.mjs doesn't apply. It applies only ${urlSettingsThisFileApplies.join(' and ')}.`)
    }
  }
  const targetSessionAttrs = settings.get('target_session_attrs') || 'any'
  if (!targetSessionAttrsThisFileApplies.includes(targetSessionAttrs)) {
    throw new Error(`The database URL has target_session_attrs=${targetSessionAttrs}, which pg_with_multiple_database_servers.mjs doesn't apply. It applies ${targetSessionAttrsThisFileApplies.join(', ')}.`)
  }
  return {
    servers,
    targetSessionAttrs,
    connectionSettings: {
      user: decodeURIComponent(user),
      password: decodeURIComponent(password),
      database: decodeURIComponent(database),
      connectionTimeoutMillis: Number(settings.get('connect_timeout') || 0) * 1000,
      // TCP keepalive on, with the kernel's timing: a delay here would also
      // set Node's own probe interval and count (1 second, 10 probes) in
      // place of the server's.
      keepAlive: true,
    },
  }
}

async function sessionState(server, connectionSettings) {
  const client = new pg.Client({ ...connectionSettings, ...server })
  // A server that ends this short connection makes connect() or query()
  // fail, which the caller handles. pg also emits 'error' then, and an
  // 'error' with no listener ends the Node process.
  client.on('error', () => {})
  try {
    await client.connect()
    const { rows } = await client.query("select pg_is_in_recovery() as standby, current_setting('transaction_read_only') = 'off' as writable")
    return rows[0]
  } finally {
    client.end().catch(() => {})
  }
}

async function findTheServer({ servers, targetSessionAttrs, connectionSettings }) {
  const whyNot = []
  let firstThatAnswered = null
  for (const server of servers) {
    const name = `${server.host}:${server.port}`
    let state
    try {
      state = await sessionState(server, connectionSettings)
    } catch (error) {
      whyNot.push(`${name}: ${error.message}`)
      continue
    }
    firstThatAnswered ??= server
    if (targetSessionAttrs === 'any') return server
    if (targetSessionAttrs === 'read-write' && state.writable) return server
    if (targetSessionAttrs === 'prefer-standby' && state.standby) return server
    whyNot.push(`${name} is ${state.standby ? 'a standby' : state.writable ? 'the primary' : 'read-only for this login'}`)
  }
  if (targetSessionAttrs === 'prefer-standby' && firstThatAnswered) return firstThatAnswered
  throw new Error(`No database server fits target_session_attrs=${targetSessionAttrs}: ${whyNot.join('; ')}`)
}

// A pg.Client class whose connections go to the database URL's servers. It
// ignores the connection settings it's given, such as an ORM's host and
// connectionString, because the URL holds them all; it keeps the others,
// such as statement_timeout.
export function clientClassForDatabaseUrl(databaseUrl) {
  const url = readDatabaseUrl(databaseUrl)
  return class ClientThatFindsItsDatabaseServer extends pg.Client {
    constructor(clientSettings = {}) {
      const { connectionString, host, port, user, password, database, ...otherSettings } = clientSettings
      super({ ...otherSettings, ...url.connectionSettings, ...url.servers[0] })
      // A failover ends every connection to the old primary (see the top of
      // this file), also one that an ORM holds between two statements, such
      // as in a transaction. pg then emits 'error' on the connection, and an
      // 'error' with no listener ends the Node process: the pool listens
      // only while a connection is idle in it. With this listener, the
      // connection's next statement fails instead, and the pool drops the
      // connection.
      this.on('error', () => {})
    }

    connect(callback) {
      const connecting = findTheServer(url).then((server) => {
        this.host = server.host
        this.port = server.port
        return super.connect()
      })
      if (!callback) return connecting
      connecting.then(() => callback(null, this), callback)
    }
  }
}

// A failover also ends the old primary's connections that are idle in the
// pool, and pg.Pool then emits 'error'. Without a listener, that ends the
// Node process.
function logIdleConnectionErrors(pool) {
  pool.on('error', (error, client) => {
    console.warn(`An idle database connection to ${client?.host}:${client?.port} closed: ${error.message}`)
  })
  return pool
}

// A pg.Pool for the database URL. poolSettings are pg.Pool's own, such as
// max and idleTimeoutMillis.
export function poolForDatabaseUrl(databaseUrl, poolSettings = {}) {
  return logIdleConnectionErrors(new pg.Pool({ ...poolSettings, Client: clientClassForDatabaseUrl(databaseUrl) }))
}

// The pg module, with its Client and Pool for the database URL, for an ORM
// that takes the pg module itself, such as Sequelize's dialectModule and
// Knex's _driver().
export function pgModuleForDatabaseUrl(databaseUrl) {
  const Client = clientClassForDatabaseUrl(databaseUrl)
  class Pool extends pg.Pool {
    constructor(poolSettings = {}) {
      super({ ...poolSettings, Client })
      logIdleConnectionErrors(this)
    }
  }
  return { ...pg, Client, Pool }
}

// The database's name, for an ORM that wants it beside the client class or
// the pg module, such as Sequelize, TypeORM, and MikroORM.
export function databaseNameInDatabaseUrl(databaseUrl) {
  return readDatabaseUrl(databaseUrl).connectionSettings.database
}

// The database URL with only the server that fits it now, and without
// target_session_attrs, for a tool that reads the URL itself and can't take
// a list of servers, such as Prisma's CLI and drizzle-kit:
// postgresql://shop:PASSWORD@db02:5432/shop?connect_timeout=3.
// run_with_the_primary_database_url.mjs runs such a tool with it.
export async function singleServerDatabaseUrl(databaseUrl) {
  const url = readDatabaseUrl(databaseUrl)
  const server = await findTheServer(url)
  const { user, password, database, connectionTimeoutMillis } = url.connectionSettings
  const credentials = user ? `${encodeURIComponent(user)}${password ? `:${encodeURIComponent(password)}` : ''}@` : ''
  const timeout = connectionTimeoutMillis ? `?connect_timeout=${connectionTimeoutMillis / 1000}` : ''
  return `postgresql://${credentials}${server.host}:${server.port}/${encodeURIComponent(database)}${timeout}`
}
