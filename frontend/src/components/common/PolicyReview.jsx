import { useEffect,useState } from 'react'
import { apiRequest } from '../../api/client'
export default function PolicyReview(){
 const [policy,setPolicy]=useState(null),[error,setError]=useState(''),[checked,setChecked]=useState(false),[busy,setBusy]=useState(false)
 async function load(){setError('');try{setPolicy(await apiRequest('/api/policies/status'))}catch{setError('Policy status could not be checked. Retry when connected.')}}
 useEffect(()=>{load()},[])
 async function accept(){setBusy(true);try{await apiRequest('/api/policies/accept',{method:'POST',body:JSON.stringify({terms_version:policy.terms_version,privacy_version:policy.privacy_version})});setChecked(false);await load()}catch(e){setError(e.message)}finally{setBusy(false)}}
 if(error)return <aside className="notice" role="status">{error} <button onClick={load}>Retry</button></aside>
 if(!policy?.published||policy.current)return null
 return <section className="panel form-stack" aria-labelledby="policy-review-title"><h2 id="policy-review-title">Review updated policies</h2><p>{policy.required?'Acceptance is required before further research activity. Account export, deletion, and sign-out remain available.':'Please review the current policies.'}</p><details><summary>Terms · {policy.terms_version}</summary><pre style={{whiteSpace:'pre-wrap'}}>{policy.terms_text}</pre></details><details><summary>Privacy · {policy.privacy_version}</summary><pre style={{whiteSpace:'pre-wrap'}}>{policy.privacy_text}</pre></details><label><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/> I have reviewed these versions and accept the Terms and acknowledge the Privacy Policy.</label><button className="btn" disabled={!checked||busy} onClick={accept}>Record acceptance</button></section>
}
