import Badge from '../common/Badge'

const STATUS = {
  live: { label: 'LIVE', tone: 'positive' },
  modelled: { label: 'MODELLED', tone: 'accent' },
  unavailable: { label: 'UNAVAILABLE', tone: 'warning' },
  not_applicable: { label: 'NOT APPLICABLE', tone: 'neutral' },
  public: { label: 'PUBLIC', tone: 'neutral' },
}

const QUALITY = {
  high: 'HIGH QUALITY',
  medium: 'MEDIUM QUALITY',
  low: 'LOW QUALITY',
  modelled: 'MODELLED',
  unavailable: 'NONE',
  not_applicable: 'N/A',
  none: 'NONE',
}

export default function DataSources({ result }) {
  const sources = result?.dataSources || result?.report?.data_sources || []
  const attempts = result?.sourceAttempts || {}
  if (!sources.length) return null

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">Provenance</div>
          <h2>Data sources</h2>
        </div>
        {Number.isFinite(attempts.attempted) && (
          <Badge tone="neutral">{attempts.successful || 0}/{attempts.attempted} sources returned</Badge>
        )}
      </div>
      <div className="source-list">
        {sources.map((item) => {
          const status = STATUS[item.status] || { label: String(item.status || 'unknown').toUpperCase(), tone: 'neutral' }
          const quality = QUALITY[item.evidenceQuality] || QUALITY.none
          return (
            <div key={item.key || item.source} className="source-row">
              <strong>{item.source}</strong>
              <Badge tone={status.tone}>{status.label}</Badge>
              <span>{quality}</span>
              {item.errorCode && <span className="source-error">{item.errorCode}</span>}
            </div>
          )
        })}
      </div>
    </section>
  )
}
