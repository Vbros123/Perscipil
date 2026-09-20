import { useEffect, useState } from 'react'
import { API_BASE, apiRequest } from '../api/client'
import PageHeader from '../components/common/PageHeader'
import ErrorNotice from '../components/common/ErrorNotice'

export default function Developer() {
  const [keys,setKeys]=useState([]),[label,setLabel]=useState(''),[secret,setSecret]=useState(''),[error,setError]=useState('')
  const load=()=>apiRequest('/api/keys').then(setKeys)
  useEffect(()=>{load().catch(e=>setError(e.message))},[])
  async function create(e){e.preventDefault();try{const k=await apiRequest('/api/keys',{method:'POST',body:JSON.stringify({label})});setSecret(k.key);setLabel('');await load()}catch(e){setError(e.message)}}
  return <div className="page-stack"><PageHeader eyebrow="Pilot API" title="Developer">Account-scoped public-evidence API. Each key has score:read scope and a 1,000-request lifetime pilot quota. Licensed report redistribution is disabled.</PageHeader><ErrorNotice message={error}/>
    <form className="panel form-stack" onSubmit={create}><label>Key label<input value={label} maxLength={80} required onChange={e=>setLabel(e.target.value)}/></label><button className="btn btn-primary">Create key</button></form>
    {secret && <section className="notice notice-info"><p>Copy this key now. It will not be shown again.</p><code>{secret}</code><button className="btn btn-ghost" onClick={()=>setSecret('')}>Hide key</button></section>}
    <section className="panel"><h2>Your API keys</h2>{keys.length ? keys.map(k=><div key={k.id}><strong>{k.label}</strong> · {k.calls}/1000 requests · {k.revoked?'Revoked':'Active'} {!k.revoked&&<button className="btn btn-ghost" onClick={async()=>{try{await apiRequest(`/api/keys/${k.id}`,{method:'DELETE'});await load()}catch(e){setError(e.message)}}}>Revoke</button>}</div>):<p>No keys yet.</p>}</section>
    <pre className="code-block">{`curl -X POST "${API_BASE}/api/v1/score" \\\n  -H "X-API-Key: <your-key>" \\\n  -H "Content-Type: application/json" \\\n  -d '{"legal_name":"Example Company","country_code":"US"}'`}</pre>
    <p>Rotate a key by creating its replacement, updating your integration, then revoking the old key. A research score is not a default probability or credit rating.</p>
  </div>
}
