import { pool } from '../database.mjs';
const operation = process.argv[2];
try {
  if (operation === 'freeze') await pool.query('UPDATE controls SET maintenance=true,jobs_paused=true WHERE id=1');
  else if (operation === 'resume-web') await pool.query('UPDATE controls SET maintenance=false WHERE id=1');
  else if (operation === 'resume-jobs') await pool.query('UPDATE controls SET jobs_paused=false WHERE id=1');
  else throw Error('Usage: control.mjs freeze|resume-web|resume-jobs');
  console.log(JSON.stringify((await pool.query('SELECT * FROM controls')).rows));
} finally { await pool.end(); }
