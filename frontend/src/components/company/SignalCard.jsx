import { ExternalLink } from 'lucide-react'

import Badge from '../common/Badge'

const toneForScore = (score) => {
  if (score >= 70) return 'positive'
  if (score >= 45) return 'accent'
  if (score >= 30) return 'warning'
  return 'danger'
}

const STATUS_BADGES = {
  live: { label: 'LIVE', tone: 'positive' },
  verified: { label: 'LIVE', tone: 'positive' },
  modelled: { label: 'MODELLED', tone: 'accent' },
  unavailable: { label: 'UNAVAILABLE', tone: 'warning' },
  not_applicable: { label: 'NOT APPLICABLE', tone: 'neutral' },
}

const QUALITY_BADGES = {
  high: { label: 'HIGH EVIDENCE', tone: 'positive' },
  medium: { label: 'MEDIUM EVIDENCE', tone: 'accent' },
  low: { label: 'LOW EVIDENCE', tone: 'warning' },
  modelled: { label: 'MODELLED', tone: 'accent' },
  unavailable: { label: 'MISSING', tone: 'warning' },
  not_applicable: { label: 'NOT APPLICABLE', tone: 'neutral' },
}

export default function SignalCard({ signal }) {
  const rawScore = Number(signal?.raw_score)
  const hasScore = signal?.raw_score !== null && signal?.raw_score !== undefined && Number.isFinite(rawScore)
  const score = hasScore ? Math.round(rawScore) : null
  const tone = toneForScore(score ?? 0)
  const confidence = Number(signal?.entity_match_confidence)
  const statusKey = signal.availability_status || signal.status || (signal.is_simulated ? 'unavailable' : 'live')
  const badge = STATUS_BADGES[statusKey] || { label: String(statusKey).replaceAll('_', ' ').toUpperCase(), tone: 'neutral' }
  const qualityKey = signal.evidenceQuality || signal.evidence_quality || (statusKey === 'modelled' ? 'modelled' : statusKey)
  const qualityBadge = QUALITY_BADGES[qualityKey]
  const showScore = Boolean(signal.used_in_score) && hasScore

  return (
    <article className="signal-card">
      <div className="signal-head">
        <div>
          <h3>{signal.signal}</h3>
          <p>{signal.provider || signal.category_label || signal.category}</p>
        </div>
        <div className="signal-badges">
          <Badge tone={badge.tone}>{badge.label}</Badge>
          {qualityBadge && qualityKey !== statusKey && qualityKey !== 'unavailable' && qualityKey !== 'not_applicable' && (
            <Badge tone={qualityBadge.tone}>{qualityBadge.label}</Badge>
          )}
        </div>
      </div>
      <div className="signal-score">
        <span>{signal.display}</span>
        <strong>{showScore ? `${score}/100` : ''}</strong>
      </div>
      <div className="progress-track" aria-hidden={!showScore}>
        <div className={`progress-fill fill-${tone}`} style={{ width: showScore ? `${score}%` : '0%' }} />
      </div>
      <p className="signal-copy">{signal.insight}</p>
      {showScore && (
        <div className="signal-provenance">
          <span>Observed {signal.freshness_days ?? signal.retrieved_at ?? '—'}</span>
          <span>Entity match {Number.isFinite(confidence) ? `${Math.round(confidence * 100)}%` : 'not reported'}</span>
          <span>Transform {signal.transform_version || signal.track || '—'}</span>
        </div>
      )}
      <footer className="signal-foot">
        <span>
          {showScore
            ? `Weight ${signal.weight_pct || `${Math.round((signal.weight || 0) * 100)}%`}`
            : (signal.weight ? `Excluded · model weight ${signal.weight_pct}` : 'Excluded from model')}
        </span>
        {signal.source_url && (
          <a href={signal.source_url} target="_blank" rel="noreferrer">
            Source <ExternalLink size={12} />
          </a>
        )}
      </footer>
    </article>
  )
}
