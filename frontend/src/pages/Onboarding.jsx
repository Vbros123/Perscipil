import { BRAND } from '../lib/brand'
import BrandMark from '../components/common/BrandMark'
import { ArrowRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from '../router'

import { getSettings, updateSettings } from '../api/settings'
import ErrorNotice from '../components/common/ErrorNotice'
import { useAuth } from '../context/AuthContext'

export default function Onboarding() {
  const { user, updateUser } = useAuth()
  const [form, setForm] = useState({
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    company: user?.company || '',
    role: user?.role || '',
    risk_threshold: 550,
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    let mounted = true
    getSettings()
      .then((settings) => {
        if (mounted) {
          setForm((current) => ({ ...current, risk_threshold: settings.risk_threshold }))
        }
      })
      .catch((err) => {
        if (mounted) setError(err.message || 'Unable to load workspace settings.')
      })
    return () => { mounted = false }
  }, [])

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await updateUser({
        first_name: form.first_name,
        last_name: form.last_name,
        company: form.company,
        role: form.role,
      })
      await updateSettings({ risk_threshold: Number(form.risk_threshold) })
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || 'Unable to save onboarding.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <Link to="/dashboard" className="brand auth-brand">
        <BrandMark />
        <span><strong>{BRAND.name}</strong><small>Workspace setup</small></span>
      </Link>
      <section className="auth-card wide">
        <div className="eyebrow">Onboarding</div>
        <h1>Set up your research desk</h1>
        <ErrorNotice message={error} />
        <form className="form-stack" onSubmit={submit}>
          <div className="form-grid">
            <label>First name<input value={form.first_name} onChange={update('first_name')} /></label>
            <label>Last name<input value={form.last_name} onChange={update('last_name')} /></label>
          </div>
          <div className="form-grid">
            <label>Company<input value={form.company} onChange={update('company')} /></label>
            <label>Role<input value={form.role} onChange={update('role')} /></label>
          </div>
          <label>Risk threshold
            <input type="number" min="0" max="1000" value={form.risk_threshold} onChange={update('risk_threshold')} />
          </label>
          <button className="btn btn-primary" disabled={loading}>{loading ? 'Saving' : 'Enter dashboard'} <ArrowRight size={16} /></button>
        </form>
      </section>
    </main>
  )
}
