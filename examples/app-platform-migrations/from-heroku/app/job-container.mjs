// The Stack has one jobs command. Keep report and daily clock lifecycles together.
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const children = [];
let stopping = false;
let remaining = 0;
function stop() {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill('SIGTERM');
}
process.on('SIGTERM', stop);
process.on('SIGINT', stop);
for (const entry of process.env.JOBS_PAUSED === 'true' ? ['jobs.mjs'] : ['jobs.mjs', 'clock.mjs']) {
  const child = spawn(process.execPath, [fileURLToPath(new URL(entry, import.meta.url))], { stdio: 'inherit' });
  children.push(child); remaining++;
  child.on('error', () => { process.exitCode = 1; stop(); });
  child.on('exit', () => {
    remaining--;
    if (!stopping) { process.exitCode = 1; stop(); }
    if (!remaining) process.exit(process.exitCode || 0);
  });
}
