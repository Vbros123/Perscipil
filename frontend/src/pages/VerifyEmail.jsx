import { CheckCircle2, Gauge } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { verifyEmail } from '../api/auth'
import ErrorNotice from '../components/common/ErrorNotice'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const token = useMemo(() => params.get('token') || '', [params])
  const [error, setError] = useState('')
  const [verified, setVerified] = useState(false)
  const verificationRequest = useRef(null)

  useEffect(() => {
    let mounted = true
    async function run() {
      if (!token) {
        setError('Verification token is missing.')
        return
      }
      try {
        if (!verificationRequest.current) {
          verificationRequest.current = verifyEmail({ token })
        }
        await verificationRequest.current
        if (mounted) setVerified(true)
      } catch (err) {
        if (mounted) setError(err.message || 'Unable to verify email.')
      }
    }
    run()
    return () => { mounted = false }
  }, [token])

  return (
    <main className="auth-page">
      <Link to="/" className="brand auth-brand">
        <span className="brand-mark"><Gauge size={19} /></span>
        <span><strong>PrivateLens</strong><small>Email verification</small></span>
      </Link>
      <section className="auth-card">
        <div className="eyebrow">Account security</div>
        <h1>{verified ? 'Email verified' : 'Verifying email'}</h1>
        <ErrorNotice message={error} />
        {verified && <div className="notice notice-success"><CheckCircle2 size={17} /> Your email is verified.</div>}
        <Link className="btn btn-primary" to="/login">Continue to login</Link>
      </section>
    </main>
  )
}
