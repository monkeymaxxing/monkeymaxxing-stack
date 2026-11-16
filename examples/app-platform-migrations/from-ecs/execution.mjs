// One destination jobs command owns reports and the application schedule.
import { runJob } from './jobs.mjs';
import { runSchedule } from './schedule.mjs';
import { pool } from './database.mjs';
import { setTimeout as delay } from 'node:timers/promises';
if (process.env.QUEUE_BACKEND && process.env.QUEUE_BACKEND !== 'postgres') throw Error('Destination execution requires QUEUE_BACKEND=postgres');
let stopping = false;
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => { stopping = true; });
let nextScheduleCheck = 0;
try {
  do {
    try {
      await runJob();
      if (Date.now() >= nextScheduleCheck) { await runSchedule(); nextScheduleCheck = Date.now() + 60000; }
    } catch (error) {
      const temporarilyUnavailable = error.message?.startsWith('No database server fits target_session_attrs=')
        || error.message === 'Connection terminated unexpectedly'
        || error.code?.startsWith('08')
        || ['57P01', '25006', 'ECONNRESET', 'ECONNREFUSED', 'ETIMEDOUT', 'EPIPE'].includes(error.code);
      if (!temporarilyUnavailable || process.argv.includes('--once')) throw error;
      console.error('Database unavailable for jobs; the next cycle will reconnect.');
    }
    if (process.argv.includes('--once')) break;
    if (!stopping) await delay(1000);
  } while (!stopping);
} finally { await pool.end(); }
