import express from 'express'
import multer from 'multer'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { transaction } from './database.mjs'
import { credentials, refuse, passwordHash, passwordMatches, accountFor, newSession, sessionToken, expiredCookie } from './accounts.mjs'
import { putDocument, getDocument, sha256 } from './storage.mjs'

if (!process.env.APP_ORIGIN) throw new Error('APP_ORIGIN is required')

const root = fileURLToPath(new URL('../', import.meta.url))
const dummyHash = await passwordHash('unusable random password')
export const app = express()
app.disable('x-powered-by')
app.use((request, response, next) => {
  response.set('Cache-Control', 'no-store').set('X-Content-Type-Options', 'nosniff')
  if (!['GET','HEAD','OPTIONS'].includes(request.method) && request.headers.origin !== process.env.APP_ORIGIN) return response.status(403).json({error:'Origin refused'})
  next()
})
app.use(express.urlencoded({extended:false, limit:'64kb', parameterLimit:10}))
app.use('/assets', express.static(root+'assets', {
  setHeaders(response, file) {
    // Only content-hashed filenames can keep the same bytes for a year.
    response.setHeader('Cache-Control', /\.[a-f0-9]{12}\.(?:css|js)$/.test(file)
      ? 'public, max-age=31536000, immutable' : 'public, max-age=0')
  },
}))
app.get('/', async (request, response) => response.type('html').send(await readFile(root+'home.html','utf8')))
app.get('/healthz', async (request, response) => {
  await transaction(client=>client.query('SELECT 1'))
  response.json({status:'ok'})
})
app.post('/register', async (request, response) => {
  const {email,password}=credentials(request.body)
  const encoded=await passwordHash(password)
  let cookie
  try {
    cookie=await transaction(async client=>{
      const {rows}=await client.query('INSERT INTO accounts(email,password_hash) VALUES($1,$2) RETURNING id',[email,encoded])
      return newSession(client,rows[0].id)
    })
  } catch(error) { if(error.code==='23505') refuse(409,'Email is already registered'); throw error }
  response.set('Set-Cookie',cookie).json({status:'registered'})
})
app.post('/login', async (request,response)=>{
  const {email,password}=credentials(request.body)
  const cookie=await transaction(async client=>{
    const {rows}=await client.query('SELECT id,password_hash FROM accounts WHERE email=$1',[email])
    const valid=await passwordMatches(password,rows[0]?.password_hash || dummyHash)
    if(!rows.length || !valid) refuse(401,'Email or password refused')
    return newSession(client,rows[0].id)
  })
  response.set('Set-Cookie',cookie).json({status:'logged in'})
})
app.post('/logout', async (request,response)=>{
  await transaction(client=>client.query('DELETE FROM sessions WHERE token_hash=$1',[sha256(sessionToken(request))]))
  response.set('Set-Cookie',expiredCookie).json({status:'logged out'})
})
app.get('/records',async(request,response)=>response.json(await transaction(async client=>{
  const owner=await accountFor(client,request)
  return (await client.query('SELECT id,title,description FROM records WHERE account_id=$1 ORDER BY id',[owner])).rows
})))
function recordFields(body={}) {
  const {title,description=''}=body
  if(typeof title!=='string' || title.length<1 || title.length>200 || typeof description!=='string' || description.length>10000) refuse(400,'Title must be 1 to 200 characters; description at most 10000')
  return [title,description]
}
app.post('/records',async(request,response)=>{
  const fields=recordFields(request.body)
  const row=await transaction(async client=>{
    const owner=await accountFor(client,request)
    return (await client.query('INSERT INTO records(title,description,account_id) VALUES($1,$2,$3) RETURNING id',[...fields,owner])).rows[0]
  })
  response.status(201).json(row)
})
app.post('/records/:identifier/update',async(request,response)=>{
  const fields=recordFields(request.body)
  const row=await transaction(async client=>{
    const owner=await accountFor(client,request)
    return (await client.query('UPDATE records SET title=$1,description=$2 WHERE id=$3 AND account_id=$4 RETURNING id',[...fields,request.params.identifier,owner])).rows[0]
  })
  if(!row) refuse(404,'Record not found')
  response.json(row)
})
app.post('/records/:identifier/delete',async(request,response)=>{
  const row=await transaction(async client=>{
    const owner=await accountFor(client,request)
    return (await client.query('DELETE FROM records WHERE id=$1 AND account_id=$2 RETURNING id',[request.params.identifier,owner])).rows[0]
  })
  if(!row) refuse(404,'Record not found')
  response.json(row)
})
app.get('/documents',async(request,response)=>response.json(await transaction(async client=>{
  const owner=await accountFor(client,request)
  return (await client.query('SELECT id,filename,sha256,byte_count FROM documents WHERE account_id=$1 ORDER BY id',[owner])).rows
})))
const upload=multer({storage:multer.memoryStorage(),limits:{fileSize:8*1024*1024,files:1,fields:0,parts:1}})
app.post('/documents',upload.single('file'),async(request,response)=>{
  if(!request.file) refuse(400,'Choose a document')
  const filename=request.file.originalname
  if(filename.length>255) refuse(400,'Filename is longer than 255 characters')
  const row=await transaction(async client=>{
    const owner=await accountFor(client,request)
    const document=await putDocument(owner,filename,request.file.buffer)
    return (await client.query('INSERT INTO documents(account_id,object_key,filename,sha256,byte_count) VALUES($1,$2,$3,$4,$5) RETURNING id',[owner,document.objectKey,filename,document.sha256,document.byteCount])).rows[0]
  })
  response.status(201).json(row)
})
app.get('/documents/:identifier',async(request,response)=>{
  const row=await transaction(async client=>{
    const owner=await accountFor(client,request)
    return (await client.query('SELECT * FROM documents WHERE id=$1 AND account_id=$2',[request.params.identifier,owner])).rows[0]
  })
  if(!row) refuse(404,'Document not found')
  response.type('application/octet-stream').set('Content-Disposition','attachment').send(await getDocument(row))
})
app.post('/reports',async(request,response)=>{
  const row=await transaction(async client=>{
    const owner=await accountFor(client,request)
    return (await client.query('INSERT INTO report_jobs(account_id) VALUES($1) RETURNING id',[owner])).rows[0]
  })
  response.status(201).json(row)
})
app.get('/reports',async(request,response)=>response.json(await transaction(async client=>{
  const owner=await accountFor(client,request)
  return (await client.query('SELECT id,output FROM report_jobs WHERE account_id=$1 ORDER BY id',[owner])).rows
})))
app.get('/reports/:identifier',async(request,response)=>{
  const row=await transaction(async client=>{
    const owner=await accountFor(client,request)
    return (await client.query('SELECT id,output FROM report_jobs WHERE id=$1 AND account_id=$2',[request.params.identifier,owner])).rows[0]
  })
  if(!row) refuse(404,'Report not found')
  response.json(row)
})
app.use((request,response)=>response.status(404).json({error:'Page not found'}))
app.use((error,request,response,next)=>{
  const httpStatusCode=error.httpStatusCode || (error instanceof multer.MulterError ? 413 : error.status===413 ? 413 : 503)
  // Do not log request bodies, tokens, SQL parameters or connection URLs.
  response.status(httpStatusCode).json({error:error.httpStatusCode ? error.message : httpStatusCode===413 ? 'Upload or form exceeds its size limit' : 'Request failed; check saved data before resubmitting'})
})
