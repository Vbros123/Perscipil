import Badge from '../common/Badge'

const STATUS = {
  live: { label: 'LIVE', tone: 'positive' },
  modelled: { label: 'MODELLED', tone: 'accent' },
  unavailable: { label: 'UNAVAILABLE', tone: 'warning' },
  not_applicable: { label: 'NOT APPLICABLE', tone: 'neutral' },
  not_connected: { label: 'NOT CONNECTED', tone: 'neutral' },
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

const GROUP_ORDER = [
  'IDENTITY & REGISTRY',
  'FINANCIAL & REGULATORY',
  'GOVERNMENT ACTIVITY',
  'INDUSTRY CONTEXT',
  'PUBLIC SIGNALS',
  'OPERATING SIGNALS',
  'LICENSED DATA',
]

function matchLabel(item) {
  if (item.entityMatch) return item.entityMatch
  if (item.status === 'not_applicable' && item.key === 'sec') return 'Private company'
  if (item.status === 'live' && item.key === 'census') return 'Industry-level'
  if (item.optional && item.status === 'unavailable') return 'Optional source'
  if (item.status === 'live') return 'Entity matched'
  return null
}

export default function DataSources({ result }) {
  const sources = result?.dataSources || result?.report?.data_sources || []
  const attempts = result?.sourceAttempts || {}
  if (!sources.length) return null

  const groups = new Map()
  sources.forEach((item) => {
    const label = item.groupLabel || 'PUBLIC SIGNALS'
    if (!groups.has(label)) groups.set(label, [])
    groups.get(label).push(item)
  })
  const ordered = GROUP_ORDER.filter((label) => groups.has(label)).concat(
    [...groups.keys()].filter((label) => !GROUP_ORDER.includes(label)),
  )

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">Provenance</div>
          <h2>Data sources</h2>
        </div>
        {Number.isFinite(attempts.attempted) && (
          <Badge tone="neutral">{attempts.successful || 0}/{attempts.attempted} required sources returned</Badge>
        )}
      </div>
      <div className="source-groups">
        {ordered.map((label) => (
          <div key={label} className="source-group">
            <h3>{label}</h3>
            <div className="source-list">
              {groups.get(label).map((item) => {
                const status = STATUS[item.status] || { label: String(item.status || 'unknown').replaceAll('_', ' ').toUpperCase(), tone: 'neutral' }
                const quality = QUALITY[item.evidenceQuality] || QUALITY.none
                const match = matchLabel(item)
                return (
                  <div key={item.key || item.source} className="source-row">
                    <strong>{item.source}</strong>
                    {/^https?:\/\//.test(item.sourceUrl || "") && <a href={item.sourceUrl} target="_blank" rel="noreferrer">Source record</a>}
                    <Badge tone={status.tone}>{status.label}</Badge>
                    <span>{quality}</span>
                    {match && <span className="source-match">{match}</span>}
                    {item.errorCode && !item.optional && <span className="source-error">{item.errorCode}</span>}
                    {item.optional && item.status === 'unavailable' && <span className="source-match">Optional</span>}
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
      <p className="muted">Wikipedia text is attributed to Wikipedia contributors; consult the linked article and its history. <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer">CC BY-SA 4.0</a> applies where specified by the source. Data may be excerpted or transformed.</p>
    </section>
  )
}
