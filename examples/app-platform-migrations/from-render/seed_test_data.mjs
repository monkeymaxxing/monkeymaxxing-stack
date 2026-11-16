import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
if (!['development', 'staging'].includes(process.env.APP_ENV)) {
  throw new Error('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data');
}
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '--accounts' || !/^\d+$/.test(args[1]) || BigInt(args[1]) < 2n)) {
  throw new Error('Usage: seed-test-data [--accounts N]; --accounts must be a whole number of at least 2');
}
const accounts = args[1] || '2';
const base=process.env.APP_URL;if(!base)throw new Error('APP_URL is required');
const password=process.env.FIXTURE_PASSWORD;if(!password)throw new Error('FIXTURE_PASSWORD is required');
const fixtures=[['barbara','Barbara','First'],['michael','Michael','Second']];
for(const [slug,name,ordinal] of fixtures){let cookie;
 async function request(path,body,method=body?'POST':'GET'){
  const r=await fetch(base+'/api'+path,{method,headers:{...(cookie?{cookie}:{}),...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  if(r.status===409&&path==='/auth/register')return null;
  if(!r.ok)throw new Error(method+' '+path+' returned '+r.status);
  const set=r.headers.get('set-cookie');if(set)cookie=set.split(';')[0];return r.json();}
 const credentials={email:slug+'@example.com',password};
 await request('/auth/register',credentials);await request('/auth/login',credentials);
 const records=await request('/records');if(!records.some(x=>x.title===name+' invoice'))await request('/records',{title:name+' invoice'});
 const bytes=Buffer.from(name+' synthetic document\n');const sha=createHash('sha256').update(bytes).digest('hex');
 const docs=await request('/documents');if(!docs.some(x=>x.filename===slug+'-note.txt'&&x.sha256===sha))await request('/documents',{filename:slug+'-note.txt',content_base64:bytes.toString('base64')});
 const jobs=await request('/jobs');if(!jobs.some(x=>x.state==='PENDING'))await request('/jobs',{});
 await request('/auth/logout',{});console.log('Synthetic fixture ready:',slug+'@example.com');}

if (BigInt(accounts) > 2n) {
  const {pool,transaction} = await import('./database.mjs');
  const {default:bcrypt} = await import('bcryptjs');
  try {
    const passwordHash = await bcrypt.hash(process.env.FIXTURE_PASSWORD, 12);
    await transaction(async client => {
      await client.query('SELECT pg_advisory_xact_lock(7341206)');
      await client.query(`INSERT INTO users(id,email,password_hash)
        SELECT gen_random_uuid(), 'test-account-' || lpad(n::text, greatest(6,length(n::text)), '0') || '@example.com', $2
        FROM generate_series(3,$1::bigint) AS n ON CONFLICT (email) DO NOTHING`, [accounts,passwordHash]);
      await client.query(`INSERT INTO identities(user_id,issuer,subject)
        SELECT u.id, 'application-password', u.id::text FROM users u
        JOIN generate_series(3,$1::bigint) n ON u.email='test-account-' || lpad(n::text,greatest(6,length(n::text)),'0') || '@example.com'
        ON CONFLICT DO NOTHING`, [accounts]);
      await client.query(`INSERT INTO records(id,owner_id,title,description)
        SELECT gen_random_uuid(), u.id, 'Test record ' || n, 'Generated test record' FROM users u
        JOIN generate_series(3,$1::bigint) n ON u.email='test-account-' || lpad(n::text,greatest(6,length(n::text)),'0') || '@example.com'
        WHERE NOT EXISTS (SELECT 1 FROM records r WHERE r.owner_id=u.id)`, [accounts]);
    });
  } finally { await pool.end(); }
}
