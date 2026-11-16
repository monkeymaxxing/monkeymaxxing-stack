import cluster from 'node:cluster'
import { retainedAsset } from '../lib/retained-assets.mjs'

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
  // SvelteKit 3 removed ORIGIN. Canonical headers are overwritten inside this server,
  // never trusted from the client, so the framework sees the runtime public origin.
  process.env.PROTOCOL_HEADER = 'x-portal-protocol'
  process.env.HOST_HEADER = 'x-portal-host'
  process.env.BODY_SIZE_LIMIT = String(8 * 1024 * 1024 + 65536)
  const { createServer } = await import('node:http')
  const { handler } = await import('../build/handler.js')
  const server = createServer(async (request, response) => {
    request.headers['x-portal-protocol'] = origin.protocol.slice(0,-1)
    request.headers['x-portal-host'] = origin.host
    response.setHeader('Cache-Control','no-store')
    response.setHeader('X-Content-Type-Options','nosniff')
    try {
      const asset = await retainedAsset(request.url, request.method, 'build/client', ['/_app/immutable/', '/assets/'])
      if (asset) {
        // Ordinary public files keep adapter-node's absent cache label.
        if (asset.ok && !asset.headers.has('Cache-Control')) response.removeHeader('Cache-Control')
        response.writeHead(asset.status, Object.fromEntries(asset.headers))
        response.end(request.method === 'HEAD' ? undefined : Buffer.from(await asset.arrayBuffer()))
        return
      }
      handler(request,response)
    } catch (error) {
      console.error(error)
      response.writeHead(500)
      response.end()
    }
  })
  server.requestTimeout = 15000; server.headersTimeout = 10000
  server.listen(port,'0.0.0.0')
  let stopping = false
  function stop() {
    if (stopping) return
    stopping = true
    const deadline = setTimeout(()=>process.exit(1),25000); deadline.unref()
    server.close(() => process.emit('sveltekit:shutdown'))
    server.closeIdleConnections()
  }
  process.on('SIGTERM',stop); process.on('SIGINT',stop)
}
