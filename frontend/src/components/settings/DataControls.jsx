import { useState } from 'react'
import { apiRequest } from '../../api/client'
import { useAuth } from '../../context/AuthContext'

export default function DataControls() {
  const { logout } = useAuth()
  const [password,setPassword]=useState(''),[confirmation,setConfirmation]=useState(''),[error,setError]=useState('')
  async function download(){try{const data=await apiRequest('/api/users/me/export');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='privatelens-account.json';a.click();URL.revokeObjectURL(url)}catch(e){setError(e.message)}}
  async function remove(e){e.preventDefault();try{await apiRequest('/api/users/me',{method:'DELETE',body:JSON.stringify({password,confirmation})});await logout(false)}catch(e){setError(e.message)}}
  return <section className="panel form-stack"><h2>Your data</h2>{error&&<p role="alert">{error}</p>}<button className="btn btn-ghost" onClick={download}>Export account data</button><p>Deleting your account removes saved research and revokes access. De-identified security and policy records are retained. Backups expire separately.</p><form className="form-stack" onSubmit={remove}><label>Current password<input type="password" required value={password} onChange={e=>setPassword(e.target.value)}/></label><label>Type DELETE MY ACCOUNT<input value={confirmation} onChange={e=>setConfirmation(e.target.value)} required/></label><button className="btn btn-ghost" disabled={confirmation!=='DELETE MY ACCOUNT'}>Permanently delete account</button></form></section>
}
