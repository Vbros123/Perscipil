import { useState } from 'react'
import { apiRequest } from '../../api/client'
export default function WorkspaceMembers({organization,members,onRefresh}) {
 const [password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('')
 async function change(member,transfer){setBusy(true);setError('');try{await apiRequest(`/api/organizations/${organization.id}/`+(transfer?'ownership':`members/${member.user_id}`),{method:transfer?'POST':'PATCH',body:JSON.stringify(transfer?{user_id:member.user_id,password}:{role:member.role==='admin'?'member':'admin'})});setPassword('');await onRefresh()}catch(e){setError(e.message)}finally{setBusy(false)}}
 if(organization.role!=='owner')return null
 return <section className="panel form-stack"><h2>Manage workspace roles</h2>{error&&<p role="alert">{error}</p>}<label>Confirm password for ownership transfer<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>{members.filter(m=>m.active&&m.role!=='owner').map(m=><div key={m.user_id}>{m.email} · {m.role}<button className="btn" disabled={busy} onClick={()=>change(m,false)}>{m.role==='admin'?'Make member':'Make admin'}</button><button className="btn" disabled={busy||!password} onClick={()=>change(m,true)}>Transfer ownership</button></div>)}</section>
}
