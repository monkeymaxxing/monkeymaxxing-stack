// Run before and after moving the database, using a protected source-issued session.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
process.umask(0o077);
const source=JSON.parse(await readFile(process.env.SOURCE_SESSION_FILE,'utf8'));
const audit=JSON.parse(await readFile(process.env.EXPORT_DIR+'/table-audit.json','utf8'));
const base=process.env.APP_URL;
async function call(path,{method='GET',body,raw,status=200,cookie=source.cookie}={}){
 const headers={cookie};if(body!==undefined){headers['content-type']='application/json';raw=JSON.stringify(body);}else if(raw!==undefined)headers['content-type']='application/octet-stream';
 const response=await fetch(base+path,{method,headers,body:raw});assert.equal(response.status,status,method+' '+path);
 const bytes=Buffer.from(await response.arrayBuffer());let value;try{value=JSON.parse(bytes);}catch{value=bytes;}return {bytes,value};
}
assert.equal((await call('/api/me')).value.id,source.user.id,'Source-issued session remains valid');
for(const record of audit.records.filter(r=>r.owner_id===source.user.id))assert.equal((await call('/api/records/'+record.id)).value.id,record.id);
for(const document of audit.documents.filter(d=>d.owner_id===source.user.id)){
 const {bytes}=await call('/api/documents/'+document.id);assert.equal(createHash('sha256').update(bytes).digest('hex'),document.sha256);
}
const other=audit.documents.find(d=>d.owner_id!==source.user.id);await call('/api/documents/'+other.id,{status:404});
const checkpointFile=process.env.TRANSITION_CHECKPOINT_FILE;
if(process.argv.includes('--old-database')){
 const record=(await call('/api/records',{method:'POST',body:{title:'Destination write before database replication'},status:201})).value;
 const document=(await call('/api/documents?file_name=transition.txt',{method:'POST',raw:'Private destination bytes written before database replication\n',status:201})).value;
 await writeFile(checkpointFile,JSON.stringify({record,document},null,2)+'\n',{flag:'wx',mode:0o600});
}else{
 const checkpoint=JSON.parse(await readFile(checkpointFile,'utf8'));
 assert.equal((await call('/api/records/'+checkpoint.record.id)).value.owner_id,source.user.id);
 assert.equal((await call('/api/documents/'+checkpoint.document.id)).bytes.toString(),'Private destination bytes written before database replication\n');
 const record=(await call('/api/records',{method:'POST',body:{title:'Standalone destination write'},status:201})).value;
 await call('/api/records/'+record.id,{method:'DELETE',status:204});
}
console.log('Transition customer actions passed: source session, stable IDs, ownership, exact private bytes, and destination writes');
