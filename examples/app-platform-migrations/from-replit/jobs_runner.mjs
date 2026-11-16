import { startBackgroundWork } from './jobs.mjs';
import { pool } from './database.mjs';
const stop = startBackgroundWork();
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, async () => {
  stop();
  await pool.end();
  process.exit(0);
});
