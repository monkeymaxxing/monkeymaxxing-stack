import { setTimeout as sleep } from 'node:timers/promises';
import { pool } from './database.mjs';
import { archiveReports } from './schedule.mjs';

// PostgreSQL's unique UTC-date occurrence remains the authority during restarts or overlap.
const dailyTime = process.env.ARCHIVE_DAILY_UTC_TIME || '00:00';
if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(dailyTime)) throw new Error('ARCHIVE_DAILY_UTC_TIME must be HH:MM in UTC.');
const [hour, minute] = dailyTime.split(':').map(Number);
const abort = new AbortController();
process.on('SIGTERM', () => abort.abort());
process.on('SIGINT', () => abort.abort());
let due = new Date();
due.setUTCHours(hour, minute, 0, 0);
try {
  while (!abort.signal.aborted) {
    await sleep(Math.max(0, due.getTime() - Date.now()), undefined, { signal: abort.signal });
    if (abort.signal.aborted) break;
    const committed = await archiveReports();
    console.log(`Daily archive timer fired; scheduled_at=${due.toISOString()}; occurrence=${committed ? 'committed' : 'already_completed'}`);
    do { due = new Date(due.getTime() + 86400000); } while (due.getTime() <= Date.now());
  }
} catch (error) {
  if (error.name !== 'AbortError') { console.error('Daily archive clock failed.'); process.exitCode = 1; }
} finally { await pool.end(); }
