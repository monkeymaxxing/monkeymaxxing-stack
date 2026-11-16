import express from 'express';
import bcrypt from 'bcryptjs';
import { randomBytes, randomUUID, createHash } from 'node:crypto';
import { pool, transaction } from './database.mjs';
import * as storage from './storage.mjs';
import { runSchedule } from './jobs.mjs';
import { fileURLToPath } from 'node:url';

const app=express();
const hash=value=>createHash('sha256').update(value).digest('hex');
const cookieName='manual_portal_session';
// Files are buffered in memory, so keep a document below 1 MiB.
const maximumDocumentBytes=1024*1024;
app.set('trust proxy',1);
app.use((_req,res,next)=>{res.set('Cache-Control','no-store');next();});
app.use(express.json({limit:'2mb'}));
app.disable('x-powered-by');
app.get('/healthz',async(_req,res)=>{
  let deadline;
  try {
    const result = await Promise.race([
      pool.query("SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE name='002_record_description.sql') AS ready"),
      new Promise((_,reject)=>{deadline=setTimeout(()=>reject(new Error('Health deadline exceeded.')),2000);}),
    ]);
    if (!result.rows[0].ready) return res.status(503).json({ok:false});
    res.json({ok:true});
  } catch {res.status(503).json({ok:false});}
  finally {clearTimeout(deadline);}
});
app.use('/api',(req,res,next)=>{
  res.set('Cache-Control','no-store');
  const origin=req.get('origin');
  if(!['GET','HEAD'].includes(req.method)&&origin&&origin!==`${req.protocol}://${req.get('host')}`) return res.status(403).json({error:'Use this app origin for changes.'});
  next();
});
async function authenticate(req,res,next) {
  const token=(req.headers.cookie||'').split(';').map(p=>p.trim()).find(p=>p.startsWith(cookieName+'='))?.slice(cookieName.length+1);
  if(!token) return res.status(401).json({error:'Sign in required.'});
  const user=(await pool.query('SELECT u.id,u.email,u.is_admin FROM sessions s JOIN users u ON u.id=s.owner_id WHERE s.token_hash=$1 AND s.revoked_at IS NULL AND s.expires_at>now()',[hash(token)])).rows[0];
  if(!user) return res.status(401).json({error:'Sign in required.'});
  req.user=user;req.sessionHash=hash(token);next();
}
async function mutationsAllowed(_req,res,next) {
  const controls=(await pool.query('SELECT maintenance_enabled FROM controls WHERE id=1')).rows[0];
  if(!controls||controls.maintenance_enabled)return res.status(503).json({error:'Maintenance pauses changes, uploads, and report requests.'});
  next();
}
const admin=(req,res,next)=>req.user.is_admin?next():res.status(403).json({error:'Only the fixture administrator can change global controls.'});
const sessionCookie=(res,token,secure)=>res.cookie(cookieName,token,{httpOnly:true,secure,sameSite:'strict',path:'/',maxAge:7*86400*1000});
async function session(res,user,secure) {
  const token=randomBytes(32).toString('base64url');
  await pool.query("INSERT INTO sessions(token_hash,owner_id,expires_at) VALUES($1,$2,now()+interval '7 days')",[hash(token),user.id]);
  sessionCookie(res,token,secure);
}
function credentials(body) {
  const email=String(body.email||'').trim().toLowerCase();
  const password=String(body.password||'');
  if(!/^[^@\s]+@example\.com$/.test(email)||password.length<12||Buffer.byteLength(password)>72)return null;
  return {email,password};
}
app.post('/api/auth/register',mutationsAllowed,async(req,res)=>{
  const value=credentials(req.body);
  if(!value)return res.status(400).json({error:'Use an example.com email and a password of 12 characters to 72 UTF-8 bytes.'});
  const passwordHash=await bcrypt.hash(value.password,12);
  try {
    const user=await transaction(async client=>{
      await client.query('SELECT pg_advisory_xact_lock(7341206)');
      const isAdmin=!(await client.query('SELECT id FROM users LIMIT 1')).rows.length;
      const user=(await client.query('INSERT INTO users(id,email,password_hash,is_admin) VALUES($1,$2,$3,$4) RETURNING id,email,is_admin',[randomUUID(),value.email,passwordHash,isAdmin])).rows[0];
      await client.query('INSERT INTO identities(issuer,subject,user_id) VALUES($1,$2,$3)',[process.env.AUTH_ISSUER || 'urn:portal:password',user.id,user.id]);
      return user;
    });
    await session(res,user,req.secure);res.status(201).json(user);
  } catch(error) {if(error.code==='23505')return res.status(409).json({error:'Email already registered.'});throw error;}
});
app.post('/api/auth/login',async(req,res)=>{
  const value=credentials(req.body);
  const user=value?(await pool.query('SELECT id,email,is_admin,password_hash FROM users WHERE email=$1',[value.email])).rows[0]:null;
  if(!user||!await bcrypt.compare(value.password,user.password_hash))return res.status(401).json({error:'Incorrect email or password.'});
  await session(res,user,req.secure);res.json({id:user.id,email:user.email,is_admin:user.is_admin});
});
app.post('/api/auth/logout',authenticate,async(req,res)=>{
  await pool.query('UPDATE sessions SET revoked_at=now() WHERE token_hash=$1',[req.sessionHash]);
  res.clearCookie(cookieName,{httpOnly:true,secure:req.secure,sameSite:'strict',path:'/'});res.json({ok:true});
});
app.get('/api/me',authenticate,(req,res)=>res.json(req.user));
app.use('/api',authenticate);
app.param('id',(req,res,next,id)=>/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)?next():res.status(404).json({error:'Not found.'}));
app.get('/api/records',async(req,res)=>res.json((await pool.query('SELECT * FROM records WHERE owner_id=$1 ORDER BY created_at',[req.user.id])).rows));
app.get('/api/records/:id',async(req,res)=>{
  const record=(await pool.query('SELECT * FROM records WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id])).rows[0];
  record?res.json(record):res.status(404).json({error:'Not found.'});
});
function recordInput(body) {
  if(typeof body.title!=='string'||!body.title.trim()||body.title.length>200||('description'in body&&typeof body.description!=='string'))return null;
  return {title:body.title.trim(),description:body.description??''};
}
app.post('/api/records',mutationsAllowed,async(req,res)=>{
  const value=recordInput(req.body);if(!value)return res.status(400).json({error:'A title of 1 to 200 characters is required.'});
  res.status(201).json((await pool.query('INSERT INTO records(id,owner_id,title,description) VALUES($1,$2,$3,$4) RETURNING *',[randomUUID(),req.user.id,value.title,value.description])).rows[0]);
});
app.patch('/api/records/:id',mutationsAllowed,async(req,res)=>{
  const value=recordInput(req.body);if(!value)return res.status(400).json({error:'A valid title and description are required.'});
  const row=(await pool.query('UPDATE records SET title=$3,description=COALESCE($4,description),updated_at=now() WHERE id=$1 AND owner_id=$2 RETURNING *',[req.params.id,req.user.id,value.title,req.body.description??null])).rows[0];
  row?res.json(row):res.status(404).json({error:'Not found.'});
});
app.delete('/api/records/:id',mutationsAllowed,async(req,res)=>{
  const result=await pool.query('DELETE FROM records WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id]);
  result.rowCount?res.json({ok:true}):res.status(404).json({error:'Not found.'});
});
app.get('/api/documents',async(req,res)=>res.json((await pool.query('SELECT * FROM documents WHERE owner_id=$1 ORDER BY created_at',[req.user.id])).rows));
app.post('/api/documents',mutationsAllowed,async(req,res)=>{
  if(typeof req.body.content_base64!=='string'||typeof req.body.filename!=='string')return res.status(400).json({error:'A filename and base64 file bytes are required.'});
  const bytes=Buffer.from(req.body.content_base64,'base64');
  const filename=req.body.filename.replaceAll('\\','/').split('/').pop().replace(/[\u0000-\u001f\u007f]/g,'').slice(0,255);
  if(!filename||bytes.length<1||bytes.length>maximumDocumentBytes||bytes.toString('base64')!==req.body.content_base64)return res.status(400).json({error:'Choose a file between 1 byte and 1 MiB.'});
  const id=randomUUID(),key=`private/${req.user.id}/${id}`;
  await storage.upload(key,bytes);
  try {
    const row=(await pool.query('INSERT INTO documents(id,owner_id,filename,object_key,sha256,byte_length) VALUES($1,$2,$3,$4,$5,$6) RETURNING *',[id,req.user.id,filename,key,hash(bytes),bytes.length])).rows[0];
    res.status(201).json(row);
  } catch(error) {await storage.remove(key);throw error;}
});
app.get('/api/documents/:id/download',async(req,res)=>{
  const row=(await pool.query('SELECT * FROM documents WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id])).rows[0];
  if(!row)return res.status(404).json({error:'Not found.'});
  const bytes=await storage.download(row.object_key);
  if(hash(bytes)!==row.sha256)return res.status(502).json({error:'Stored document integrity check failed.'});
  res.set({'Content-Type':'application/octet-stream','X-Content-Type-Options':'nosniff','Content-Disposition':`attachment; filename*=UTF-8''${encodeURIComponent(row.filename)}`}).send(bytes);
});
app.get('/api/jobs',async(req,res)=>res.json((await pool.query('SELECT * FROM jobs WHERE owner_id=$1 ORDER BY created_at',[req.user.id])).rows));
app.get('/api/jobs/:id',async(req,res)=>{
  const row=(await pool.query('SELECT * FROM jobs WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id])).rows[0];
  row?res.json(row):res.status(404).json({error:'Not found.'});
});
app.post('/api/jobs',mutationsAllowed,async(req,res)=>res.status(201).json((await pool.query('INSERT INTO jobs(id,owner_id) VALUES($1,$2) RETURNING *',[randomUUID(),req.user.id])).rows[0]));
app.get('/api/operations',async(_req,res)=>res.json({controls:(await pool.query('SELECT * FROM controls')).rows[0],schedules:(await pool.query('SELECT * FROM schedules')).rows}));
app.put('/api/operations',admin,async(req,res)=>{
  const allowed=['worker_paused','scheduler_paused','maintenance_enabled'];
  const changes=Object.entries(req.body).filter(([key])=>allowed.includes(key));
  if(!changes.length||changes.some(([,value])=>typeof value!=='boolean'))return res.status(400).json({error:'Send a boolean pause or maintenance setting.'});
  for(const [key,value] of changes)await pool.query(`UPDATE controls SET ${key}=$1 WHERE id=1`,[value]);
  res.json((await pool.query('SELECT * FROM controls')).rows[0]);
});
app.post('/api/operations/schedule/run',admin,async(_req,res)=>res.json(await runSchedule(true)));
app.use('/api',(_req,res)=>res.status(404).json({error:'Route not found.'}));
app.use(express.static(fileURLToPath(new URL('./web',import.meta.url))));
app.use((error,_req,res,_next)=>{console.error('Request failed:',error.code||error.name);res.status(error.status||500).json({error:'The request failed. Check the application console.'});});

const server=app.listen(Number(process.env.PORT||5000),'0.0.0.0',()=>console.log('Portal listening.'));
for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{server.close(()=>pool.end().then(()=>process.exit(0)));server.closeIdleConnections();setTimeout(()=>process.exit(1),25000).unref();});
