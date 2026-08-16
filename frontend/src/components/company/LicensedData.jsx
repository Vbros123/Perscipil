import Badge from '../common/Badge'

export default function LicensedData({ result }) {
  const panel = result?.licensedData
  if (!panel || panel.connected) return null

  return (
    <section className="panel licensed-panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">Enterprise data</div>
          <h2>{panel.title || 'Financial / Credit Data'}</h2>
        </div>
        <Badge tone="neutral">Not connected</Badge>
      </div>
      <p>{panel.message}</p>
      <ul className="clean-list">
        <li>Available in {panel.availableIn || 'Enterprise/paid data mode'}</li>
        <li>Provider integration architecture ready</li>
        <li>These signals are not claimed and are not scored</li>
      </ul>
    </section>
  )
}
