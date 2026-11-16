// Runs a command with DATABASE_URL narrowed to the one server that is the
// primary now, for a migration tool that reads DATABASE_URL itself and can't
// take a list of servers, such as Prisma's CLI and drizzle-kit. The app's
// migration_command then starts with it:
//
//   node run_with_the_primary_database_url.mjs npx prisma migrate deploy
//
// It needs pg_with_multiple_database_servers.mjs beside it. A tool that
// connects through the app's own pools, such as Knex's, Sequelize's,
// TypeORM's, or MikroORM's, needs neither.
import { spawn } from 'node:child_process'
import { singleServerDatabaseUrl } from './pg_with_multiple_database_servers.mjs'

const [command, ...commandArguments] = process.argv.slice(2)
if (!command) {
  console.error('Usage: node run_with_the_primary_database_url.mjs COMMAND [ARGUMENT...]')
  process.exit(2)
}

let databaseUrl = await singleServerDatabaseUrl(process.env.DATABASE_URL)
// The stack runs the migrations with PGOPTIONS="-c lock_timeout=5s", so a
// migration that waits for a table lock fails after 5 seconds instead of
// holding up the app's requests behind it. pg reads PGOPTIONS by itself;
// Prisma's CLI doesn't, but takes the same setting as the URL's options.
if (process.env.PGOPTIONS) {
  databaseUrl += `${databaseUrl.includes('?') ? '&' : '?'}options=${encodeURIComponent(process.env.PGOPTIONS)}`
}

const child = spawn(command, commandArguments, { stdio: 'inherit', env: { ...process.env, DATABASE_URL: databaseUrl } })
child.on('error', (error) => {
  console.error(`run_with_the_primary_database_url.mjs couldn't start ${command}: ${error.message}`)
  process.exit(1)
})
// A command that a signal ended has no exit status: it failed.
child.on('exit', (code) => process.exit(code ?? 1))
