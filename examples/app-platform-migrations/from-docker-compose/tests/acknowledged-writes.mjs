import { appendFile, access } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';
import assert from 'node:assert/strict';
const base=process.env.APP_URL;
const interval=Number(process.env.WRITE_INTERVAL_MS||100);
assert.ok(Number.isInteger(interval)&&interval>0,'WRITE_INTERVAL_MS must be a positive integer');
const login=await fetch(base+'/api/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email:'barbara@example.com',password:process.env.FIXTURE_PASSWORD})});
assert.equal(login.status,200);
const cookie=login.headers.get('set-cookie').split(';')[0];
const prefix=process.env.WRITE_PREFIX || 'Acknowledged migration write';
for(let number=0;;number++){
 try{await access(process.env.WRITER_STOP_FILE);break;}catch(error){if(error.code!=='ENOENT')throw error;}
 const started_at=Date.now();const title=prefix+' '+number;
 let http_status_code='connection_error',record_id=null;
 try{
  const response=await fetch(base+'/api/records',{method:'POST',headers:{cookie,'content-type':'application/json'},body:JSON.stringify({title}),signal:AbortSignal.timeout(5000)});
  http_status_code=response.status;
  const text=await response.text();
  if(http_status_code===201){record_id=JSON.parse(text).id;assert.match(record_id,/^[0-9a-f-]{36}$/);}
 }catch(error){if(http_status_code===201)throw error;}
 await appendFile(process.env.WRITER_RESULT_FILE,JSON.stringify({started_at,finished_at:Date.now(),http_status_code,record_id,title})+'\n',{mode:0o600});
 // Each request is distinct. Never replay a mutation whose reply was lost.
 await delay(interval);
}
console.log('Acknowledged-write collection stopped');
