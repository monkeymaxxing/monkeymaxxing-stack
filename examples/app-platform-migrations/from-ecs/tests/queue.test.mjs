import test from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { pool, migrate } from '../database.mjs';
import { dispatchNotifications, runJob, runSqsOnce } from '../jobs.mjs';
import { runSchedule } from '../schedule.mjs';

if (process.env.REHEARSAL_CONFIRM !== 'disposable-destination') throw Error('Use an empty disposable database');
const ownerId = randomUUID();
const pendingId = randomUUID();
const delayedId = randomUUID();
let failSend = true;
let receivedId = pendingId;
let failDelete = true;
const sent = [];
let acknowledged = 0;
const transport = {async send(command) {
  switch (command.constructor.name) {
    case 'SendMessageCommand':
      if (failSend) throw Error('injected unavailable queue');
      sent.push(command.input);
      return {};
    case 'ReceiveMessageCommand':
      return {Messages: [{Body: JSON.stringify({job_id: receivedId}), ReceiptHandle: 'synthetic-receipt'}]};
    case 'DeleteMessageCommand': {
      const row = (await pool.query('SELECT state,output FROM report_jobs WHERE id=$1', [receivedId])).rows[0];
      assert.equal(row.state, 'COMPLETED', 'another connection sees completion before acknowledgement');
      assert.equal(row.output, 'record_count=1\n');
      if (failDelete) throw Error('injected lost acknowledgement');
      acknowledged++;
      return {};
    }
    case 'ChangeMessageVisibilityCommand':
      assert.ok(command.input.VisibilityTimeout > 0);
      return {};
    default: throw Error('Unexpected queue command');
  }
}};

test.before(async () => {
  await migrate();
  await pool.query('INSERT INTO users(id,email,password_hash) VALUES($1,$2,$3)', [ownerId, 'queue-test@example.com', 'synthetic-not-for-login']);
  await pool.query('INSERT INTO records(id,owner_id,title) VALUES($1,$2,$3)', [randomUUID(), ownerId, 'Queue fixture']);
  await pool.query("INSERT INTO report_jobs(id,owner_id,available_at) VALUES($1,$3,now()),($2,$3,now()+interval '10 minutes')", [pendingId, delayedId, ownerId]);
  await pool.query('UPDATE controls SET jobs_paused=false WHERE id=1');
});

test('failed send preserves the durable notification; successful send preserves delayed due time', async () => {
  await assert.rejects(dispatchNotifications(transport), /injected unavailable queue/);
  assert.equal((await pool.query('SELECT count(*)::int AS n FROM report_jobs WHERE sqs_notified_at IS NOT NULL')).rows[0].n, 0);
  failSend = false;
  assert.equal(await dispatchNotifications(transport), 2);
  assert.equal(sent.length, 2);
  assert.equal(sent.find(message => JSON.parse(message.MessageBody).job_id === pendingId).DelaySeconds, 0);
  assert.ok(sent.find(message => JSON.parse(message.MessageBody).job_id === delayedId).DelaySeconds > 0);
});

test('lost SQS acknowledgement and duplicate delivery keep the original committed output', async () => {
  await assert.rejects(runSqsOnce(transport), /injected lost acknowledgement/);
  const first = (await pool.query('SELECT * FROM report_jobs WHERE id=$1', [pendingId])).rows[0];
  await pool.query('INSERT INTO records(id,owner_id,title) VALUES($1,$2,$3)', [randomUUID(), ownerId, 'Would change a duplicate report']);
  failDelete = false;
  await runSqsOnce(transport);
  assert.equal(acknowledged, 1);
  assert.deepEqual((await pool.query('SELECT * FROM report_jobs WHERE id=$1', [pendingId])).rows[0], first);
});

test('invisible or delayed notification stays pending and PostgreSQL replacement honors available_at', async () => {
  receivedId = delayedId;
  await runSqsOnce(transport);
  assert.equal(acknowledged, 1, 'early message is not acknowledged');
  assert.equal((await runJob()).state, 'absent', 'destination does not execute before the due time');
  assert.equal((await pool.query('SELECT state FROM report_jobs WHERE id=$1', [delayedId])).rows[0].state, 'PENDING');
  await pool.query('UPDATE report_jobs SET available_at=now() WHERE id=$1', [delayedId]);
  assert.equal((await runJob()).id, delayedId, 'destination needs no SQS receive or credential');
  assert.equal((await pool.query('SELECT output FROM report_jobs WHERE id=$1', [delayedId])).rows[0].output, 'record_count=2\n');
  assert.equal((await runJob()).state, 'absent');
});

test('execution pause also stops the scheduler; overlapping schedule calls commit once', async () => {
  await pool.query('UPDATE controls SET jobs_paused=true WHERE id=1');
  assert.equal(await runSchedule(), 'paused');
  assert.equal((await pool.query('SELECT count(*)::int AS n FROM scheduled_runs')).rows[0].n, 0);
  await pool.query('UPDATE controls SET jobs_paused=false WHERE id=1');
  await Promise.all([runSchedule(), runSchedule()]);
  assert.equal((await pool.query('SELECT count(*)::int AS n FROM scheduled_runs')).rows[0].n, 1);
});

test.after(async () => { await pool.end(); });
