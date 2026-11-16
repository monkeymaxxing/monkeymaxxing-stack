import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';

if (process.env.REHEARSAL_CONFIRM !== 'disposable-destination') throw Error('Use an empty disposable database and bucket');
const appDir = process.env.APP_DIR || fileURLToPath(new URL('../', import.meta.url));
const { pool, migrate } = await import(pathToFileURL(appDir + '/database.mjs'));
const base = 'http://127.0.0.1:18031';

test('a lost INSERT reply retains committed metadata and downloadable private bytes', async () => {
  await migrate();
  const server = spawn(process.execPath, ['--import', fileURLToPath(new URL('lose-document-reply.mjs', import.meta.url)), appDir + '/server.mjs'], {
    env: {...process.env, APP_DIR: appDir, PORT: '18031', WEB_CONCURRENCY: '1', COOKIE_SECURE: 'false'}, stdio: 'inherit'
  });
  try {
    let ready = false;
    for (let i = 0; i < 100; i++) {
      try { if ((await fetch(base + '/healthz')).ok) { ready = true; break; } } catch {}
      await delay(50);
    }
    assert.ok(ready, 'injected web process is ready');
    const credentials = {email: 'document-test@example.com', password: process.env.FIXTURE_PASSWORD};
    let response = await fetch(base + '/api/register', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(credentials)});
    assert.equal(response.status, 201);
    response = await fetch(base + '/api/login', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(credentials)});
    assert.equal(response.status, 200);
    const cookie = response.headers.get('set-cookie').split(';')[0];
    response = await fetch(base + '/api/documents?file_name=retained.txt', {method: 'POST', headers: {cookie, 'content-type': 'application/octet-stream'}, body: 'Committed private bytes\n'});
    assert.equal(response.status, 500, 'the caller receives the uncertain write failure');
    const documents = (await pool.query('SELECT * FROM documents')).rows;
    assert.equal(documents.length, 1, 'the actual INSERT committed');
    response = await fetch(base + '/api/documents/' + documents[0].id, {headers: {cookie}});
    assert.equal(response.status, 200, 'the committed document remains downloadable');
    assert.equal(await response.text(), 'Committed private bytes\n');
  } finally {
    if (server.exitCode === null) { const stopped = once(server, 'exit'); server.kill('SIGTERM'); await stopped; }
  }
});
test.after(async () => { await pool.end(); });
