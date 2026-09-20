export default function SettingsForm({ values, setValues, onSubmit, loading }) {
  return (
    <form className="panel form-stack" onSubmit={onSubmit}>
      <label>Default view
        <select value={values.default_view || 'dashboard'} onChange={(event) => setValues({ ...values, default_view: event.target.value })}>
          <option value="dashboard">Dashboard</option>
          <option value="watchlist">Watchlist</option>
          <option value="history">History</option>
        </select>
      </label>
      <label>Risk threshold
        <input
          type="number"
          min="0"
          max="1000"
          value={values.risk_threshold ?? 550}
          onChange={(event) => setValues({ ...values, risk_threshold: Number(event.target.value) })}
        />
      </label>
      <label className="switch-row">
        <span>Email alerts preference (delivery not active)</span>
        <input type="checkbox" checked={Boolean(values.email_alerts)} onChange={(event) => setValues({ ...values, email_alerts: event.target.checked })} />
      </label>
      <label className="switch-row">
        <span>Weekly digest preference (delivery not active)</span>
        <input type="checkbox" checked={Boolean(values.weekly_digest)} onChange={(event) => setValues({ ...values, weekly_digest: event.target.checked })} />
      </label>
      <label className="switch-row">
        <span>Show unavailable-source labels</span>
        <input type="checkbox" checked={Boolean(values.simulated_data_labels)} onChange={(event) => setValues({ ...values, simulated_data_labels: event.target.checked })} />
      </label>
      <button className="btn btn-primary" disabled={loading}>{loading ? 'Saving' : 'Save settings'}</button>
    </form>
  )
}
