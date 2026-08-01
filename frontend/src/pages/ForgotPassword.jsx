import { ArrowRight, Gauge } from 'lucide-react'
import { useState } from 'react'
import { Link } from '../router'

import { requestPasswordReset } from '../api/auth'
import ErrorNotice from '../components/common/ErrorNotice'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const result = await requestPasswordReset({ email })
      setMessage(result.message)
    } catch (err) {
      setError(err.message || 'Unable to issue reset instructions.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <Link to="/" className="brand auth-brand">
        <span className="brand-mark"><Gauge size={19} /></span>
        <span><strong>PrivateLens</strong><small>Account recovery</small></span>
      </Link>
      <section className="auth-card">
        <div className="eyebrow">Password reset</div>
        <h1>Recover access</h1>
        <ErrorNotice message={error} />
        {message && <div className="notice notice-success">{message}</div>}
        <form onSubmit={submit} className="form-stack">
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <button className="btn btn-primary" disabled={loading}>{loading ? 'Issuing' : 'Send reset'} <ArrowRight size={16} /></button>
        </form>
        <p className="auth-switch"><Link to="/login">Back to login</Link></p>
      </section>
    </main>
  )
}
