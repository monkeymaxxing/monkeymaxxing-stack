import {createHash} from 'node:crypto';
if (!['development', 'staging'].includes(process.env.APP_ENV)) {
  throw new Error('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data');
}
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '--accounts' || !/^\d+$/.test(args[1]) || BigInt(args[1]) < 2n)) {
  throw new Error('Usage: seed-test-data [--accounts N]; --accounts must be a whole number of at least 2');
}
const accounts = args[1] || '2';

if(!process.env.FIXTURE_PASSWORD||!process.env.APP_URL)throw Error('APP_URL and FIXTURE_PASSWORD are required');
for(const [person,description] of [['Barbara','First synthetic record'],['Michael','Second synthetic record']]){
 let cookie='';
 async function request(path,method='GET',body,raw=false){
  const response=await fetch(new URL('/api'+path,process.env.APP_URL),{method,headers:{'X-Portal-Request':'true',...(cookie?{Cookie:cookie}:{}),...(body!==undefined?{'Content-Type':raw?'application/octet-stream':'application/json'}:{})},body:body===undefined?undefined:raw?body:JSON.stringify(body)});
  const next=response.headers.get('set-cookie');if(next)cookie=next.split(';')[0];
  return response;
 }
 const account={email:person.toLowerCase()+'@example.com',password:process.env.FIXTURE_PASSWORD};
 let response=await request('/register','POST',account);
 if(response.status===409)response=await request('/login','POST',account);
 if(!response.ok)throw Error('Test account access failed: '+response.status);
 const me=await(await request('/me')).json();
 const records=await(await request('/records')).json();
 if(!records.some(r=>r.title===person+' invoice')){response=await request('/records','POST',{title:person+' invoice',...(me.description_enabled?{description}:{})});if(!response.ok)throw Error('Test record failed');}
 const bytes=Buffer.from(person+' synthetic document\n');const sha256=createHash('sha256').update(bytes).digest('hex');
 const documents=await(await request('/documents')).json();
 if(!documents.some(d=>d.file_name===person.toLowerCase()+'-note.txt'&&d.sha256===sha256)){
  response=await request('/documents?file_name='+person.toLowerCase()+'-note.txt','POST',bytes,true);if(!response.ok)throw Error('Test document failed');
 }
 const jobs=await(await request('/jobs')).json();if(!jobs.length){response=await request('/jobs','POST',{});if(!response.ok)throw Error('Test job failed');}
 await request('/logout','POST',{});console.log('test fixture checked',account.email);
}

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
      await client.query(`INSERT INTO records(id,owner_id,title,description)
        SELECT gen_random_uuid(), u.id, 'Test record ' || n, 'Generated test record' FROM users u
        JOIN generate_series(3,$1::bigint) n ON u.email='test-account-' || lpad(n::text,greatest(6,length(n::text)),'0') || '@example.com'
        WHERE NOT EXISTS (SELECT 1 FROM records r WHERE r.owner_id=u.id)`, [accounts]);
    });
  } finally { await pool.end(); }
}
