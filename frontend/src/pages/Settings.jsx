import { useEffect, useState } from 'react'

import { getSettings, updateSettings } from '../api/settings'
import ErrorNotice from '../components/common/ErrorNotice'
import PageHeader from '../components/common/PageHeader'
import SettingsForm from '../components/settings/SettingsForm'

export default function Settings() {
  const [values, setValues] = useState({
    default_view: 'dashboard',
    risk_threshold: 550,
    email_alerts: true,
    weekly_digest: true,
    simulated_data_labels: true,
  })
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        setValues(await getSettings())
      } catch (err) {
        setError(err.message || 'Unable to load settings.')
      }
    }
    load()
  }, [])

  const submit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')
    try {
      setValues(await updateSettings(values))
      setMessage('Settings saved.')
    } catch (err) {
      setError(err.message || 'Unable to save settings.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-stack narrow">
      <PageHeader eyebrow="Workspace" title="Settings">
        Configure the operating defaults for your PrivateLens research desk.
      </PageHeader>
      <ErrorNotice message={error} />
      {message && <div className="notice notice-success">{message}</div>}
      <SettingsForm values={values} setValues={setValues} onSubmit={submit} loading={loading} />
    </div>
  )
}
