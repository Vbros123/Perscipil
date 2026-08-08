import { ArrowRight, ScanSearch } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from '../router'

import ErrorNotice from '../components/common/ErrorNotice'
import { useAuth } from '../context/AuthContext'

export default function Signup() {
  const [form, setForm] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    company: '',
    role: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const signupInProgress = useRef(false)
  const { signup, isAuthenticated } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!isAuthenticated) return
    navigate(signupInProgress.current ? '/onboarding' : '/dashboard', { replace: true })
  }, [isAuthenticated, navigate])

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    signupInProgress.current = true
    try {
      await signup(form)
    } catch (err) {
      signupInProgress.current = false
      setError(err.message || 'Unable to create account.')
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
      <section className="auth-card wide">
        <div className="eyebrow">Create workspace</div>
        <h1>Start using PrivateLens</h1>
        <ErrorNotice message={error} />
        <form onSubmit={submit} className="form-stack">
          <div className="form-grid">
            <label>First name<input value={form.first_name} onChange={update('first_name')} /></label>
            <label>Last name<input value={form.last_name} onChange={update('last_name')} /></label>
          </div>
          <label>Email<input type="email" value={form.email} onChange={update('email')} required /></label>
          <label>Password
            <input type="password" minLength={12} value={form.password} onChange={update('password')} required />
            <small className="field-help">Use at least 12 characters with a mix of uppercase, lowercase, numbers, or symbols.</small>
          </label>
          <div className="form-grid">
            <label>Company<input value={form.company} onChange={update('company')} /></label>
            <label>Role<input value={form.role} onChange={update('role')} /></label>
          </div>
          <button className="btn btn-primary" disabled={loading}>{loading ? 'Creating' : 'Create account'} <ArrowRight size={16} /></button>
        </form>
        <p className="auth-switch">Already have an account? <Link to="/login">Log in</Link></p>
      </section>
    </main>
  )
}
