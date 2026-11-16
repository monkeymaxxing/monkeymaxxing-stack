<script setup>
import { onMounted } from 'vue'
useHead({title:'Private customer portal',htmlAttrs:{lang:'en'},link:[{rel:'stylesheet',href:'/assets/portal.d055d47ecf33.css'}]})
onMounted(() => {

const status = document.getElementById('status');
async function api(path, body) {
 const response = await fetch(path, body ? {method:'POST', body} : {});
 const data = await response.json();
 if (!response.ok) throw new Error(data.error || 'Request failed');
 return data;
}
async function act(task) { try { await task(); status.textContent = 'Saved.'; await refresh(); } catch(error) {status.textContent = error.message;} }
async function refresh() {
 const rows = await api('/records'); const area = document.getElementById('records'); area.replaceChildren();
 for (const row of rows) {
  const entry = document.createElement('div'); const title = document.createElement('input'); title.value=row.title; title.setAttribute('aria-label','Record title');
  const description=document.createElement('textarea'); description.value=row.description; description.setAttribute('aria-label','Record description');
  const update=document.createElement('button'); update.textContent='Update'; update.onclick=()=>act(()=>api(`/records/${row.id}/update`,new URLSearchParams({title:title.value,description:description.value})));
  const remove=document.createElement('button'); remove.textContent='Delete'; remove.onclick=()=>act(()=>api(`/records/${row.id}/delete`,new URLSearchParams()));
  entry.append(title,description,update,remove);area.append(entry);
 }
 const documents=await api('/documents'); const files=document.getElementById('documents');files.replaceChildren();
 for (const file of documents) {const link=document.createElement('a');link.href=`/documents/${file.id}`;link.textContent=file.filename;const p=document.createElement('p');p.append(link);files.append(p);}
 document.getElementById('reports').textContent=(await api('/reports')).map(row=>`${row.id}: ${row.output===null?'Waiting':row.output}`).join('\n');
}
for(const action of ['login','register']) document.querySelector(`[name=${action}]`).onclick=()=>act(()=>api('/'+action,new URLSearchParams(new FormData(document.getElementById('account')))));
document.getElementById('account').onsubmit=event=>event.preventDefault();
document.getElementById('logout').onclick=async()=>{try{await api('/logout',new URLSearchParams());for(const id of ['records','documents','reports']) document.getElementById(id).replaceChildren();status.textContent='Logged out.';}catch(error){status.textContent=error.message;}};
document.getElementById('record').onsubmit=event=>{event.preventDefault();act(()=>api('/records',new URLSearchParams(new FormData(event.target))));};
document.getElementById('document').onsubmit=event=>{event.preventDefault();act(()=>api('/documents',new FormData(event.target)));};
document.getElementById('report').onclick=()=>act(()=>api('/reports',new URLSearchParams()));
document.getElementById('refresh').onclick=()=>act(async()=>{});

})
</script>
<template><main>
<h1>Private customer portal</h1>
<p>Create an account to keep records, upload private documents, and request record-count reports.</p>
<form id="account"><h2>Account</h2><label>Email <input name="email" type="email" required autocomplete="username"></label><label>Password (12 to 72 bytes) <input name="password" type="password" required autocomplete="current-password" minlength="12" maxlength="72"></label><button name="register" type="button">Register</button><button name="login" type="button">Log in</button></form>
<button id="logout">Log out</button>
<form id="record"><h2>Records</h2><label>Title <input name="title" required maxlength="200"></label><label>Description <textarea name="description" maxlength="10000"></textarea></label><button>Save record</button></form>
<div id="records"></div>
<form id="document"><h2>Private documents</h2><label>Document (at most 8 MiB) <input name="file" type="file" required></label><button>Upload</button></form><div id="documents"></div>
<h2>Reports</h2><button id="report">Queue record-count report</button><button id="refresh">Refresh data and reports</button><pre id="reports"></pre><p id="status" role="status" aria-live="polite"></p>

</main></template>
