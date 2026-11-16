// This test changes only a disposable restored copy, never the live source.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { databaseChecks, snapshotDatabase } from '../data-transfer.mjs';
import { writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { setTimeout as sleep } from 'node:timers/promises';
import { pool, migrate } from '../app/database.mjs';
import { completeReport } from '../app/jobs.mjs';
import { archiveReports } from '../app/schedule.mjs';

const checks = [];
const children = [];
assert.ok(process.env.ALLOW_DISPOSABLE_REHEARSAL==='true' && process.env.NODE_ENV==='test','Use a disposable restored test copy only.');
const password = (await readFile(process.env.FIXTURE_PASSWORD_FILE,'utf8')).trim();
const manifest=JSON.parse(await readFile(process.env.EXPORT_DIR+'/manifest.json'));
const snapshot=JSON.parse(await readFile(process.env.EXPORT_DIR+'/snapshot.json'));
const firstPort=Number(process.env.REHEARSAL_FIRST_PORT||18081);
const appDirectory = new URL('../app/', import.meta.url);
const check = (condition, name) => assert.ok(condition, name);
function start(file, env = {}) {
  const child = spawn(process.execPath, [file], { cwd: appDirectory, env: { ...process.env, ...env }, stdio: ['ignore', 'ignore', 'ignore'] });
  children.push(child); return child;
}
async function stop(child, signal = 'SIGTERM') {
  if (child.exitCode !== null || child.signalCode) return;
  const ended = once(child, 'exit'); child.kill(signal); await ended;
}
async function until(action, label, seconds = 15) {
  const end = Date.now() + seconds * 1000;
  while (Date.now() < end) {
    try { if (await action()) return; } catch { /* Wait for this owned process to become ready. */ }
    await sleep(100);
  }
  throw new Error(label);
}
function actor(person) {
  let cookie = '';
  return { person, async request(path, { method = 'GET', body, raw, other = false, origin } = {}) {
    const headers = { Cookie: cookie };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (raw !== undefined) { headers['Content-Type'] = 'application/octet-stream'; headers['X-File-Name'] = `${person}-note.txt`; }
    if (origin) headers.Origin = origin;
    const response = await fetch(`http://127.0.0.1:${other ? firstPort+1 : firstPort}${path}`, { method, headers, body: raw ?? (body === undefined ? undefined : JSON.stringify(body)) });
    const newCookie = response.headers.get('set-cookie');
    if (newCookie) cookie = newCookie.split(';')[0];
    const bytes = Buffer.from(await response.arrayBuffer());
    const value = response.headers.get('content-type')?.includes('application/json') ? JSON.parse(bytes) : undefined;
    return { status: response.status, value, bytes };
  } };
}
let webA, webB;
try {
  const expectedDatabase = JSON.stringify(manifest.database);
  check(JSON.stringify(databaseChecks(await snapshotDatabase(pool)))===expectedDatabase,'Exact restored rows, password hashes, ownership, outputs and migration ledger');
  await migrate();await migrate();
  check(JSON.stringify(databaseChecks(await snapshotDatabase(pool)))===expectedDatabase,'Restored migrations remain idempotent and unchanged');
  check((await pool.query('SHOW server_version')).rows[0].server_version.startsWith('17.'),'Destination PostgreSQL must be 17');
  checks.push('Exact restore across every application table, including existing bcrypt hashes, session state, IDs, owners, completed output and migration checksums.');
  webA = start('web.mjs', { PORT: String(firstPort) });
  webB = start('web.mjs', { PORT: String(firstPort+1) });
  await until(async () => (await fetch(`http://127.0.0.1:${firstPort}/healthz`)).ok && (await fetch(`http://127.0.0.1:${firstPort+1}/healthz`)).ok, 'web processes did not become ready');
  checks.push('Two web instances start with two processes each after restore and unchanged migrations.');
  const actors = [actor('barbara'), actor('michael')];
  const fixture = [];
  for (const user of actors) {
    const owner=snapshot.users.find(row=>row.email===`${user.person}@example.com`);
    const record=snapshot.records.find(row=>row.owner_id===owner.id);
    const document=snapshot.documents.find(row=>row.owner_id===owner.id);
    const job=snapshot.report_jobs.find(row=>row.owner_id===owner.id&&row.state==='PENDING');
    const result=await user.request('/api/login',{method:'POST',body:{email:owner.email,password}});
    check(result.status===200 && result.value.id===owner.id,'Existing-password login preserves account UUID');
    const me=await user.request('/api/me',{other:true});
    check(me.status===200 && me.value.id===owner.id,'Restored session crosses web instances');
    const rows=await user.request('/api/records');
    check(rows.value.length===1&&rows.value[0].id===record.id&&rows.value[0].description===record.description,'Exact fixture record after restore');
    const bytes=await user.request(`/api/documents/${document.id}`,{other:true});
    check(bytes.status===200&&bytes.bytes.equals(Buffer.from(`${user.person==='barbara'?'Barbara':'Michael'} synthetic document\n`)),'Exact restored private document bytes');
    fixture.push({owner,record,document,job});
  }
  checks.push('Both existing passwords, preserved account/record UUIDs, descriptions and exact private file bytes work through HTTP.');
  for (const [index, user] of actors.entries()) {
    const other = fixture[1 - index];
    for (const [path, method, body] of [
      [`/api/records/${other.record.id}`, 'GET'],
      [`/api/records/${other.record.id}`, 'PATCH', { title: 'must not change' }],
      [`/api/records/${other.record.id}`, 'DELETE'],
      [`/api/documents/${other.document.id}`, 'GET'],
      [`/api/reports/${other.job.id}`, 'GET'],
    ]) check((await user.request(path, { method, body })).status === 404, 'other-owner access refused');
    for (const path of ['/api/records', '/api/documents', '/api/reports']) {
      const result = await user.request(path);
      check(result.status === 200 && result.value.length >= 1 && result.value.every(row => row.owner_id === fixture[index].owner.id), 'owned lists');
    }
    let result = await user.request('/api/records', { method: 'POST', body: { title: 'temporary' } });
    check(result.status === 201 && result.value.description === '', 'old-client title-only default');
    const id = result.value.id;
    result = await user.request(`/api/records/${id}`, { method: 'PATCH', body: { title: 'updated', description: 'temporary description' } });
    check(result.status === 200 && result.value.title === 'updated', 'owned record edit');
    check((await user.request(`/api/records/${id}`, { method: 'DELETE' })).status === 200, 'owned record deletion');
    const newBytes=Buffer.from('Destination private document\n');
    const uploaded=await user.request('/api/documents',{method:'POST',raw:newBytes});
    check(uploaded.status===201,'New destination private upload');
    const downloaded=await user.request(`/api/documents/${uploaded.value.id}`,{other:true});
    check(downloaded.status===200&&downloaded.bytes.equals(newBytes),'New destination upload downloads exact bytes across web instances');
    check((await user.request('/api/records', { method: 'POST', origin: 'https://foreign.example.com', body: { title: 'must not create' } })).status === 403, 'foreign-origin mutation refusal');
    check((await user.request('/api/logout', { method: 'POST' })).status === 200, 'logout');
    check((await user.request('/api/me', { other: true })).status === 401, 'logout recognized by second web instance');
    result = await user.request('/api/login', { method: 'POST', body: { email: `${user.person}@example.com`, password: 'definitely-the-wrong-password' } });
    check(result.status === 401, 'wrong-password refusal');
    result = await user.request('/api/login', { method: 'POST', body: { email: `${user.person}@example.com`, password } });
    check(result.status === 200 && result.value.id === fixture[index].owner.id, 'existing-password login');
  }
  checks.push('Each owner passes CRUD, new private uploads with byte equality, isolation refusals, cross-instance sessions, logout, wrong-password refusal, and existing-password login.');
  const results = await Promise.all([completeReport(), completeReport(), completeReport(), completeReport()]);
  check(results.filter(Boolean).length === 2, 'concurrent workers claim each job once');
  const jobs = (await pool.query('SELECT state,output FROM report_jobs')).rows;
  check(jobs.length === 3 && jobs.every(job => job.state === 'COMPLETED' && job.output === 'record_count=1\n'), 'owner-only exact report output');
  checks.push('Concurrent report transactions complete each fixture job once with record_count=1 followed by LF.');
  await actors[0].request('/api/reports', { method: 'POST' });
  const paused = start('jobs.mjs', { JOBS_PAUSED: 'true' });
  await sleep(1200); await stop(paused);
  check((await pool.query("SELECT count(*)::int AS n FROM report_jobs WHERE state='PENDING'")).rows[0].n === 1, 'paused worker preserves job');
  await pool.query(`CREATE FUNCTION interrupt_preflight_report() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
    IF current_setting('application_name')='interrupt-proof' THEN PERFORM pg_sleep(8); END IF;
    RETURN NEW; END $$`);
  await pool.query('CREATE TRIGGER interrupt_preflight_report BEFORE UPDATE ON report_jobs FOR EACH ROW EXECUTE FUNCTION interrupt_preflight_report()');
  const interrupted = start('jobs.mjs', { JOBS_PAUSED: 'false', PGAPPNAME: 'interrupt-proof' });
  await until(async () => (await pool.query("SELECT count(*)::int AS n FROM pg_stat_activity WHERE application_name='interrupt-proof' AND wait_event='PgSleep'")).rows[0].n === 1, 'worker did not reach open completion transaction');
  await stop(interrupted, 'SIGKILL');
  await until(async () => (await pool.query("SELECT count(*)::int AS n FROM pg_stat_activity WHERE application_name='interrupt-proof'")).rows[0].n === 0, 'killed worker connection remained');
  check((await pool.query("SELECT count(*)::int AS n FROM report_jobs WHERE state='PENDING'")).rows[0].n === 1, 'interrupted transaction retains pending work');
  await pool.query('DROP TRIGGER interrupt_preflight_report ON report_jobs');
  await pool.query('DROP FUNCTION interrupt_preflight_report()');
  const worker = start('jobs.mjs', { JOBS_PAUSED: 'false' });
  await until(async () => (await pool.query("SELECT count(*)::int AS n FROM report_jobs WHERE state='PENDING'")).rows[0].n === 0, 'replacement worker did not complete waiting report');
  await stop(worker);
  checks.push('Actual jobs entry point respects pause; SIGKILL during its completion transaction leaves work for a replacement worker.');
  // Only the disposable copy changes after the exact-restore comparison above.
  await pool.query("DELETE FROM schedule_runs WHERE task_name='archive_completed_reports'");
  await pool.query("UPDATE report_jobs SET completed_at=now()-interval '31 days' WHERE id=$1",[snapshot.report_jobs.find(job=>job.state==='COMPLETED').id]);
  const archives=await Promise.all([archiveReports(),archiveReports()]);
  check(archives.filter(Boolean).length===1,'Concurrent daily archive commits once');
  check((await pool.query('SELECT archived_job_count FROM schedule_runs')).rows[0].archived_job_count===1,'Daily archive changes only the old completed report');
  checks.push('Concurrent schedule invocations commit one occurrence and archive only the old completed report.');
  await pool.query("DELETE FROM schedule_runs WHERE task_name='archive_completed_reports'");
  await actors[0].request('/api/reports',{method:'POST'});
  const combined=start('job-container.mjs',{JOBS_PAUSED:'false',ARCHIVE_DAILY_UTC_TIME:'00:00'});
  await until(async()=> (await pool.query("SELECT count(*)::int AS n FROM report_jobs WHERE state='PENDING'")).rows[0].n===0 && (await pool.query('SELECT count(*)::int AS n FROM schedule_runs')).rows[0].n===1,'Combined jobs command did not run report and clock work');
  await stop(combined);
  checks.push('The actual Stack jobs command runs reports and the clock together, catches up a due UTC occurrence, and stops both on SIGTERM.');
  const newcomer=actor('newcomer');
  const registered=await newcomer.request('/api/register',{method:'POST',body:{email:'newcomer@example.com',password}});
  check(registered.status===201,'New destination account registration');
  await newcomer.request('/api/logout',{method:'POST'});
  checks.push('New accounts can register independently after the source export.');
  for (const user of actors) await user.request('/api/logout', { method: 'POST' });
  await stop(webA); await stop(webB);
  checks.push('Web process groups and worker close on SIGTERM.');
  const result = { scope: 'Standalone rehearsal of the frozen Heroku export on PostgreSQL 17 and independent S3-compatible storage', node_version: process.version, postgres_version: (await pool.query('SHOW server_version')).rows[0].server_version, checks, passed: true };
  await writeFile(process.env.EXPORT_DIR+'/rehearsal-result.json', JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result, null, 2));
} finally {
  for (const child of children) await stop(child);
  await pool.end();
}
