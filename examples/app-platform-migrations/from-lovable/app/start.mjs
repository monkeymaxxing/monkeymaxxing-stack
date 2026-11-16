import cluster from 'node:cluster';
const count = Number(process.env.WEB_CONCURRENCY || 1);
if (!Number.isInteger(count) || count < 1) throw new Error('WEB_CONCURRENCY must be a positive integer');
if (cluster.isPrimary) {
  let stopping = false;
  for (let i=0;i<count;i++) cluster.fork();
  cluster.on('exit', () => {
    if (!stopping) cluster.fork();
    else if (!Object.values(cluster.workers).some(Boolean)) process.exit(0);
  });
  for (const signal of ['SIGTERM','SIGINT']) process.on(signal, () => {
    stopping = true;
    for (const worker of Object.values(cluster.workers)) worker?.process.kill('SIGTERM');
  });
} else {
  await import('./.output/server/index.mjs');
  // srvx closes HTTP listeners on SIGTERM; release cluster IPC so the worker can exit.
  process.on('SIGTERM', () => { if (process.connected) process.disconnect(); });
}
