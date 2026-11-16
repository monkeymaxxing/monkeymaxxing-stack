import express from 'express';
import bcrypt from 'bcryptjs';
import {randomBytes,randomUUID,createHash} from 'node:crypto';
import cluster from 'node:cluster';
import {query,transaction,pool} from './database.mjs';
import {putDocument,getDocument,deleteDocument} from './storage.mjs';
const hash=value=>createHash('sha256').update(value).digest('hex');
const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const fail=(status,message)=>Object.assign(new Error(message),{status});
const workers=Number(process.env.WEB_CONCURRENCY||1);
if(!Number.isSafeInteger(workers)||workers<1)throw Error('WEB_CONCURRENCY must be a positive integer');
if(cluster.isPrimary&&workers>1){
 for(let i=0;i<workers;i++)cluster.fork();
 let stopping=false;
 cluster.on('exit',()=>{if(!stopping)cluster.fork();});
 for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{stopping=true;for(const w of Object.values(cluster.workers))w.process.kill(signal);});
}else{await start();}
async function start(){
 const schema=await query("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='records' AND column_name='description') AS added");
 const descriptionEnabled=schema.rows[0].added;
 const app=express();app.disable('x-powered-by');app.set('trust proxy',1);
 app.use((req,res,next)=>{res.set({'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"});
  if(['POST','PUT','PATCH','DELETE'].includes(req.method)&&req.path.startsWith('/api/')){
   if(req.get('X-Portal-Request')!=='true')return res.status(403).json({error:'X-Portal-Request header required'});
   if(req.get('Origin')&&req.get('Origin')!==`${req.protocol}://${req.get('host')}`)return res.status(403).json({error:'Request origin refused'});
  }next();
 });
 app.use(express.json({limit:'16kb'}));
 app.get('/healthz',async(req,res)=>{await query('SELECT 1');res.json({status:'ok',description_enabled:descriptionEnabled,process_id:process.pid});});
 const sessionToken=req=>{const cookie=(req.headers.cookie||'').split(';').find(s=>s.trim().startsWith('portal_session='));return cookie?.trim().slice('portal_session='.length);};
 async function createSession(res,user){const token=randomBytes(32).toString('hex');await query("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES($1,$2,now()+interval '7 days')",[hash(token),user.id]);res.cookie('portal_session',token,{httpOnly:true,secure:process.env.NODE_ENV==='production',sameSite:'strict',path:'/',maxAge:7*86400000});}
 function credentials(req){const email=String(req.body?.email||'').trim().toLowerCase();const password=req.body?.password;
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||email.length>254||typeof password!=='string'||password.length<12||Buffer.byteLength(password)>72)throw fail(400,'Valid email and a password of 12 to 72 bytes required');return {email,password};}
 app.post('/api/register',async(req,res)=>{const {email,password}=credentials(req);const passwordHash=await bcrypt.hash(password,12);
  const user=await transaction(async c=>{await c.query('SELECT pg_advisory_xact_lock(431505)');
   const count=await c.query('SELECT count(*)::integer AS total FROM users');
   return (await c.query('INSERT INTO users(id,email,password_hash,is_admin) VALUES($1,$2,$3,$4) RETURNING id,email,is_admin',[randomUUID(),email,passwordHash,count.rows[0].total===0])).rows[0];
  });await createSession(res,user);res.status(201).json(user);
 });
 app.post('/api/login',async(req,res)=>{const {email,password}=credentials(req);const user=(await query('SELECT * FROM users WHERE email=$1',[email])).rows[0];
  if(!user||!await bcrypt.compare(password,user.password_hash))throw fail(401,'Email or password incorrect');
  await createSession(res,user);res.json({id:user.id,email:user.email,is_admin:user.is_admin});
 });
 app.use('/api',async(req,res,next)=>{const token=sessionToken(req);if(!token)return res.status(401).json({error:'Login required'});
  const user=(await query('SELECT u.id,u.email,u.is_admin FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=$1 AND s.expires_at>now()',[hash(token)])).rows[0];
  if(!user)return res.status(401).json({error:'Login required'});req.user=user;next();
 });
 app.param('id',(req,res,next,id)=>{if(!uuid.test(id))return res.status(404).json({error:'Not found'});next();});
 app.get('/api/me',(req,res)=>res.json({...req.user,description_enabled:descriptionEnabled,process_id:process.pid}));
 app.post('/api/logout',async(req,res)=>{await query('DELETE FROM sessions WHERE token_hash=$1',[hash(sessionToken(req))]);res.clearCookie('portal_session',{path:'/',httpOnly:true,secure:process.env.NODE_ENV==='production',sameSite:'strict'});res.status(204).end();});
 function recordInput(req){const title=typeof req.body?.title==='string'?req.body.title.trim():'';if(!title||title.length>200)throw fail(400,'Record title must contain 1 to 200 characters');const description=req.body?.description??'';if(typeof description!=='string'||description.length>10000)throw fail(400,'Description must be text of at most 10000 characters');return {title,description};}
 app.get('/api/records',async(req,res)=>res.json((await query('SELECT * FROM records WHERE owner_id=$1 ORDER BY created_at',[req.user.id])).rows));
 app.get('/api/records/:id',async(req,res)=>{const row=(await query('SELECT * FROM records WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id])).rows[0];if(!row)throw fail(404,'Not found');res.json(row);});
 app.post('/api/records',async(req,res)=>{const {title,description}=recordInput(req);const values=[randomUUID(),req.user.id,title];if(descriptionEnabled)values.push(description);
  const sql=descriptionEnabled?'INSERT INTO records(id,owner_id,title,description) VALUES($1,$2,$3,$4) RETURNING *':'INSERT INTO records(id,owner_id,title) VALUES($1,$2,$3) RETURNING *';res.status(201).json((await query(sql,values)).rows[0]);
 });
 app.put('/api/records/:id',async(req,res)=>{const {title,description}=recordInput(req);const values=[req.params.id,req.user.id,title];if(descriptionEnabled)values.push(description);
  const row=(await query(`UPDATE records SET title=$3,updated_at=now()${descriptionEnabled?',description=$4':''} WHERE id=$1 AND owner_id=$2 RETURNING *`,values)).rows[0];if(!row)throw fail(404,'Not found');res.json(row);
 });
 app.delete('/api/records/:id',async(req,res)=>{const r=await query('DELETE FROM records WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id]);if(!r.rowCount)throw fail(404,'Not found');res.status(204).end();});
 app.get('/api/documents',async(req,res)=>res.json((await query('SELECT * FROM documents WHERE owner_id=$1 ORDER BY created_at',[req.user.id])).rows));
 // Buffering is bounded to 1 MiB to keep uploads within the trial service memory.
 app.post('/api/documents',express.raw({type:'application/octet-stream',limit:'1mb'}),async(req,res)=>{
  if(!Buffer.isBuffer(req.body)||!req.body.length)throw fail(400,'A nonempty application/octet-stream upload is required');
  const fileName=typeof req.query.file_name==='string'?req.query.file_name:'';if(!fileName||fileName.length>255||/[\r\n/\\]/.test(fileName))throw fail(400,'A plain file_name of 1 to 255 characters is required');
  const id=randomUUID();const key=`private/${req.user.id}/${id}`;const sha256=hash(req.body);await putDocument(key,req.body);
  try{const row=(await query('INSERT INTO documents(id,owner_id,file_name,object_key,sha256,byte_length) VALUES($1,$2,$3,$4,$5,$6) RETURNING *',[id,req.user.id,fileName,key,sha256,req.body.length])).rows[0];res.status(201).json(row);}catch(e){await deleteDocument(key).catch(()=>{});throw e;}
 });
 app.get('/api/documents/:id/download',async(req,res)=>{const row=(await query('SELECT * FROM documents WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id])).rows[0];if(!row)throw fail(404,'Not found');
  const bytes=await getDocument(row.object_key);if(hash(bytes)!==row.sha256||bytes.length!==row.byte_length)throw fail(502,'Stored document integrity check failed');res.set({'Content-Type':'application/octet-stream','Content-Disposition':`attachment; filename*=UTF-8''${encodeURIComponent(row.file_name)}`}).send(bytes);
 });
 app.get('/api/jobs',async(req,res)=>res.json((await query('SELECT * FROM jobs WHERE owner_id=$1 ORDER BY created_at',[req.user.id])).rows));
 app.post('/api/jobs',async(req,res)=>res.status(201).json((await query('INSERT INTO jobs(id,owner_id) VALUES($1,$2) RETURNING *',[randomUUID(),req.user.id])).rows[0]));
 app.get('/api/jobs/:id',async(req,res)=>{const row=(await query('SELECT * FROM jobs WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id])).rows[0];if(!row)throw fail(404,'Not found');res.json(row);});
 app.get('/api/jobs/:id/report',async(req,res)=>{const row=(await query('SELECT * FROM jobs WHERE id=$1 AND owner_id=$2',[req.params.id,req.user.id])).rows[0];if(!row)throw fail(404,'Not found');if(row.state!=='COMPLETED')throw fail(409,'Report is pending');res.type('text/plain').send(row.output);});
 app.get('/api/schedule',async(req,res)=>res.json((await query('SELECT * FROM scheduled_runs ORDER BY occurrence_at DESC LIMIT 10')).rows));
 app.get('/api/worker',async(req,res)=>res.json((await query('SELECT worker_paused FROM controls WHERE id=1')).rows[0]));
 app.put('/api/worker',async(req,res)=>{if(!req.user.is_admin)throw fail(403,'Fixture administrator required');if(typeof req.body?.worker_paused!=='boolean')throw fail(400,'worker_paused must be a boolean');res.json((await query('UPDATE controls SET worker_paused=$1 WHERE id=1 RETURNING worker_paused',[req.body.worker_paused])).rows[0]);});
 app.use(express.static(new URL('./web/',import.meta.url).pathname));
 app.use((req,res)=>res.status(404).json({error:'Not found'}));
 app.use((e,req,res,next)=>{const status=e.code==='23505'?409:e.status||500;console.error('request error',status,e.code||e.name);res.status(status).json({error:status===500?'Request failed':e.code==='23505'?'Account already exists':e.message});});
 const server=app.listen(Number(process.env.PORT||8080),'0.0.0.0',()=>console.log('portal listening',process.pid));
 for(const signal of ['SIGTERM','SIGINT'])process.once(signal,()=>{server.close(async()=>{await pool.end();process.exit(0);});setTimeout(()=>process.exit(1),12000).unref();});
}
