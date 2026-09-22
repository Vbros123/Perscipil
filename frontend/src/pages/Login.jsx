import { ArrowRight, ScanSearch } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from '../router'

import ErrorNotice from '../components/common/ErrorNotice'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const [form, setForm] = useState({ email: '', password: '', mfa_code: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login, flashMessage } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(form)
      navigate(location.state?.from?.pathname || '/dashboard', { replace: true })
    } catch (err) {
      setError(err.message || 'Unable to log in.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <Link to="/" className="brand auth-brand">
        <span className="brand-mark"><ScanSearch size={17} /></span>
        <span><strong>PrivateLens</strong><small>Company intelligence</small></span>
      </Link>
      <section className="auth-card">
        <div className="eyebrow">Workspace access</div>
        <h1>Log in</h1>
        {flashMessage && <div className="notice notice-success">{flashMessage}</div>}
        <ErrorNotice message={error} />
        <form onSubmit={submit} className="form-stack">
          <label>Email<input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /></label>
          <label>Password<input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>
          <label>Authenticator or recovery code (if enabled)<input autoComplete="one-time-code" maxLength={80} value={form.mfa_code} onChange={event=>setForm({...form,mfa_code:event.target.value})}/></label>
          <button className="btn btn-primary" disabled={loading}>{loading ? 'Checking' : 'Continue'} <ArrowRight size={16} /></button>
        </form>
        <p className="auth-switch"><Link to="/forgot-password">Forgot password?</Link></p>
        <p className="auth-switch">No account yet? <Link to="/signup">Create one</Link></p>
      </section>
    </main>
  )
}
