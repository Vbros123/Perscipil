import { useEffect, useState } from 'react'
import { apiRequest } from '../../api/client'
export default function WorkspaceLibrary({organization}) {
 const [saved,setSaved]=useState([]),[name,setName]=useState(''),[batch,setBatch]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false)
 const root=`/api/organizations/${organization.id}`
 async function load(){setSaved((await apiRequest(root+'/resources?kind=watchlist&limit=100')).items)}
 useEffect(()=>{let active=true;apiRequest(root+'/resources?kind=watchlist&limit=100').then(r=>{if(active)setSaved(r.items)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[root])
 async function act(fn){setBusy(true);setError('');try{await fn()}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function download(){const text=await apiRequest(root+'/batches/'+encodeURIComponent(batch)+'/export');const url=URL.createObjectURL(new Blob([text],{type:'text/csv'}));const link=document.createElement('a');link.href=url;link.download='workspace-screening.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
 return <section className="panel form-stack"><h2>Saved companies and batch exports</h2>{error&&<p role="alert">{error}</p>}<form onSubmit={e=>{e.preventDefault();act(async()=>{await apiRequest(root+'/watchlist',{method:'POST',body:JSON.stringify({legal_name:name})});setName('');await load()})}}><label>Company name<input required value={name} onChange={e=>setName(e.target.value)}/></label><button className="btn" disabled={busy}>Save company</button></form>{saved.map(r=><p key={r.id}>{r.payload.legal_name}<button className="btn" disabled={busy} onClick={()=>act(async()=>{await apiRequest(root+`/resources/${r.id}`,{method:'DELETE'});await load()})}>Remove</button></p>)}<label>Batch key from job progress<input value={batch} onChange={e=>setBatch(e.target.value)}/></label><button className="btn" disabled={busy||!batch} onClick={()=>act(download)}>Download batch CSV</button></section>
}
