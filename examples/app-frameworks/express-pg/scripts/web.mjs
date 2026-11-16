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
  const {app}=await import('../lib/app.mjs')
  const {closeDatabase}=await import('../lib/database.mjs')
  const port=Number(process.env.PORT)
  if(!Number.isInteger(port) || port<1 || port>65535) throw new Error('PORT must be a valid TCP port')
  const server=app.listen(port,'0.0.0.0')
  server.requestTimeout=15000;server.headersTimeout=10000
  let stopping=false
  function stop() {
    if(stopping) return
    stopping=true
    const deadline=setTimeout(()=>process.exit(1),25000);deadline.unref()
    server.close(async()=>{
      try { await closeDatabase();cluster.worker.disconnect() }
      catch { process.exitCode=1;cluster.worker.disconnect() }
    })
  }
  process.on('SIGTERM',stop);process.on('SIGINT',stop)
}
