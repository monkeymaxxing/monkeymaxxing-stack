import { pool, transaction } from './database.mjs';
import { SQSClient, SendMessageCommand, ReceiveMessageCommand, DeleteMessageCommand, ChangeMessageVisibilityCommand } from '@aws-sdk/client-sqs';
import { pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const backend = process.env.QUEUE_BACKEND || 'postgres';
if (!['postgres', 'sqs'].includes(backend)) throw Error('QUEUE_BACKEND must be postgres or sqs');
const queueUrl = process.env.SQS_QUEUE_URL;
const sqs = backend === 'sqs' ? new SQSClient({region: process.env.AWS_REGION}) : null;
if (backend === 'sqs' && !queueUrl) throw Error('SQS_QUEUE_URL is required for QUEUE_BACKEND=sqs');

export async function runJob(jobId = null) {
  return transaction(async client => {
    if ((await client.query('SELECT jobs_paused FROM controls WHERE id=1')).rows[0].jobs_paused) return {state: 'paused'};
    const result = jobId
      ? await client.query('SELECT * FROM report_jobs WHERE id=$1 FOR UPDATE', [jobId])
      : await client.query("SELECT * FROM report_jobs WHERE state='PENDING' AND available_at<=now() ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1");
    if (!result.rowCount) return {state: 'absent'};
    const job = result.rows[0];
    if (job.state === 'COMPLETED') return {state: 'completed', id: job.id};
    const remainingSeconds = Math.ceil((new Date(job.available_at).getTime() - Date.now()) / 1000);
    if (remainingSeconds > 0) return {state: 'delayed', remainingSeconds};
    const count = await client.query('SELECT count(*)::integer AS count FROM records WHERE owner_id=$1', [job.owner_id]);
    await client.query("UPDATE report_jobs SET state='COMPLETED',output=$2,completed_at=now() WHERE id=$1", [job.id, `record_count=${count.rows[0].count}\n`]);
    return {state: 'completed', id: job.id};
  });
}

export async function dispatchNotifications(transport = sqs) {
  return transaction(async client => {
    if ((await client.query('SELECT jobs_paused FROM controls WHERE id=1')).rows[0].jobs_paused) return 0;
    const jobs = await client.query("SELECT id,available_at FROM report_jobs WHERE state='PENDING' AND sqs_notified_at IS NULL ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 10");
    for (const job of jobs.rows) {
      // A crash after SendMessage and before COMMIT can send twice. Completion is idempotent by job ID.
      const seconds = Math.max(0, Math.min(900, Math.ceil((new Date(job.available_at).getTime() - Date.now()) / 1000)));
      await transport.send(new SendMessageCommand({QueueUrl: queueUrl, MessageBody: JSON.stringify({job_id: job.id}), DelaySeconds: seconds}));
      await client.query('UPDATE report_jobs SET sqs_notified_at=now() WHERE id=$1', [job.id]);
    }
    return jobs.rowCount;
  });
}

export async function runSqsOnce(transport = sqs) {
  if ((await pool.query('SELECT jobs_paused FROM controls WHERE id=1')).rows[0].jobs_paused) return;
  await dispatchNotifications(transport);
  const response = await transport.send(new ReceiveMessageCommand({QueueUrl: queueUrl, MaxNumberOfMessages: 1, WaitTimeSeconds: 1, VisibilityTimeout: 60}));
  for (const message of response.Messages || []) {
    const body = JSON.parse(message.Body);
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(body.job_id)) throw Error('SQS message needs a UUID job_id');
    const result = await runJob(body.job_id);
    if (result.state === 'completed') {
      // runJob has committed before this acknowledgement. A failed delete may redeliver safely.
      await transport.send(new DeleteMessageCommand({QueueUrl: queueUrl, ReceiptHandle: message.ReceiptHandle}));
    } else if (result.state === 'delayed') {
      await transport.send(new ChangeMessageVisibilityCommand({QueueUrl: queueUrl, ReceiptHandle: message.ReceiptHandle, VisibilityTimeout: Math.min(43200, result.remainingSeconds)}));
    } else if (result.state === 'absent') {
      throw Error('SQS job_id has no PostgreSQL ledger row');
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  let stopping = false;
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => { stopping = true; });
  try {
    do {
      if (backend === 'sqs') await runSqsOnce(); else await runJob();
      if (process.argv.includes('--once')) break;
      if (!stopping) await delay(1000);
    } while (!stopping);
  } finally { sqs?.destroy(); await pool.end(); }
}
