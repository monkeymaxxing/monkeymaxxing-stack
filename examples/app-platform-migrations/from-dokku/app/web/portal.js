const element = id => document.getElementById(id);
function notice(text) { element('notice').textContent = text; }
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error);
  return value;
}
const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
function button(text, action) {
  const item = document.createElement('button'); item.textContent = text;
  item.onclick = () => action().catch(error => notice(error.message)); return item;
}
async function refresh() {
  let user;
  try { user = await api('/api/me'); }
  catch { element('account').hidden = false; element('portal').hidden = true; return; }
  element('account').hidden = true; element('portal').hidden = false; element('identity').textContent = user.email;
  const [records, documents, reports] = await Promise.all(['/api/records', '/api/documents', '/api/reports'].map(path => api(path)));
  element('records').replaceChildren();
  for (const record of records) {
    const item = document.createElement('li');
    const title = document.createElement('input'); title.value = record.title; title.setAttribute('aria-label', 'Record title');
    item.append(title);
    let description;
    if ('description' in record) { description = document.createElement('textarea'); description.value = record.description; description.setAttribute('aria-label', 'Record description'); item.append(description); }
    item.append(button('Save record', async () => { await api(`/api/records/${record.id}`, json('PATCH', { title: title.value, ...(description ? { description: description.value } : {}) })); notice('Record saved.'); await refresh(); }));
    item.append(button('Delete record', async () => { await api(`/api/records/${record.id}`, { method: 'DELETE' }); notice('Record deleted.'); await refresh(); }));
    element('records').append(item);
  }
  element('documents').replaceChildren();
  for (const documentRow of documents) {
    const item = document.createElement('li'); const link = document.createElement('a');
    link.href = `/api/documents/${documentRow.id}`; link.textContent = documentRow.file_name; item.append(link); element('documents').append(item);
  }
  element('reports').replaceChildren();
  for (const report of reports) { const item = document.createElement('li'); item.textContent = `${report.state}: ${report.output || 'Waiting for a report worker.'}`; element('reports').append(item); }
}
element('credentials').onsubmit = async event => {
  event.preventDefault();
  try { const data = new FormData(event.target); await api(`/api/${event.submitter.value}`, json('POST', Object.fromEntries(data))); event.target.password.value = ''; notice('Signed in.'); await refresh(); }
  catch (error) { notice(error.message); }
};
element('record').onsubmit = async event => {
  event.preventDefault();
  try { await api('/api/records', json('POST', Object.fromEntries(new FormData(event.target)))); event.target.reset(); notice('Record created.'); await refresh(); }
  catch (error) { notice(error.message); }
};
element('upload').onsubmit = async event => {
  event.preventDefault();
  try {
    const file = new FormData(event.target).get('file');
    const response = await fetch('/api/documents', { method: 'POST', headers: { 'Content-Type': 'application/octet-stream', 'X-File-Name': file.name }, body: file });
    if (!response.ok) throw new Error((await response.json()).error);
    event.target.reset(); notice('Private document uploaded.'); await refresh();
  } catch (error) { notice(error.message); }
};
element('logout').onclick = () => api('/api/logout', { method: 'POST' }).then(() => { notice('Signed out.'); return refresh(); }).catch(error => notice(error.message));
element('report').onclick = () => api('/api/reports', { method: 'POST' }).then(() => { notice('Report queued.'); return refresh(); }).catch(error => notice(error.message));
element('refresh').onclick = () => refresh().catch(error => notice(error.message));
refresh().catch(error => notice(error.message));
