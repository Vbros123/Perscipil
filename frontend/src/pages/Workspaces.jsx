import { useEffect, useRef, useState } from 'react'
import { apiRequest } from '../api/client'
import PageHeader from '../components/common/PageHeader'
import ErrorNotice from '../components/common/ErrorNotice'

export default function Workspaces() {
  const [list,setList]=useState([]),[selected,setSelected]=useState(''),[name,setName]=useState('')
  const [members,setMembers]=useState([]),[jobs,setJobs]=useState([]),[email,setEmail]=useState(''),[invite,setInvite]=useState('')
  const [token,setToken]=useState(''),[company,setCompany]=useState(''),[csv,setCsv]=useState('company,country_code\n'),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  const [keys,setKeys]=useState([]),[secret,setSecret]=useState(''),[reports,setReports]=useState([])
  const selectedRef=useRef(selected)
  selectedRef.current=selected
  const root=`/api/organizations/${selected}`
  const current=list.find(o=>String(o.id)===String(selected))
  const admin=['owner','admin'].includes(current?.role)
  async function load(){setList(await apiRequest('/api/organizations'))}
  async function refresh(){
    if(!selected)return
    const requested=selected
    const [m,j,r,k]=await Promise.all([apiRequest(root+'/members'),apiRequest(root+'/jobs?limit=100'),apiRequest(root+'/resources?kind=report'),admin?apiRequest(root+'/keys'):Promise.resolve([])])
    if(selectedRef.current!==requested)return
    setMembers(m);setJobs(j.items);setReports(r.items);setKeys(k)
  }
  async function action(fn){setBusy(true);setError('');try{await fn()}catch(e){setError(e.message)}finally{setBusy(false)}}
  useEffect(()=>{load().catch(e=>setError(e.message))},[])
  useEffect(()=>{setSecret('');setInvite('');setMembers([]);setJobs([]);setReports([]);setKeys([]);refresh().catch(e=>setError(e.message))},[selected])
  const post=(path,body)=>apiRequest(path,{method:'POST',body:JSON.stringify(body)})
  return <div className="page-stack">
    <PageHeader title="Team workspaces" eyebrow="Shared research">Personal data stays in your individual workspace. Team research is stored separately.</PageHeader>
    <ErrorNotice message={error}/>
    <form className="panel form-stack" onSubmit={e=>{e.preventDefault();action(async()=>{const o=await post('/api/organizations',{name});await load();setSelected(String(o.id));setName('')})}}>
      <label>New workspace name<input required maxLength={120} value={name} onChange={e=>setName(e.target.value)}/></label><button className="btn btn-primary" disabled={busy}>Create workspace</button>
    </form>
    <form className="panel form-stack" onSubmit={e=>{e.preventDefault();action(async()=>{await post('/api/organizations/invitations/accept',{token});setToken('');await load()})}}><label>Invitation token<input value={token} onChange={e=>setToken(e.target.value)} required autoComplete="off"/></label><p>Your account email must be verified and match the invitation.</p><button className="btn" disabled={busy}>Accept invitation</button></form>
    <label>Selected workspace<select disabled={busy} value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Choose workspace</option>{list.map(o=><option key={o.id} value={o.id}>{o.name} · {o.role}</option>)}</select></label>
    {selected&&<>
      <section className="panel form-stack"><h2>Members</h2>{members.filter(m=>m.active).map(m=><div key={m.user_id}>{m.email} · {m.role} {admin&&m.role!=='owner'&&<button className="btn" disabled={busy} onClick={()=>action(async()=>{await apiRequest(root+`/members/${m.user_id}`,{method:'DELETE'});await refresh()})}>Revoke access</button>}</div>)}
      {admin&&<form className="form-stack" onSubmit={e=>{e.preventDefault();action(async()=>{const r=await post(root+'/invitations',{email});setInvite(r.invitation_token)})}}><label>Invite a member by email<input type="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label><button className="btn" disabled={busy}>Create invitation</button>{invite&&<label>Share this token privately with the invited person<textarea readOnly value={invite}/></label>}</form>}</section>
      <form className="panel form-stack" onSubmit={e=>{e.preventDefault();action(async()=>{await post(root+'/scores',{identity:{legal_name:company},idempotency_key:crypto.randomUUID()});setCompany('');await refresh()})}}><h2>Company screening</h2><label>Company name<input required value={company} onChange={e=>setCompany(e.target.value)}/></label><button className="btn btn-primary" disabled={busy}>Queue screening</button><p>Jobs run on the background worker when activated. Source availability varies.</p></form>
      <form className="panel form-stack" onSubmit={e=>{e.preventDefault();action(async()=>{await post(root+'/batches',{csv_text:csv,idempotency_key:crypto.randomUUID()});await refresh()})}}><h2>Bulk screening</h2><label>CSV · maximum 1,000 rows, 512 KiB<textarea rows={8} required value={csv} onChange={e=>setCsv(e.target.value)}/></label><button className="btn" disabled={busy}>Queue batch</button></form>
      <section className="panel"><h2>Job progress</h2><button className="btn" disabled={busy} onClick={()=>action(refresh)}>Refresh progress</button>{jobs.length===0&&<p>No jobs yet.</p>}{jobs.map(j=><div key={j.id}><strong>{j.company}</strong> · {j.state} · attempts {j.attempts}{j.error_code&&<span> · {j.error_code}</span>}{['queued','retry','running'].includes(j.state)&&<button className="btn" onClick={()=>action(async()=>{await post(root+`/jobs/${j.id}/cancel`,{});await refresh()})}>Cancel</button>}</div>)}</section>
      <section className="panel"><h2>Shared reports</h2>{reports.length===0&&<p>No completed reports yet.</p>}{reports.map(r=><details key={r.id}><summary>{r.payload.company_name||'Company report'} · Research score {r.payload.private_score??'Unavailable'}</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(r.payload,null,2)}</pre></details>)}</section>
      {admin&&<section className="panel form-stack"><h2>Workspace API keys</h2><button className="btn" disabled={busy} onClick={()=>action(async()=>{const k=await post(root+'/keys',{label:'Workspace integration',scopes:['score:read','reports:read']});setSecret(k.key);await refresh()})}>Create API key</button>{secret&&<label>Save this key securely; shown once<textarea readOnly value={secret}/></label>}{keys.map(k=><div key={k.id}>{k.label} · {k.calls} calls · {k.revoked?'Revoked':'Active'}{!k.revoked&&<button className="btn" onClick={()=>action(async()=>{await apiRequest(root+`/keys/${k.id}`,{method:'DELETE'});await refresh()})}>Revoke key</button>}</div>)}</section>}
    </>}
  </div>
}
