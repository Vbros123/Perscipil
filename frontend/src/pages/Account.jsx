import { useState } from 'react'

import ErrorNotice from '../components/common/ErrorNotice'
import PageHeader from '../components/common/PageHeader'
import { useAuth } from '../context/AuthContext'

export default function Account() {
  const { user, updateUser } = useAuth()
  const [form, setForm] = useState({
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    company: user?.company || '',
    role: user?.role || '',
  })
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    try {
      await updateUser(form)
      setMessage('Account updated.')
    } catch (err) {
      setError(err.message || 'Unable to update account.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-stack narrow">
      <PageHeader eyebrow="Profile" title="Account">
        Keep your workspace identity current.
      </PageHeader>
      <ErrorNotice message={error} />
      {message && <div className="notice notice-success">{message}</div>}
      <form className="panel form-stack" onSubmit={submit}>
        <label>Email<input value={user?.email || ''} disabled /></label>
        <div className="form-grid">
          <label>First name<input value={form.first_name} onChange={update('first_name')} /></label>
          <label>Last name<input value={form.last_name} onChange={update('last_name')} /></label>
        </div>
        <div className="form-grid">
          <label>Company<input value={form.company} onChange={update('company')} /></label>
          <label>Role<input value={form.role} onChange={update('role')} /></label>
        </div>
        <button className="btn btn-primary" disabled={loading}>{loading ? 'Saving' : 'Save profile'}</button>
      </form>
    </div>
  )
}
