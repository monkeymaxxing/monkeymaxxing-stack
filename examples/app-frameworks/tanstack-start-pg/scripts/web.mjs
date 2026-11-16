import cluster from 'node:cluster'
const count = Number(process.env.WEB_CONCURRENCY || 1)
if (!Number.isInteger(count) || count < 1) throw new Error('WEB_CONCURRENCY must be a positive integer')
if (cluster.isPrimary) {
  let stopping = false
  let failed = false
  const workers = new Set()
  function stop(signal) {
    stopping = true
    for (const worker of workers) worker?.process.kill(signal)
  }
  cluster.on('exit', (worker, code, signal) => {
    workers.delete(worker)
    if (!stopping) { failed = true; stop('SIGTERM') }
    else if (code !== 0 && signal !== 'SIGTERM' && signal !== 'SIGINT') failed = true
    if (workers.size === 0) process.exit(failed ? 1 : 0)
  })
  for (const signal of ['SIGTERM', 'SIGINT']) process.once(signal, () => stop(signal))
  for (let index = 0; index < count; index++) workers.add(cluster.fork())
} else {
  await import('../.output/server/index.mjs')
}
