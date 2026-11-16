'use client'
import { useEffect, useState } from 'react'

export default function Portal() {
  const [signedIn, setSignedIn] = useState(false)
  const [message, setMessage] = useState('')
  const [records, setRecords] = useState([])
  const [documents, setDocuments] = useState([])
  const [reports, setReports] = useState([])
  async function request(path, body) {
    const response = await fetch(path, { method: body === undefined ? 'GET' : 'POST', body, cache: 'no-store' })
    const value = await response.json()
    if (!response.ok) throw new Error(value.error)
    return value
  }
  async function refresh() {
    const values = await Promise.all(['/records', '/documents', '/reports'].map(path => request(path)))
    setRecords(values[0]); setDocuments(values[1]); setReports(values[2]); setSignedIn(true)
  }
  useEffect(() => { refresh().catch(() => {}) }, [])
  async function submit(event, path) {
    event.preventDefault()
    const form = event.currentTarget
    try {
      await request(path, new FormData(form))
      if (path === '/logout') { setSignedIn(false); setMessage('You are logged out.'); return }
      await refresh()
      setMessage('Saved. Refresh reports to see completed work.')
    } catch (error) { setMessage(error.message) }
  }
  return <main>
    <h1>Private customer portal</h1>
    <p>Keep private records and documents. Request a report that counts your records.</p>
    <p role="status">{message}</p>
    {!signedIn ? <>
      {['login', 'register'].map(action => <form key={action} onSubmit={event => submit(event, `/${action}`)}>
        <h2>{action === 'login' ? 'Log in' : 'Create an account'}</h2>
        <p><label>Email <input name="email" type="email" autoComplete="email" required maxLength={254}/></label></p>
        <p><label>Password (12 to 72 bytes) <input name="password" type="password" autoComplete={action === 'login' ? 'current-password' : 'new-password'} required minLength={12} maxLength={72}/></label></p>
        <button>{action === 'login' ? 'Log in' : 'Create account'}</button>
      </form>)}
    </> : <>
      <form onSubmit={event => submit(event, '/logout')}><button>Log out</button></form>
      <h2>Your records</h2>
      <form onSubmit={event => submit(event, '/records')}>
        <p><label>Title <input name="title" required maxLength={200}/></label></p>
        <p><label>Description <textarea name="description" maxLength={4000}/></label></p><button>Add record</button>
      </form>
      {records.map(record => <section key={record.id}>
        <form onSubmit={event => submit(event, `/records/${record.id}/update`)}>
          <p><label>Title <input name="title" defaultValue={record.title} required maxLength={200}/></label></p>
          <p><label>Description <textarea name="description" defaultValue={record.description} maxLength={4000}/></label></p><button>Save record</button>
        </form>
        <form onSubmit={event => submit(event, `/records/${record.id}/delete`)}><button>Delete record</button></form>
      </section>)}
      <h2>Your private documents</h2>
      <form onSubmit={event => submit(event, '/documents')}><label>File (up to 8 MiB) <input name="file" type="file" required/></label><button>Upload</button></form>
      <ul>{documents.map(document => <li key={document.id}><a href={`/documents/${document.id}`}>{document.file_name}</a></li>)}</ul>
      <h2>Your record-count reports</h2>
      <form onSubmit={event => submit(event, '/reports')}><button>Request report</button></form>
      <button onClick={() => refresh().catch(error => setMessage(error.message))}>Refresh reports</button>
      <ul>{reports.map(report => <li key={report.id}>{report.output || 'Waiting for a worker'}</li>)}</ul>
    </>}
  </main>
}
