import { migrate, pool } from './database.mjs';
try { await migrate(); console.log('Database migrations applied.'); }
catch { console.error('Database migration failed.'); process.exitCode = 1; }
finally { await pool.end(); }
