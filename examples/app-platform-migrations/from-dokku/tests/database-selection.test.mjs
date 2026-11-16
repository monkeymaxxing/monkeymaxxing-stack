import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { clientClassForDatabaseUrl, singleServerDatabaseUrl } from '../app/pg_with_multiple_database_servers.mjs';
const require = createRequire(new URL('../app/package.json', import.meta.url));
const pg = require('pg');

test('unchanged database URL follows the writable app login through a fenced move', async t => {
  // No server is started: these are the session states reported by PostgreSQL.
  const states = {
    'old.example.com': { standby: false, writable: true },
    'db01.example.com': { standby: false, writable: false },
  };
  t.mock.method(pg.Client.prototype, 'connect', async function () {});
  t.mock.method(pg.Client.prototype, 'query', async function () { return { rows: [states[this.host]] }; });
  t.mock.method(pg.Client.prototype, 'end', async function () {});
  const url = 'postgresql://portal_db:synthetic-password@old.example.com:5432,db01.example.com:5432/portal_db?target_session_attrs=read-write&connect_timeout=3';
  const Client = clientClassForDatabaseUrl(url);
  async function selectedHost() {
    const client = new Client();
    try { await client.connect(); return client.host; }
    finally { await client.end(); }
  }
  assert.equal(await selectedHost(), 'old.example.com');
  states['old.example.com'].writable = false;
  await assert.rejects(selectedHost(), /No database server fits target_session_attrs=read-write/);
  states['db01.example.com'].writable = true;
  assert.equal(await selectedHost(), 'db01.example.com');
  assert.equal(new URL(await singleServerDatabaseUrl(url)).hostname, 'db01.example.com');
});
