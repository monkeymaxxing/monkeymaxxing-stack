const el=id=>document.getElementById(id);
async function api(path,body,method=body?'POST':'GET'){const r=await fetch('/api'+path,{method,headers:body?{'Content-Type':'application/json'}:{},...(body?{body:JSON.stringify(body)}:{})});const d=await r.json();if(!r.ok)throw Error(d.error);return d;}
function task(fn){return async e=>{e?.preventDefault();try{el('message').textContent='';await fn();}catch(e){el('message').textContent=e.message;}};}
function action(label,fn){const b=document.createElement('button');b.textContent=label;b.onclick=task(fn);return b;}
async function refresh(){const me=await api('/me');el('auth').hidden=true;el('portal').hidden=false;el('identity').textContent=me.email;
 for(const type of ['records','documents','jobs']){const rows=await api('/'+type);el(type).replaceChildren();for(const row of rows){const li=document.createElement('li');li.textContent=type==='records'?`${row.title}: ${row.description||''}`:type==='documents'?row.filename:`${row.state}: ${row.output||'Waiting for worker'}`;
 if(type==='records'){li.append(action('Edit',async()=>{const title=prompt('Record title',row.title);if(title===null)return;const description=prompt('Description',row.description||'');if(description===null)return;await api('/records/'+row.id,{title,description},'PATCH');await refresh();}),action('Delete',async()=>{await api('/records/'+row.id,undefined,'DELETE');await refresh();}));}
 if(type==='documents')li.append(action('Download',async()=>{const r=await fetch('/api/documents/'+row.id+'/download');if(!r.ok)throw Error('Download failed');const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download=row.filename;a.click();URL.revokeObjectURL(url);}));el(type).append(li);}}
 const s=await api('/schedules');el('schedule').textContent=s.map(x=>`${x.id}: ${x.cron_expression} UTC; last run ${x.last_run_at||'not yet run'}`).join('; ');}
for(const name of ['register','login'])el(name).onclick=task(async()=>{await api('/auth/'+name,{email:el('email').value,password:el('password').value});el('password').value='';await refresh();});
el('logout').onclick=task(async()=>{await api('/auth/logout',{});el('auth').hidden=false;el('portal').hidden=true;});
el('record-form').onsubmit=task(async()=>{await api('/records',{title:el('title').value,description:el('description').value});await refresh();});
el('upload').onclick=task(async()=>{const file=el('document').files[0];if(!file)throw Error('Choose a document');if(file.size>1048576)throw Error('Document exceeds the 1 MiB buffered transfer limit');const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);await api('/documents',{filename:file.name,content_base64:btoa(binary)});await refresh();});
el('queue').onclick=task(async()=>{await api('/jobs',{});await refresh();});
refresh().catch(()=>{});
