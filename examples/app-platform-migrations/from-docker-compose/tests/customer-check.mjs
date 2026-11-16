import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const base=process.env.APP_URL;
const results=[];
async function request(path,{method='GET',cookie,body,raw,status=200}={}){
 const headers={};if(cookie)headers.cookie=cookie;
 if(body!==undefined){headers['content-type']='application/json';raw=JSON.stringify(body);}
 else if(raw!==undefined)headers['content-type']='application/octet-stream';
 const r=await fetch(base+path,{method,headers,body:raw});assert.equal(r.status,status,method+' '+path);
 const bytes=Buffer.from(await r.arrayBuffer());let value;try{value=JSON.parse(bytes);}catch{value=bytes;}
 return {value,bytes,cookie:r.headers.get('set-cookie')?.split(';')[0]};
}
const baseline=process.env.BASELINE_FILE?JSON.parse(await readFile(process.env.BASELINE_FILE,'utf8')):null;
for(const person of ['Barbara','Michael']){
 const email=person.toLowerCase()+'@example.com';
 const login=await request('/api/login',{method:'POST',body:{email,password:process.env.FIXTURE_PASSWORD}});
 const cookie=login.cookie;const user=login.value;
 const records=(await request('/api/records',{cookie})).value;
 const original=records.find(r=>r.title===person+' invoice');assert.ok(original,'Original owned record survived');assert.equal(original.owner_id,user.id);
 const docs=(await request('/api/documents',{cookie})).value;
 const document=docs.find(d=>d.file_name===person.toLowerCase()+'-note.txt');assert.ok(document);
 const bytes=(await request('/api/documents/'+document.id,{cookie})).bytes;
 assert.equal(bytes.toString(),person+' synthetic document\n');assert.equal(createHash('sha256').update(bytes).digest('hex'),document.sha256);
 const reports=(await request('/api/reports',{cookie})).value;assert.ok(reports.length>=1);
 const identity={email,id:user.id,record_id:original.id,document_id:document.id,object_key:document.object_key,sha256:document.sha256,report_id:reports[0].id};
 if(baseline)assert.deepEqual(identity,baseline.find(u=>u.email===email),'Stable identities and owner-linked objects');
 results.push({...identity,cookie});
}
for(const [current,foreign] of [[results[0],results[1]],[results[1],results[0]]]){
 for(const path of ['/api/records/'+foreign.record_id,'/api/documents/'+foreign.document_id,'/api/reports/'+foreign.report_id])await request(path,{cookie:current.cookie,status:404});
}
const cookie=results[0].cookie;
const record=(await request('/api/records',{method:'POST',cookie,body:{title:'Customer check temporary'},status:201})).value;
await request('/api/records/'+record.id,{method:'PATCH',cookie,body:{title:'Customer check edited',description:'Destination write'}});
await request('/api/records/'+record.id,{method:'DELETE',cookie,status:204});
const uploaded=(await request('/api/documents?file_name=customer-check.txt',{method:'POST',cookie,raw:'New destination private bytes\n',status:201})).value;
assert.equal((await request('/api/documents/'+uploaded.id,{cookie})).bytes.toString(),'New destination private bytes\n');
await request('/api/documents/'+uploaded.id,{cookie:results[1].cookie,status:404});
await request('/api/logout',{method:'POST',cookie});await request('/api/me',{cookie,status:401});
for(const user of results)delete user.cookie;
if(process.env.SAVE_BASELINE_FILE)await writeFile(process.env.SAVE_BASELINE_FILE,JSON.stringify(results,null,2)+'\n');
console.log(JSON.stringify({customer_checks_passed:true,accounts:results.length,original_private_documents:results.length,crud:true,private_upload:true,foreign_owner_refused:true,logout_revoked:true}));
