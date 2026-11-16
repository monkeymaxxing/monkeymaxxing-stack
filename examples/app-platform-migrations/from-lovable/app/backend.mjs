import { createHash, randomBytes, randomUUID } from 'node:crypto';
import bcrypt from 'bcryptjs';
import { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import { poolForDatabaseUrl } from './pg_with_multiple_database_servers.mjs';

export const sha256 = value => createHash('sha256').update(value).digest('hex');
export const pool = poolForDatabaseUrl(process.env.DATABASE_URL, {
  max: 5, statement_timeout: 10000, query_timeout: 12000, idleTimeoutMillis: 5000,
});
process.once('SIGTERM', () => pool.end());
pool.on('error', error => console.error('Idle database connection ended:', error.code || 'connection_error'));
export const storage = new S3Client({
  endpoint: process.env.S3_ENDPOINT, region: process.env.S3_REGION || 'auto', forcePathStyle: true,
  credentials: { accessKeyId: process.env.S3_ACCESS_KEY_ID, secretAccessKey: process.env.S3_SECRET_ACCESS_KEY },
  // Mutations with an uncertain result must be checked, never replayed automatically.
  maxAttempts: 1,
});
export const bucket = process.env.S3_BUCKET;
export async function putObject(key, bytes) {
  return storage.send(new PutObjectCommand({ Bucket: bucket, Key: key, Body: bytes, ContentType: 'application/octet-stream' }));
}
export async function objectBytes(key) {
  const object = await storage.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
  return Buffer.from(await object.Body.transformToByteArray());
}
export async function transaction(action) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await action(client);
    await client.query('COMMIT');
    return result;
  } catch (error) {
    await client.query('ROLLBACK').catch(() => {});
    throw error;
  } finally { client.release(); }
}
export async function runJob(ownerId = null) {
  return transaction(async client => {
    const { rows: [job] } = await client.query(
      `SELECT * FROM report_jobs WHERE status='PENDING' AND ($1::uuid IS NULL OR user_id=$1)
       ORDER BY requested_at,id LIMIT 1 FOR UPDATE SKIP LOCKED`, [ownerId]);
    if (!job) return { processed: 0, job: null };
    const { rows: [{ count }] } = await client.query('SELECT count(*) FROM records WHERE user_id=$1', [job.user_id]);
    const { rows: [done] } = await client.query(
      `UPDATE report_jobs SET status='COMPLETED',started_at=now(),completed_at=now(),attempts=attempts+1,output=$2
       WHERE id=$1 RETURNING *`, [job.id, `record_count=${count}\n`]);
    return { processed: 1, job: done };
  });
}
export async function maintenance() {
  return pool.query(`UPDATE report_jobs SET archived_at=now() WHERE status='COMPLETED'
    AND archived_at IS NULL AND completed_at < now()-interval '30 days'`);
}
class HttpError extends Error { constructor(status, message) { super(message); this.status = status; } }
const json = (value, status = 200, headers = {}) => Response.json(value, { status, headers: { 'cache-control': 'no-store', ...headers } });
const reject = (status, message) => { throw new HttpError(status, message); };
const uuid = value => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const titleValue = value => {
  if (typeof value !== 'string' || !value.trim() || value.trim().length > 200) reject(400, 'Title must contain 1 to 200 characters');
  return value.trim();
};
async function bodyJson(request) {
  if (!request.headers.get('content-type')?.startsWith('application/json')) reject(415, 'Send application/json');
  try { return await request.json(); } catch { reject(400, 'Invalid JSON'); }
}
const origin = () => {
  if (!process.env.PUBLIC_ORIGIN) throw new Error('PUBLIC_ORIGIN is required');
  return new URL(process.env.PUBLIC_ORIGIN).origin;
};
const cookie = (token, expires) => `portal_session=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${expires}${origin().startsWith('https:') ? '; Secure' : ''}`;
export async function currentUser(request) {
  const token = /(?:^|;\s*)portal_session=([a-f0-9]{64})(?:;|$)/.exec(request.headers.get('cookie') || '')?.[1];
  if (!token) reject(401, 'Log in first');
  const { rows: [user] } = await pool.query(`SELECT u.id,u.email FROM sessions s JOIN users u ON u.id=s.user_id
    WHERE token_hash=$1 AND expires_at>now() AND (u.banned_until IS NULL OR u.banned_until<=now())`, [sha256(token)]);
  if (!user) reject(401, 'Log in first');
  return user;
}
export async function account(request) {
  const user = await currentUser(request);
  const { rows: [counts] } = await pool.query(`SELECT
    (SELECT count(*)::int FROM records WHERE user_id=$1) AS records,
    (SELECT count(*)::int FROM documents WHERE user_id=$1) AS documents,
    (SELECT count(*)::int FROM report_jobs WHERE user_id=$1) AS reports`, [user.id]);
  return { user, userId: user.id, email: user.email, counts, checkedAt: new Date().toISOString() };
}
export async function api(request) {
  const url = new URL(request.url), route = url.pathname, method = request.method;
  if (!route.startsWith('/api/')) return null;
  try {
    if (!['GET', 'HEAD'].includes(method) && request.headers.get('origin') !== origin()) reject(403, 'Request origin refused');
    if (method === 'POST' && ['/api/login', '/api/register'].includes(route)) {
      const body = await bodyJson(request);
      if (typeof body.email !== 'string' || !/^\S+@\S+\.\S+$/.test(body.email.trim()) || typeof body.password !== 'string') reject(400, 'Email and password required');
      const email = body.email.trim().toLowerCase();
      if (route === '/api/register') {
        if (body.password.length < 8 || Buffer.byteLength(body.password) > 72) reject(400, 'Password must have at least 8 characters and at most 72 UTF-8 bytes');
        await pool.query('INSERT INTO users(id,email,password_hash,email_confirmed_at) VALUES($1,$2,$3,now())', [randomUUID(), email, await bcrypt.hash(body.password, 12)]);
      }
      const { rows: [user] } = await pool.query('SELECT * FROM users WHERE lower(email)=$1', [email]);
      if (!user || !await bcrypt.compare(body.password, user.password_hash) || (user.banned_until && new Date(user.banned_until) > new Date())) reject(401, 'Email or password incorrect');
      const token = randomBytes(32).toString('hex');
      await pool.query("INSERT INTO sessions VALUES($1,$2,now()+interval '7 days')", [sha256(token), user.id]);
      return json({ user: { id: user.id, email: user.email } }, 200, { 'set-cookie': cookie(token, 604800) });
    }
    const user = await currentUser(request);
    if (method === 'POST' && route === '/api/logout') {
      await pool.query('DELETE FROM sessions WHERE user_id=$1', [user.id]);
      return json({ logged_out: true }, 200, { 'set-cookie': cookie('', 0) });
    }
    if (method === 'GET' && route === '/api/account') return json(await account(request));
    if (route === '/api/records') {
      if (method === 'GET') return json((await pool.query('SELECT * FROM records WHERE user_id=$1 ORDER BY created_at DESC', [user.id])).rows);
      if (method === 'POST') {
        const body = await bodyJson(request);
        return json((await pool.query('INSERT INTO records(user_id,title) VALUES($1,$2) RETURNING *', [user.id, titleValue(body.title)])).rows[0], 201);
      }
    }
    const recordId = /^\/api\/records\/([^/]+)$/.exec(route)?.[1];
    if (recordId) {
      if (!uuid(recordId)) reject(400, 'Invalid record ID');
      if (method === 'PATCH') {
        const body = await bodyJson(request);
        const { rows: [record] } = await pool.query('UPDATE records SET title=$3,updated_at=now() WHERE id=$1 AND user_id=$2 RETURNING *', [recordId, user.id, titleValue(body.title)]);
        if (!record) reject(404, 'Record not found');
        return json(record);
      }
      if (method === 'DELETE') {
        const result = await pool.query('DELETE FROM records WHERE id=$1 AND user_id=$2', [recordId, user.id]);
        if (!result.rowCount) reject(404, 'Record not found');
        return json({ deleted: true });
      }
    }
    if (route === '/api/documents') {
      if (method === 'GET') return json((await pool.query('SELECT * FROM documents WHERE user_id=$1 ORDER BY created_at DESC', [user.id])).rows);
      if (method === 'POST') {
        const name = request.headers.get('x-file-name'), recordId = request.headers.get('x-record-id') || null;
        if (!name || name.length > 255 || (recordId && !uuid(recordId))) reject(400, 'Invalid file name or record ID');
        if (recordId && !(await pool.query('SELECT id FROM records WHERE id=$1 AND user_id=$2', [recordId, user.id])).rowCount) reject(404, 'Record not found');
        // Read at most the source bucket's 20 MiB capacity; do not buffer an unbounded request.
        const chunks = []; let length = 0;
        if (request.body) for await (const chunk of request.body) {
          length += chunk.length;
          if (length > 20 * 1024 * 1024) reject(413, 'File exceeds 20 MiB');
          chunks.push(chunk);
        }
        const bytes = Buffer.concat(chunks);
        const key = `${user.id}/${randomUUID()}/${name.replace(/[^A-Za-z0-9._-]+/g, '_').slice(0,120) || 'file'}`;
        await putObject(key, bytes);
        const { rows: [document] } = await pool.query(`INSERT INTO documents(user_id,record_id,file_name,object_key,sha256,byte_count)
          VALUES($1,$2,$3,$4,$5,$6) RETURNING *`, [user.id, recordId, name, key, sha256(bytes), bytes.length]);
        return json(document, 201);
      }
    }
    const documentId = /^\/api\/documents\/([^/]+)(\/download)?$/.exec(route);
    if (documentId) {
      if (!uuid(documentId[1])) reject(400, 'Invalid document ID');
      const { rows: [document] } = await pool.query('SELECT * FROM documents WHERE id=$1 AND user_id=$2', [documentId[1], user.id]);
      if (!document) reject(404, 'Document not found');
      if (method === 'GET' && documentId[2]) return json({ signedUrl: await getSignedUrl(storage,
        new GetObjectCommand({ Bucket: bucket, Key: document.object_key }), { expiresIn: 60 }) });
      if (method === 'DELETE' && !documentId[2]) {
        // Remove the reference first. A failed storage request can leave an orphan, never a broken live reference.
        await pool.query('DELETE FROM documents WHERE id=$1 AND user_id=$2', [document.id, user.id]);
        await storage.send(new DeleteObjectCommand({ Bucket: bucket, Key: document.object_key }));
        return json({ deleted: true });
      }
    }
    if (route === '/api/reports') {
      if (method === 'GET') return json((await pool.query('SELECT * FROM report_jobs WHERE user_id=$1 ORDER BY requested_at DESC', [user.id])).rows);
      if (method === 'POST') return json((await pool.query('INSERT INTO report_jobs(user_id) VALUES($1) RETURNING *', [user.id])).rows[0], 201);
    }
    if (method === 'POST' && route === '/api/reports/run') return json(await runJob(user.id));
    reject(404, 'Route not found');
  } catch (error) {
    if (error.status) return json({ error: error.message }, error.status);
    if (error.code === '23505') return json({ error: 'An account or object already exists' }, 409);
    console.error('API request failed:', error.code || error.name);
    return json({ error: 'The request failed. Check the result before trying again.' }, 503);
  }
}
