import cluster from 'node:cluster';
const workers = Number(process.env.WEB_CONCURRENCY || 1);
if (!Number.isInteger(workers) || workers < 1) throw new Error('WEB_CONCURRENCY must be a positive integer.');
if (cluster.isPrimary) {
  let stopping = false;
  for (let index = 0; index < workers; index++) cluster.fork();
  cluster.on('exit', () => { if (!stopping) cluster.fork(); });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => {
    if (stopping) return;
    stopping = true;
    for (const worker of Object.values(cluster.workers)) worker.process.kill('SIGTERM');
  });
} else await import('./server.mjs');
