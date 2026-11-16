import express from 'express';
import bcrypt from 'bcryptjs';
import { randomUUID, randomBytes, createHash } from 'node:crypto';
import cluster from 'node:cluster';
import { pool, transaction } from './database.mjs';
import { putObject, getObject, deleteObject } from './storage.mjs';
const concurrency=Number(process.env.WEB_CONCURRENCY||1);
if(!Number.isInteger(concurrency)||concurrency<1)throw Error('WEB_CONCURRENCY must be a positive integer');
const hash=value=>createHash('sha256').update(value).digest('hex');
if(cluster.isPrimary && concurrency>1){
 for(let i=0;i<concurrency;i++)cluster.fork();
 let stopping=false;
 cluster.on('exit',()=>{if(!stopping)cluster.fork();});
 for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{stopping=true;for(const w of Object.values(cluster.workers))w.kill(signal);});
}else{
 const app=express();app.disable('x-powered-by');app.set('trust proxy',1);
 app.use((req,res,next)=>{
  res.set('X-Content-Type-Options','nosniff');res.set('Cache-Control','no-store');
  res.set('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'");
  if(!['GET','HEAD','OPTIONS'].includes(req.method)&&req.get('origin')){
   if(req.get('origin')!==`${req.protocol}://${req.get('host')}`)return res.status(403).json({error:'Request origin refused'});
  }
  next();
 });
 app.use(express.json({limit:'32kb'}));
 app.use(async(req,res,next)=>{if(!['GET','HEAD','OPTIONS'].includes(req.method)){const r=await pool.query('SELECT maintenance FROM controls WHERE id=1');if(r.rows[0].maintenance)return res.status(503).json({error:'Maintenance: writes are paused'});}next();});
 const cookieOptions={httpOnly:true,sameSite:'strict',secure:process.env.COOKIE_SECURE!=='false',path:'/',maxAge:86400000};
 const sessionToken=req=>{const m=(req.headers.cookie||'').match(/(?:^|;\s*)portal_session=([^;]+)/);return m?.[1];};
 async function issueSession(res,id){const token=randomBytes(32).toString('hex');await pool.query("INSERT INTO sessions(token_hash,owner_id,expires_at) VALUES($1,$2,now()+interval '1 day')",[hash(token),id]);res.cookie('portal_session',token,cookieOptions);}
 app.get('/healthz',async(req,res)=>{await pool.query('SELECT 1');res.json({status:'ok',server:process.env.PORT||'local'});});
 app.post('/api/register',async(req,res)=>{
  const {email,password}=req.body||{};
  if(typeof email!=='string'||! /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||typeof password!=='string'||password.length<12||Buffer.byteLength(password)>72)return res.status(400).json({error:'Use an email and a password of 12 to 72 bytes'});
  const id=randomUUID();const passwordHash=await bcrypt.hash(password,12);
  try {await pool.query('INSERT INTO users(id,email,password_hash) VALUES($1,$2,$3)',[id,email.toLowerCase(),passwordHash]);}
  catch(e){if(e.code==='23505')return res.status(409).json({error:'Account already exists'});throw e;}
  res.status(201).json({id,email:email.toLowerCase()});
 });
 app.post('/api/login',async(req,res)=>{
  const {email,password}=req.body||{};
  if(typeof email!=='string'||typeof password!=='string')return res.status(400).json({error:'Email and password are required'});
  const user=(await pool.query('SELECT * FROM users WHERE email=$1',[email.toLowerCase()])).rows[0];
  if(!user||!await bcrypt.compare(password,user.password_hash))return res.status(401).json({error:'Email or password refused'});
  await issueSession(res,user.id);res.json({id:user.id,email:user.email});
 });
 app.use('/api',async(req,res,next)=>{
  const token=sessionToken(req);if(!token)return res.status(401).json({error:'Please log in'});
  const session=await pool.query('SELECT u.id,u.email FROM sessions s JOIN users u ON u.id=s.owner_id WHERE s.token_hash=$1 AND s.expires_at>now()',[hash(token)]);
  if(!session.rowCount)return res.status(401).json({error:'Please log in'});
  req.user=session.rows[0];
  next();
 });
 app.get('/api/me',(req,res)=>res.json(req.user));
 app.post('/api/logout',async(req,res)=>{await pool.query('DELETE FROM sessions WHERE token_hash=$1',[hash(sessionToken(req))]);res.clearCookie('portal_session',{...cookieOptions,maxAge:undefined});res.json({logged_out:true});});
 app.get('/api/records',async(req,res)=>res.json((await pool.query('SELECT * FROM records WHERE owner_id=$1 ORDER BY created_at',[req.user.id])).rows));
 app.post('/api/records',async(req,res)=>{
  if(typeof req.body?.title!=='string'||!req.body.title.trim())return res.status(400).json({error:'Record title is required'});
  const id=randomUUID();const row=await pool.query('INSERT INTO records(id,owner_id,title) VALUES($1,$2,$3) RETURNING *',[id,req.user.id,req.body.title]);
  res.status(201).json(row.rows[0]);
 });
 app.get('/api/records/:id',async(req,res)=>{const r=await pool.query('SELECT * FROM records WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id]);if(!r.rowCount)return res.sendStatus(404);res.json(r.rows[0]);});
 app.patch('/api/records/:id',async(req,res)=>{
  const {title,description}=req.body||{};
  if(typeof title!=='string'||!title.trim()||(description!==undefined&&typeof description!=='string'))return res.status(400).json({error:'Record title and description must be text'});
  const r=description===undefined?await pool.query('UPDATE records SET title=$3 WHERE id=$1 AND owner_id=$2 RETURNING *',[req.params.id,req.user.id,title]):await pool.query('UPDATE records SET title=$3,description=$4 WHERE id=$1 AND owner_id=$2 RETURNING *',[req.params.id,req.user.id,title,description]);
  if(!r.rowCount)return res.sendStatus(404);res.json(r.rows[0]);
 });
 app.delete('/api/records/:id',async(req,res)=>{const r=await pool.query('DELETE FROM records WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id]);res.sendStatus(r.rowCount?204:404);});
 app.get('/api/documents',async(req,res)=>res.json((await pool.query('SELECT * FROM documents WHERE owner_id=$1 ORDER BY created_at',[req.user.id])).rows));
 // Buffers at most 1 MiB per request because this example uses in-memory S3 transfers.
 app.post('/api/documents',express.raw({type:'application/octet-stream',limit:'1mb'}),async(req,res)=>{
  const name=req.query.file_name;if(typeof name!=='string'||!name||name.includes('/')||name.includes('\\')||/[\r\n]/.test(name))return res.status(400).json({error:'Use a simple document file name'});
  if(!Buffer.isBuffer(req.body))return res.status(400).json({error:'Send application/octet-stream bytes'});
  const id=randomUUID(),key=`private/${req.user.id}/${id}`,digest=hash(req.body);
  await putObject(key,req.body);
  let row;
  try {row=await pool.query('INSERT INTO documents(id,owner_id,file_name,object_key,sha256,byte_length) VALUES($1,$2,$3,$4,$5,$6) RETURNING *',[id,req.user.id,name,key,digest,req.body.length]);}
  catch(e){await deleteObject(key);throw e;}
  res.status(201).json(row.rows[0]);
 });
 app.get('/api/documents/:id',async(req,res)=>{
  const r=await pool.query('SELECT * FROM documents WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id]);if(!r.rowCount)return res.sendStatus(404);
  const bytes=await getObject(r.rows[0].object_key);
  if(hash(bytes)!==r.rows[0].sha256)throw Error('Stored document hash mismatch');
  res.type('application/octet-stream').set('Content-Disposition',`attachment; filename*=UTF-8''${encodeURIComponent(r.rows[0].file_name)}`).send(bytes);
 });
 app.get('/api/reports',async(req,res)=>res.json((await pool.query('SELECT * FROM report_jobs WHERE owner_id=$1 ORDER BY created_at',[req.user.id])).rows));
 app.get('/api/reports/:id',async(req,res)=>{const r=await pool.query('SELECT * FROM report_jobs WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id]);if(!r.rowCount)return res.sendStatus(404);res.json(r.rows[0]);});
 app.post('/api/reports',async(req,res)=>{const r=await pool.query('INSERT INTO report_jobs(id,owner_id) VALUES($1,$2) RETURNING *',[randomUUID(),req.user.id]);res.status(202).json(r.rows[0]);});
 app.use(express.static(new URL('./web/',import.meta.url).pathname));
 app.use((error,req,res,next)=>{console.error('Request failed:',error.code||error.name);if(res.headersSent)return next(error);res.status(error.type==='entity.too.large'?413:error.type==='entity.parse.failed'||error.code==='22P02'?400:500).json({error:'Request could not be completed'});});
 const server=app.listen(Number(process.env.PORT||8080),'0.0.0.0',()=>console.log('Customer portal listening'));
 for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{server.close(async()=>{await pool.end();process.exit(0);});setTimeout(()=>process.exit(1),10000).unref();});
}
