if (!['development', 'staging'].includes(process.env.APP_ENV)) {
  throw new Error('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data');
}
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '--accounts' || !/^\d+$/.test(args[1]) || BigInt(args[1]) < 2n)) {
  throw new Error('Usage: seed-test-data [--accounts N]; --accounts must be a whole number of at least 2');
}
const accounts = args[1] || '2';
if(!process.env.FIXTURE_PASSWORD)throw Error('FIXTURE_PASSWORD is required');
const base=process.env.APP_URL||'http://127.0.0.1:8080';
for(const [person,description] of [['Barbara','First synthetic record'],['Michael','Second synthetic record']]){
 const email=person.toLowerCase()+'@example.com';
 let r=await fetch(base+'/api/register',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email,password:process.env.FIXTURE_PASSWORD})});if(![201,409].includes(r.status))throw Error('Registration failed');
 r=await fetch(base+'/api/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email,password:process.env.FIXTURE_PASSWORD})});if(!r.ok)throw Error('Login failed');const cookie=r.headers.get('set-cookie').split(';')[0];
 const call=async(path,options={})=>{const response=await fetch(base+'/api/'+path,{...options,headers:{cookie,...options.headers}});if(!response.ok)throw Error('Seed request failed: '+path);return response.json();};
 if(!(await call('records')).length){const record=await call('records',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({title:person+' invoice'})});await call('records/'+record.id,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({title:person+' invoice',description})});}
 if(!(await call('documents')).length)await call('documents?file_name='+person.toLowerCase()+'-note.txt',{method:'POST',headers:{'content-type':'application/octet-stream'},body:person+' synthetic document\n'});
 if(!(await call('reports')).length)await call('reports',{method:'POST'});
 await call('logout',{method:'POST'});
}
console.log('Test fixture is present. Existing rows and passwords were preserved.');

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
