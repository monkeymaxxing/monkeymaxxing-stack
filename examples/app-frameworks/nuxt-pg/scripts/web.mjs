import cluster from 'node:cluster'

if (cluster.isPrimary) {
  const count=Number(process.env.WEB_CONCURRENCY)
  if(!Number.isInteger(count) || count<1) throw new Error('WEB_CONCURRENCY must be a positive integer')
  let stopping=false
  let failed=false
  for(let n=0;n<count;n++) cluster.fork()
  function stop() {
    if(stopping) return
    stopping=true
    for(const worker of Object.values(cluster.workers)) worker.process.kill('SIGTERM')
  }
  process.on('SIGTERM',stop);process.on('SIGINT',stop)
  cluster.on('exit',(worker,code)=>{
    if(!stopping || code!==0) { failed=true;stop() }
    if(Object.keys(cluster.workers).length===0) process.exit(failed ? 1 : 0)
  })
} else {
  if (!process.env.APP_ORIGIN) throw new Error('APP_ORIGIN is required')
  const origin = new URL(process.env.APP_ORIGIN)
  if (origin.origin !== process.env.APP_ORIGIN || !['http:','https:'].includes(origin.protocol)) throw new Error('APP_ORIGIN must be an HTTP or HTTPS origin')
  const port = Number(process.env.PORT)
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('PORT must be a valid TCP port')
  // The Stack owns the listener port. Do not let provider-specific aliases override PORT.
  process.env.NITRO_PORT = String(port)
  process.env.NITRO_HOST = '0.0.0.0'
  process.env.NITRO_SHUTDOWN_TIMEOUT = '25000'
  await import('../.output/server/index.mjs')
}
