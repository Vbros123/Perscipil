import { ArrowRight, Gauge } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from '../router'

import { resetPassword } from '../api/auth'
import ErrorNotice from '../components/common/ErrorNotice'
import { useAuth } from '../context/AuthContext'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const defaultToken = useMemo(() => params.get('token') || '', [params])
  const [form, setForm] = useState({ token: defaultToken, new_password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { showFlashMessage } = useAuth()

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await resetPassword(form)
      showFlashMessage('Password reset. Sign in with your new password.')
      navigate('/login', { replace: true })
    } catch (err) {
      setError(err.message || 'Unable to reset password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <Link to="/" className="brand auth-brand">
        <span className="brand-mark"><Gauge size={19} /></span>
        <span><strong>PrivateLens</strong><small>Secure reset</small></span>
      </Link>
      <section className="auth-card">
        <div className="eyebrow">Password reset</div>
        <h1>Set new password</h1>
        <ErrorNotice message={error} />
        <form onSubmit={submit} className="form-stack">
          <label>Reset token<input value={form.token} onChange={(event) => setForm({ ...form, token: event.target.value })} required /></label>
          <label>New password
            <input type="password" minLength={12} value={form.new_password} onChange={(event) => setForm({ ...form, new_password: event.target.value })} required />
            <small className="field-help">Use at least 12 characters with a mix of uppercase, lowercase, numbers, or symbols.</small>
          </label>
          <button className="btn btn-primary" disabled={loading}>{loading ? 'Resetting' : 'Reset password'} <ArrowRight size={16} /></button>
        </form>
      </section>
    </main>
  )
}
