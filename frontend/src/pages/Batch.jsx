import { useEffect, useRef, useState } from 'react'
import { apiRequest } from '../api/client'
import PageHeader from '../components/common/PageHeader'
import ErrorNotice from '../components/common/ErrorNotice'

export default function Batch() {
  const [csv, setCsv] = useState('')
  const [column, setColumn] = useState('company')
  const [batch, setBatch] = useState(null)
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const running = useRef(false)
  useEffect(() => { apiRequest('/api/batches').then(setHistory).catch(e => setError(e.message)); return () => { running.current = false } }, [])
  async function loadFile(e) {
    const file = e.target.files[0]
    if (!file) return
    if (file.size > 262144) { setError('Maximum file size is 256 KiB.'); return }
    setCsv(await file.text()); setError('')
  }
  async function create(e) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const created = await apiRequest('/api/batches', { method: 'POST', body: JSON.stringify({ csv_text: csv, name_column: column }) })
      setBatch(await apiRequest(`/api/batches/${created.id}`))
      setHistory(await apiRequest('/api/batches'))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function run() {
    if (!batch || running.current) return
    running.current = true; setBusy(true); setError('')
    try {
      let next = batch
      while (running.current && next.completed < next.total) {
        next = await apiRequest(`/api/batches/${batch.id}/step`, { method: 'POST' })
        setBatch(next)
      }
    } catch (e) { setError(`${e.message}. Progress is saved; resume when ready.`) }
    finally { running.current = false; setBusy(false) }
  }
  async function download() {
    try {
      const text = await apiRequest(`/api/batches/${batch.id}/export`)
      const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }))
      const a = document.createElement('a'); a.href = url; a.download = `batch-${batch.id}.csv`; a.click(); URL.revokeObjectURL(url)
    } catch (e) { setError(e.message) }
  }
  return <div className="page-stack">
    <PageHeader eyebrow="Pilot workflow" title="Bulk screening">Upload up to 100 companies. Optional columns: country_code, registration_number, postal_code. Ambiguous matches require analyst review.</PageHeader>
    <ErrorNotice message={error} />
    <form className="panel form-stack" onSubmit={create}>
      <label>CSV file (256 KiB maximum)<input type="file" accept=".csv,text/csv" onChange={loadFile} disabled={busy} /></label>
      <label>Company-name column<input value={column} onChange={e => setColumn(e.target.value)} required /></label>
      <button className="btn btn-primary" disabled={!csv || busy}>Validate and save batch</button>
    </form>
    {batch && <section className="panel form-stack">
      <h2>Batch {batch.id}</h2><p aria-live="polite">{batch.completed} of {batch.total} complete</p>
      <progress value={batch.completed} max={batch.total} aria-label="Batch progress" />
      <div className="hero-actions">
        <button className="btn btn-primary" disabled={busy || batch.completed === batch.total} onClick={run}>Start / resume</button>
        <button className="btn btn-ghost" disabled={!busy} onClick={() => { running.current = false }}>Pause after current company</button>
        <button className="btn btn-ghost" disabled={busy} onClick={async () => { try { setBatch(await apiRequest(`/api/batches/${batch.id}/retry`, { method: 'POST' })) } catch(e) { setError(e.message) } }}>Queue failed rows again</button>
        <button className="btn btn-ghost" onClick={download}>Download results</button>
      </div>
      <p>Keep this page open while processing. Progress survives reloads. Provider limits may pause the batch.</p>
      <div style={{ overflowX: 'auto' }}><table><thead><tr><th>Company</th><th>Status</th><th>Research score</th><th>Issue</th></tr></thead><tbody>
        {batch.rows.map(row => <tr key={row.id}><td>{row.company}</td><td>{row.status}</td><td>{row.score ?? 'Unavailable'}</td><td>{row.error || '—'}</td></tr>)}
      </tbody></table></div>
    </section>}
    <section className="panel"><h2>Saved batches</h2>{history.length ? history.map(b => <button className="btn btn-ghost" disabled={busy} key={b.id} onClick={async () => { try { setBatch(await apiRequest(`/api/batches/${b.id}`)) } catch(e) { setError(e.message) } }}>Batch {b.id}</button>) : <p>No batches yet.</p>}</section>
  </div>
}
