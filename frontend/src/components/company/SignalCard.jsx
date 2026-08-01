import { Activity, ExternalLink } from 'lucide-react'

import Badge from '../common/Badge'

const toneForScore = (score) => {
  if (score >= 70) return 'positive'
  if (score >= 45) return 'accent'
  if (score >= 30) return 'warning'
  return 'danger'
}

export default function SignalCard({ signal }) {
  const score = Math.round(Number(signal?.raw_score || 0))
  const tone = toneForScore(score)
  const status = signal.is_simulated ? 'Unavailable' : (signal.used_in_score ? 'Verified input' : 'Context only')
  const statusTone = signal.is_simulated ? 'warning' : (signal.used_in_score ? 'positive' : 'neutral')
  const showScore = Boolean(signal.used_in_score)

  return (
    <article className="signal-card">
      <div className="signal-head">
        <div className="signal-icon"><Activity size={17} /></div>
        <div>
          <h3>{signal.signal}</h3>
          <p>{signal.provider || signal.category_label || signal.category}</p>
        </div>
        <Badge tone={statusTone}>{status}</Badge>
      </div>
      <div className="signal-score">
        <span>{signal.display}</span>
        <strong>{showScore ? `${score}/100` : status}</strong>
      </div>
      <div className="progress-track" aria-hidden={!showScore}>
        <div className={`progress-fill fill-${tone}`} style={{ width: showScore ? `${score}%` : '0%' }} />
      </div>
      <p className="signal-copy">{signal.insight}</p>
      {showScore && (
        <div className="signal-provenance">
          <span>Observed {signal.freshness_days ?? '-'}d ago</span>
          <span>Entity match {Math.round(Number(signal.entity_match_confidence || 0) * 100)}%</span>
          <span>Transform {signal.transform_version || '-'}</span>
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
