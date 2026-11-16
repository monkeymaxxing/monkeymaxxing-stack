import cluster from 'node:cluster';
const workerCount = Number(process.env.WEB_CONCURRENCY || '1');
if (!Number.isInteger(workerCount) || workerCount < 1) throw new Error('WEB_CONCURRENCY must be a positive integer.');
if (cluster.isPrimary) {
  let stopping = false;
  for (let i = 0; i < workerCount; i++) cluster.fork();
  cluster.on('exit', () => { if (!stopping) cluster.fork(); });
  function stop() {
    if (stopping) return;
    stopping = true;
    for (const worker of Object.values(cluster.workers)) worker?.process.kill('SIGTERM');
  }
  process.on('SIGTERM', stop);
  process.on('SIGINT', stop);
} else {
  const { app } = await import('./server.mjs');
  const { pool } = await import('./database.mjs');
  const server = app.listen(Number(process.env.PORT || 5000), '0.0.0.0', () => console.log('Customer portal is listening.'));
  let stopping = false;
  function stop() {
    if (stopping) return;
    stopping = true;
    server.close(async () => { await pool.end(); process.exit(0); });
    server.closeIdleConnections();
  }
  process.on('SIGTERM', stop);
  process.on('SIGINT', stop);
}
