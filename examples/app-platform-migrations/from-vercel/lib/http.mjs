import { database, health } from './database.mjs'
import { accountFor, sessionToken, newSession, expiredCookie, validEmail, validPassword, passwordHash, passwordMatches } from './accounts.mjs'
import { putDocument, getDocument, sha256 } from './storage.mjs'

const json = (body, status = 200, headers = {}) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store', ...headers } })
function refuse(status, message) { throw Object.assign(new Error(message), { httpStatus: status }) }
async function timedHealth() {
  let timer
  try {
    return await Promise.race([
      health(),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Health deadline exceeded')), 2000) }),
    ])
  } finally { clearTimeout(timer) }
}
// Uploads are buffered by this teaching app. Bound memory per request to 8 MiB
// plus multipart headers, before asking the form parser to allocate the body.
async function form(request) {
  const chunks = []
  let length = 0
  const reader = request.body?.getReader()
  if (!reader) return new FormData()
  try {
    for (;;) {
      const part = await reader.read()
      if (part.done) break
      length += part.value.length
      if (length > 8 * 1024 * 1024 + 65536) {
        await reader.cancel()
        refuse(413, 'The request exceeds the upload memory limit')
      }
      chunks.push(part.value)
    }
    return await new Response(Buffer.concat(chunks), { headers: { 'Content-Type': request.headers.get('content-type') || 'application/x-www-form-urlencoded' } }).formData()
  } catch (error) {
    if (error.httpStatus) throw error
    refuse(400, 'Send a valid form')
  }
}
function text(fields, key, max, required = false) {
  const value = fields.get(key) ?? ''
  if (typeof value !== 'string' || value.length > max || (required && !value.trim())) refuse(400, `Invalid ${key}`)
  return value
}
export async function handle(request) {
  try {
    const path = new URL(request.url).pathname
    const method = request.method
    if (method === 'GET' && path === '/healthz') return json(await timedHealth())
    if (method === 'POST' && request.headers.get('origin') !== process.env.APP_ORIGIN) refuse(403, 'The request origin does not match APP_ORIGIN')
    if (method === 'POST' && ['/register', '/login'].includes(path)) {
      const fields = await form(request)
      const email = text(fields, 'email', 254).trim().toLowerCase()
      const password = text(fields, 'password', 4096)
      if (!validEmail(email) || (path === '/register' ? !validPassword(password) : !password)) refuse(400, 'Use a valid email and a password of 12 to 72 bytes')
      let account
      if (path === '/register') {
        const result = await database().query('INSERT INTO accounts(email,password_hash) VALUES($1,$2) ON CONFLICT(email) DO NOTHING RETURNING id,email', [email, await passwordHash(password)])
        account = result.rows[0]
        if (!account) refuse(409, 'The account already exists')
      } else {
        const result = await database().query('SELECT id,email,password_hash FROM accounts WHERE email=$1', [email])
        account = result.rows[0]
        if (!account || !await passwordMatches(password, account.password_hash)) refuse(401, 'The email or password is incorrect')
      }
      return json({ email }, 200, { 'Set-Cookie': await newSession(account.id) })
    }
    const account = await accountFor(request)
    if (!account) refuse(401, 'Log in to continue')
    if (method === 'POST' && path === '/logout') {
      await database().query('DELETE FROM sessions WHERE token_hash=$1', [sha256(sessionToken(request))])
      return json({ logged_out: true }, 200, { 'Set-Cookie': expiredCookie })
    }
    if (path === '/records') {
      if (method === 'GET') return json((await database().query('SELECT id,title,description FROM records WHERE account_id=$1 ORDER BY id', [account.id])).rows)
      if (method === 'POST') {
        const fields = await form(request)
        return json((await database().query('INSERT INTO records(account_id,title,description) VALUES($1,$2,$3) RETURNING id', [account.id, text(fields, 'title', 200, true), text(fields, 'description', 4000)])).rows[0], 201)
      }
    }
    const record = /^\/records\/([0-9a-f-]{36})\/(update|delete)$/.exec(path)
    if (method === 'POST' && record) {
      let result
      if (record[2] === 'delete') result = await database().query('DELETE FROM records WHERE id=$1 AND account_id=$2', [record[1], account.id])
      else {
        const fields = await form(request)
        result = await database().query('UPDATE records SET title=$1,description=$2 WHERE id=$3 AND account_id=$4', [text(fields, 'title', 200, true), text(fields, 'description', 4000), record[1], account.id])
      }
      if (!result.rowCount) refuse(404, 'The record was not found')
      return json({ saved: true })
    }
    if (path === '/documents') {
      if (method === 'GET') return json((await database().query('SELECT id,file_name,sha256,byte_count FROM documents WHERE account_id=$1 ORDER BY id', [account.id])).rows)
      if (method === 'POST') {
        const file = (await form(request)).get('file')
        if (!file || typeof file.arrayBuffer !== 'function' || !file.name || file.name.length > 255) refuse(400, 'Choose a file with a name of at most 255 characters')
        if (file.size > 8 * 1024 * 1024) refuse(413, 'Files must fit the 8 MiB upload memory limit')
        const document = await putDocument(account.id, file.name, Buffer.from(await file.arrayBuffer()))
        const result = await database().query('INSERT INTO documents(account_id,object_key,file_name,sha256,byte_count) VALUES($1,$2,$3,$4,$5) RETURNING id', [account.id, document.objectKey, document.fileName, document.sha256, document.byteCount])
        return json(result.rows[0], 201)
      }
    }
    const document = /^\/documents\/([0-9a-f-]{36})$/.exec(path)
    if (method === 'GET' && document) {
      const result = await database().query('SELECT * FROM documents WHERE id=$1 AND account_id=$2', [document[1], account.id])
      if (!result.rows.length) refuse(404, 'The document was not found')
      const row = result.rows[0]
      return new Response(await getDocument(row), { headers: {
        'Content-Type': 'application/octet-stream', 'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(row.file_name)}`,
      } })
    }
    if (path === '/reports') {
      if (method === 'GET') return json((await database().query('SELECT id,output,finished_at FROM report_jobs WHERE account_id=$1 ORDER BY id', [account.id])).rows)
      if (method === 'POST') return json((await database().query('INSERT INTO report_jobs(account_id) VALUES($1) RETURNING id', [account.id])).rows[0], 201)
    }
    refuse(404, 'The page was not found')
  } catch (error) {
    if (!error.httpStatus) console.error('Portal operation failed', error.code || error.name)
    return json({ error: error.httpStatus ? error.message : 'The service is unavailable. A failed write can have committed. Check the saved data before submitting again.' }, error.httpStatus || 503)
  }
}
