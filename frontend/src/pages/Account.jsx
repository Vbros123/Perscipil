import { useState } from 'react'
import MfaControls from '../components/settings/MfaControls'
import DataControls from '../components/settings/DataControls'

import { changePassword } from '../api/auth'
import ErrorNotice from '../components/common/ErrorNotice'
import PageHeader from '../components/common/PageHeader'
import { useAuth } from '../context/AuthContext'

export default function Account() {
  const { user, updateUser, logout, showFlashMessage } = useAuth()
  const [form, setForm] = useState({
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    company: user?.company || '',
    role: user?.role || '',
  })
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [passwordForm, setPasswordForm] = useState({ current_password: '', new_password: '' })
  const [passwordLoading, setPasswordLoading] = useState(false)
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

  const submitPassword = async (event) => {
    event.preventDefault()
    setError('')
    setMessage('')
    setPasswordLoading(true)
    try {
      await changePassword(passwordForm)
      setPasswordForm({ current_password: '', new_password: '' })
      showFlashMessage('Password changed. Sign in with your new password.')
      await logout(false)
    } catch (err) {
      setError(err.message || 'Unable to change password.')
    } finally {
      setPasswordLoading(false)
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
      <form className="panel form-stack" onSubmit={submitPassword}>
        <div>
          <div className="eyebrow">Security</div>
          <h2>Change password</h2>
        </div>
        <label>Current password
          <input
            type="password"
            value={passwordForm.current_password}
            onChange={(event) => setPasswordForm({ ...passwordForm, current_password: event.target.value })}
            required
          />
        </label>
        <label>New password
          <input
            type="password"
            minLength={12}
            value={passwordForm.new_password}
            onChange={(event) => setPasswordForm({ ...passwordForm, new_password: event.target.value })}
            required
          />
          <small className="field-help">Use at least 12 characters with a mix of uppercase, lowercase, numbers, or symbols.</small>
        </label>
        <button className="btn btn-primary" disabled={passwordLoading}>{passwordLoading ? 'Updating' : 'Change password'}</button>
      </form>
      <MfaControls />
      <DataControls />
    </div>
  )
}
