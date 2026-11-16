import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

// Run the real process loop. Only its database/job dependencies are replaced.
async function runExecution(error, args = []) {
  const directory = await mkdtemp(join(tmpdir(), 'ecs-execution-'));
  await writeFile(join(directory, 'execution.mjs'), await readFile(new URL('../execution.mjs', import.meta.url)));
  await writeFile(join(directory, 'jobs.mjs'), `let calls=0;
    export async function runJob() {
      if (++calls===1) throw Object.assign(new Error(${JSON.stringify(error.message)}), ${JSON.stringify(error)});
      console.log('JOB_RECONNECTED'); process.kill(process.pid,'SIGTERM');
    }`);
  await writeFile(join(directory, 'schedule.mjs'), 'export async function runSchedule() {}');
  await writeFile(join(directory, 'database.mjs'), 'export const pool={async end(){console.log("POOL_CLOSED");}};');
  const child = spawn(process.execPath, [join(directory, 'execution.mjs'), ...args], {
    env: {...process.env, QUEUE_BACKEND: 'postgres'}, stdio: ['ignore', 'pipe', 'pipe']});
  let output = '';
  for (const stream of [child.stdout, child.stderr]) stream.on('data', chunk => { output += chunk; });
  const timeout = setTimeout(() => child.kill('SIGKILL'), 5000);
  const code = await new Promise(resolve => child.once('close', resolve));
  clearTimeout(timeout);
  return {code, output};
}

test('continuous jobs reconnect after the database fence without exiting', async () => {
  for (const error of [
    {message: 'No database server fits target_session_attrs=read-write: source disabled'},
    {message: 'connection terminated', code: '08006'},
    {message: 'administrator shutdown', code: '57P01'},
    {message: 'read-only transaction', code: '25006'},
    {message: 'Connection terminated unexpectedly'},
    {message: 'socket reset', code: 'ECONNRESET'},
    {message: 'connection refused', code: 'ECONNREFUSED'},
    {message: 'connect timed out', code: 'ETIMEDOUT'},
    {message: 'socket closed', code: 'EPIPE'},
  ]) {
    const result = await runExecution(error);
    assert.equal(result.code, 0, result.output);
    assert.match(result.output, /JOB_RECONNECTED/);
    assert.match(result.output, /POOL_CLOSED/);
  }
});

test('one-shot jobs and unexpected failures still fail visibly', async () => {
  for (const [error, args] of [
    [{message: 'No database server fits target_session_attrs=read-write'}, ['--once']],
    [{message: 'missing ledger table', code: '42P01'}, []],
  ]) {
    const result = await runExecution(error, args);
    assert.notEqual(result.code, 0);
    assert.doesNotMatch(result.output, /JOB_RECONNECTED/);
    assert.match(result.output, /POOL_CLOSED/);
  }
});
