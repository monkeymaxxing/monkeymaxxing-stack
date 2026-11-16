import { randomUUID, createHash } from 'node:crypto';
if (!['development', 'staging'].includes(process.env.APP_ENV)) {
  throw new Error('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data');
}
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '--accounts' || !/^\d+$/.test(args[1]) || BigInt(args[1]) < 2n)) {
  throw new Error('Usage: seed-test-data [--accounts N]; --accounts must be a whole number of at least 2');
}
const accounts = args[1] || '2';
const { pool, transaction } = await import('./database.mjs');
const { upload } = await import('./storage.mjs');
try {
  for (const [name, title, description] of [['Barbara','Barbara invoice','First synthetic record'],['Michael','Michael invoice','Second synthetic record']]) {
    await transaction(async client => {
      await client.query('SELECT pg_advisory_xact_lock(7341206)');
      const email = name.toLowerCase() + '@example.com';
      let user = (await client.query('SELECT id FROM users WHERE email=$1', [email])).rows[0];
      if (!user) {
        const id = randomUUID();
        user = (await client.query('INSERT INTO users(id,email,password_hash,is_admin) VALUES($1,$2,NULL,$3) RETURNING id', [id,email,name==='Barbara'])).rows[0];
        await client.query('INSERT INTO identities(issuer,subject,user_id) VALUES($1,$2,$3)', ['urn:portal:password',user.id,user.id]);
      }
      if (!(await client.query('SELECT id FROM records WHERE owner_id=$1', [user.id])).rowCount) {
        await client.query('INSERT INTO records(id,owner_id,title,description) VALUES($1,$2,$3,$4)', [randomUUID(),user.id,title,description]);
      }
      const filename = name.toLowerCase() + '-note.txt';
      if (!(await client.query('SELECT id FROM documents WHERE owner_id=$1 AND filename=$2', [user.id,filename])).rowCount) {
        const id=randomUUID(),key=`private/${user.id}/${id}`,bytes=Buffer.from(`${name} synthetic document\n`);
        await upload(key,bytes);
        await client.query('INSERT INTO documents(id,owner_id,filename,object_key,sha256,byte_length) VALUES($1,$2,$3,$4,$5,$6)', [id,user.id,filename,key,createHash('sha256').update(bytes).digest('hex'),bytes.length]);
      }
      if (!(await client.query('SELECT id FROM jobs WHERE owner_id=$1', [user.id])).rowCount) {
        await client.query('INSERT INTO jobs(id,owner_id) VALUES($1,$2)', [randomUUID(),user.id]);
      }
    });
  }
  if (BigInt(accounts) > 2n) {
    await transaction(async client => {
      await client.query('SELECT pg_advisory_xact_lock(7341206)');
      await client.query(`INSERT INTO users(id,email,password_hash)
        SELECT gen_random_uuid(), 'test-account-' || lpad(n::text, greatest(6,length(n::text)), '0') || '@example.com', NULL
        FROM generate_series(3,$1::bigint) AS n ON CONFLICT (email) DO NOTHING`, [accounts]);
      await client.query(`INSERT INTO identities(issuer,subject,user_id)
        SELECT 'urn:portal:password', u.id::text, u.id FROM users u
        JOIN generate_series(3,$1::bigint) n ON u.email='test-account-' || lpad(n::text,greatest(6,length(n::text)),'0') || '@example.com'
        ON CONFLICT DO NOTHING`, [accounts]);
      await client.query(`INSERT INTO records(id,owner_id,title,description)
        SELECT gen_random_uuid(), u.id, 'Test record ' || n, 'Generated test record' FROM users u
        JOIN generate_series(3,$1::bigint) n ON u.email='test-account-' || lpad(n::text,greatest(6,length(n::text)),'0') || '@example.com'
        WHERE NOT EXISTS (SELECT 1 FROM records r WHERE r.owner_id=u.id)`, [accounts]);
    });
  }
  console.log('Test data ready. Existing values were preserved.');
} finally { await pool.end(); }
