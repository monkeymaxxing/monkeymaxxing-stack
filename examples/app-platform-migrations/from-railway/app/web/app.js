const el=id=>document.getElementById(id);let me;
async function api(path,method='GET',body){const opts={method,headers:{'X-Portal-Request':'true'}};if(body!==undefined){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body);}const r=await fetch('/api'+path,opts);if(!r.ok){const e=await r.json();throw Error(e.error);}return r.status===204?null:r.json();}
function message(text){el('message').textContent=text;}
function action(fn){return async e=>{e?.preventDefault();try{await fn(e);}catch(e){message(e.message);}};}
function button(text,fn){const b=document.createElement('button');b.textContent=text;b.onclick=action(fn);return b;}
async function refresh(){
 me=await api('/me');el('auth').hidden=true;el('portal').hidden=false;el('identity').textContent=me.email;el('description-label').hidden=!me.description_enabled;
 const [records,documents,jobs,schedule,worker]=await Promise.all([api('/records'),api('/documents'),api('/jobs'),api('/schedule'),api('/worker')]);
 el('records').replaceChildren(...records.map(r=>{const li=document.createElement('li');const text=document.createElement('span');text.textContent=r.title+(r.description?' — '+r.description:'')+' ';li.append(text,button('Edit',async()=>{const title=prompt('Record title',r.title);if(title===null)return;const description=me.description_enabled?prompt('Description',r.description||''):'';if(description===null)return;await api('/records/'+r.id,'PUT',{title,description});await refresh();}),button('Delete',async()=>{if(!confirm('Delete this record?'))return;await api('/records/'+r.id,'DELETE');await refresh();}));return li;}));
 el('documents').replaceChildren(...documents.map(d=>{const li=document.createElement('li');const a=document.createElement('a');a.href='/api/documents/'+d.id+'/download';a.textContent=d.file_name+' ('+d.byte_length+' bytes)';li.append(a);return li;}));
 el('jobs').replaceChildren(...jobs.map(j=>{const li=document.createElement('li');li.textContent=j.state+' '+j.id+' ';if(j.state==='COMPLETED'){const a=document.createElement('a');a.href='/api/jobs/'+j.id+'/report';a.textContent='View report';li.append(a);}return li;}));
 el('worker-state').textContent=worker.worker_paused?'Reports and scheduled tasks are paused.':'Reports and scheduled tasks are running.';
 el('pause-worker').hidden=!me.is_admin;el('pause-worker').textContent=worker.worker_paused?'Resume worker':'Pause worker';el('pause-worker').onclick=action(async()=>{await api('/worker','PUT',{worker_paused:!worker.worker_paused});await refresh();});
 el('schedule').textContent=schedule.length?JSON.stringify(schedule,null,2):'No completed scheduled run yet.';
}
el('account-form').onsubmit=action(async e=>{await api('/'+e.submitter.value,'POST',{email:el('email').value,password:el('password').value});el('password').value='';message('Signed in.');await refresh();});
el('logout').onclick=action(async()=>{await api('/logout','POST',{});el('portal').hidden=true;el('auth').hidden=false;message('Signed out.');});
el('record-form').onsubmit=action(async()=>{await api('/records','POST',{title:el('title').value,description:el('description').value});el('title').value='';el('description').value='';message('Record created.');await refresh();});
el('document-form').onsubmit=action(async()=>{const file=el('document-file').files[0];if(file.size>1048576)throw Error('Document must be no larger than 1 MiB.');const r=await fetch('/api/documents?file_name='+encodeURIComponent(file.name),{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Portal-Request':'true'},body:file});if(!r.ok)throw Error((await r.json()).error);message('Document uploaded.');el('document-form').reset();await refresh();});
el('queue-report').onclick=action(async()=>{await api('/jobs','POST',{});message('Report queued.');await refresh();});el('refresh').onclick=action(refresh);
refresh().catch(()=>{});
