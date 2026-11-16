import { transaction } from './database.mjs'
import { credentials, refuse, passwordHash, passwordMatches, accountFor, newSession, sessionToken, expiredCookie } from './accounts.mjs'
import { putDocument, getDocument, sha256 } from './storage.mjs'

const dummyHash = passwordHash('unusable random password')
const uploadLimit = 8 * 1024 * 1024
const json = (data, status = 200, cookie) => Response.json(data, {
  status, headers: {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff', ...(cookie ? {'Set-Cookie':cookie} : {})},
})
async function form(request, multipart = false) {
  const limit = multipart ? uploadLimit + 65536 : 65536
  const chunks = []; let count = 0
  if (request.body) {
    const reader = request.body.getReader()
    try {
      while (true) {
        const {value,done} = await reader.read()
        if (done) break
        count += value.byteLength
        if (count > limit) { await reader.cancel(); refuse(413,'Upload or form exceeds its size limit') }
        chunks.push(value)
      }
    } finally { reader.releaseLock() }
  }
  const bytes = Buffer.concat(chunks)
  if (!multipart) return Object.fromEntries(new URLSearchParams(bytes.toString('utf8')))
  try { return await new Response(bytes, {headers:{'Content-Type':request.headers.get('content-type') || ''}}).formData() }
  catch { refuse(400,'Invalid document form') }
}
function recordFields(body) {
  const {title,description=''} = body
  if (typeof title !== 'string' || title.length < 1 || title.length > 200 || typeof description !== 'string' || description.length > 10000) refuse(400,'Title must be 1 to 200 characters; description at most 10000')
  return [title,description]
}
export async function handlePortal(request) {
  try {
    const path = new URL(request.url).pathname
    const method = request.method
    if (!process.env.APP_ORIGIN) throw new Error('APP_ORIGIN is required')
    if (!['GET','HEAD','OPTIONS'].includes(method) && request.headers.get('origin') !== process.env.APP_ORIGIN) refuse(403,'Origin refused')
    if (path === '/healthz' && method === 'GET') {
      await transaction(client=>client.query('SELECT 1'))
      return json({status:'ok'})
    }
    if (path === '/register' && method === 'POST') {
      const {email,password} = credentials(await form(request))
      const encoded = await passwordHash(password)
      let cookie
      try {
        cookie = await transaction(async client=> {
          const {rows} = await client.query('INSERT INTO accounts(email,password_hash) VALUES($1,$2) RETURNING id',[email,encoded])
          return newSession(client,rows[0].id)
        })
      } catch (error) { if (error.code === '23505') refuse(409,'Email is already registered'); throw error }
      return json({status:'registered'},200,cookie)
    }
    if (path === '/login' && method === 'POST') {
      const {email,password} = credentials(await form(request))
      const cookie = await transaction(async client=> {
        const {rows} = await client.query('SELECT id,password_hash FROM accounts WHERE email=$1',[email])
        const valid = await passwordMatches(password,rows[0]?.password_hash || await dummyHash)
        if (!rows.length || !valid) refuse(401,'Email or password refused')
        return newSession(client,rows[0].id)
      })
      return json({status:'logged in'},200,cookie)
    }
    if (path === '/logout' && method === 'POST') {
      await transaction(client=>client.query('DELETE FROM sessions WHERE token_hash=$1',[sha256(sessionToken(request))]))
      return json({status:'logged out'},200,expiredCookie)
    }
    if (['/records','/documents','/reports'].includes(path) && method === 'GET') {
      const queries = {
        '/records':'SELECT id,title,description FROM records WHERE account_id=$1 ORDER BY id',
        '/documents':'SELECT id,filename,sha256,byte_count FROM documents WHERE account_id=$1 ORDER BY id',
        '/reports':'SELECT id,output FROM report_jobs WHERE account_id=$1 ORDER BY id',
      }
      return json(await transaction(async client=> {
        const owner = await accountFor(client,request)
        return (await client.query(queries[path],[owner])).rows
      }))
    }
    if (path === '/records' && method === 'POST') {
      const fields = recordFields(await form(request))
      return json(await transaction(async client=> {
        const owner = await accountFor(client,request)
        return (await client.query('INSERT INTO records(title,description,account_id) VALUES($1,$2,$3) RETURNING id',[...fields,owner])).rows[0]
      }),201)
    }
    const record = /^\/records\/([1-9][0-9]*)\/(update|delete)$/.exec(path)
    if (record && method === 'POST') {
      const fields = record[2] === 'update' ? recordFields(await form(request)) : []
      const row = await transaction(async client=> {
        const owner = await accountFor(client,request)
        const query = record[2] === 'update' ? 'UPDATE records SET title=$1,description=$2 WHERE id=$3 AND account_id=$4 RETURNING id' : 'DELETE FROM records WHERE id=$1 AND account_id=$2 RETURNING id'
        return (await client.query(query,[...fields,record[1],owner])).rows[0]
      })
      if (!row) refuse(404,'Record not found')
      return json(row)
    }
    if (path === '/documents' && method === 'POST') {
      // Authenticate before buffering or writing an object. Recheck within the metadata transaction.
      await transaction(client=>accountFor(client,request))
      const data = await form(request,true)
      const file = data.get('file')
      if (!(file instanceof File) || [...data.keys()].length !== 1) refuse(400,'Choose one document')
      if (file.size > uploadLimit) refuse(413,'Document exceeds 8 MiB')
      if (file.name.length > 255) refuse(400,'Filename is longer than 255 characters')
      return json(await transaction(async client=> {
        const owner = await accountFor(client,request)
        const document = await putDocument(owner,file.name,Buffer.from(await file.arrayBuffer()))
        return (await client.query('INSERT INTO documents(account_id,object_key,filename,sha256,byte_count) VALUES($1,$2,$3,$4,$5) RETURNING id',[owner,document.objectKey,file.name,document.sha256,document.byteCount])).rows[0]
      }),201)
    }
    const resource = /^\/(documents|reports)\/([1-9][0-9]*)$/.exec(path)
    if (resource && method === 'GET') {
      const row = await transaction(async client=> {
        const owner = await accountFor(client,request)
        return (await client.query(resource[1] === 'documents' ? 'SELECT * FROM documents WHERE id=$1 AND account_id=$2' : 'SELECT id,output FROM report_jobs WHERE id=$1 AND account_id=$2',[resource[2],owner])).rows[0]
      })
      if (!row) refuse(404,'Document or report not found')
      if (resource[1] === 'reports') return json(row)
      return new Response(await getDocument(row),{headers:{'Content-Type':'application/octet-stream','Content-Disposition':'attachment','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}})
    }
    if (path === '/reports' && method === 'POST') {
      return json(await transaction(async client=> {
        const owner = await accountFor(client,request)
        return (await client.query('INSERT INTO report_jobs(account_id) VALUES($1) RETURNING id',[owner])).rows[0]
      }),201)
    }
    return json({error:'Page not found'},404)
  } catch (error) {
    // No request bodies, tokens, SQL parameters or connection URLs in logs.
    return json({error:error.httpStatusCode ? error.message : 'Request failed; check saved data before resubmitting'},error.httpStatusCode || 503)
  }
}
