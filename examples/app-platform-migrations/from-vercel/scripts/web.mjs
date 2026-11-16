import cluster from 'node:cluster'
import { createRequire } from 'node:module'

const count = Number(process.env.WEB_CONCURRENCY)
const port = Number(process.env.PORT)
if (!Number.isSafeInteger(count) || count < 1 || !Number.isSafeInteger(port) || port < 1 || port > 65535) {
  throw new Error('Set WEB_CONCURRENCY to a positive integer and PORT to a valid TCP port')
}
if (cluster.isPrimary) {
  let stopping = false
  let failed = false
  let shutdownExitCode
  for (let index = 0; index < count; index++) cluster.fork()
  function stop(signal) {
    if (stopping) return
    stopping = true
    shutdownExitCode = signal === 'SIGTERM' ? 143 : 130
    for (const worker of Object.values(cluster.workers)) worker.process.kill(signal)
  }
  process.once('SIGTERM', () => stop('SIGTERM'))
  process.once('SIGINT', () => stop('SIGINT'))
  cluster.on('exit', (_worker, code) => {
    // Next.js drains requests, then uses the standard 128+signal exit code.
    // Normalize only the signal we requested. Other failures stay failures.
    if (!stopping || (code !== 0 && code !== shutdownExitCode)) { failed = true; stop('SIGTERM') }
    if (Object.keys(cluster.workers).length === 0) process.exit(failed ? 1 : 0)
  })
} else {
  // This is the generated standalone server, not a custom Next.js server.
  // Next.js closes its listener and drains requests on SIGTERM.
  process.env.HOSTNAME = process.env.BIND_ADDRESS || '0.0.0.0'
  createRequire(import.meta.url)('../server.js')
}
