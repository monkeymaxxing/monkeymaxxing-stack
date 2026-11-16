const status=document.querySelector('#status');
async function api(path,options={}){const response=await fetch('/api/'+path,options);if(!response.ok)throw Error(`Request failed (${response.status})`);if(response.status===204)return null;return response.json();}
function button(text,action){const b=document.createElement('button');b.textContent=text;b.onclick=()=>run(action);return b;}
async function run(action){try{await action();status.textContent='Saved';await refresh();}catch(error){status.textContent=error.message;}}
const json=body=>({headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
async function refresh(){
 const me=await api('me');document.querySelector('#identity').textContent='Logged in as '+me.email;
 const records=await api('records'),documents=await api('documents'),reports=await api('reports');
 for(const kind of ['records','documents','reports'])document.querySelector('#'+kind).replaceChildren();
 for(const record of records){const li=document.createElement('li');const text=document.createElement('span');text.textContent=record.title+(record.description?' — '+record.description:'');li.append(text,button('Edit',async()=>{const title=prompt('Record title',record.title);if(title===null)return;const description=prompt('Description',record.description||'');if(description===null)return;await api('records/'+record.id,{method:'PATCH',...json({title,description})});}),button('Delete',()=>api('records/'+record.id,{method:'DELETE'})));document.querySelector('#records').append(li);}
 for(const documentRow of documents){const li=document.createElement('li');const a=document.createElement('a');a.textContent=documentRow.file_name;a.href='/api/documents/'+documentRow.id;li.append(a);document.querySelector('#documents').append(li);}
 for(const report of reports){const li=document.createElement('li');li.textContent=report.state+(report.output?' '+report.output:'');document.querySelector('#reports').append(li);}
}
document.querySelector('#account').onsubmit=e=>{e.preventDefault();const form=e.target;run(async()=>{const action=e.submitter.value;await api(action,{method:'POST',...json({email:form.email.value,password:form.password.value})});if(action==='register')await api('login',{method:'POST',...json({email:form.email.value,password:form.password.value})});form.password.value='';});};
document.querySelector('#logout').onclick=async()=>{try{await api('logout',{method:'POST'});document.querySelector('#identity').textContent='Logged out';for(const kind of ['records','documents','reports'])document.querySelector('#'+kind).replaceChildren();status.textContent='Logged out';}catch(error){status.textContent=error.message;}};
document.querySelector('#record').onsubmit=e=>{e.preventDefault();run(async()=>{await api('records',{method:'POST',...json({title:e.target.title.value})});e.target.reset();});};
document.querySelector('#upload').onsubmit=e=>{e.preventDefault();const file=e.target.document.files[0];run(async()=>{await api('documents?file_name='+encodeURIComponent(file.name),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:await file.arrayBuffer()});e.target.reset();});};
document.querySelector('#queue').onclick=()=>run(()=>api('reports',{method:'POST'}));
refresh().catch(()=>{status.textContent='Register or log in to view your private data.';});
