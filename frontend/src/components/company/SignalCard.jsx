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

  return (
    <article className="signal-card">
      <div className="signal-head">
        <div className="signal-icon"><Activity size={17} /></div>
        <div>
          <h3>{signal.signal}</h3>
          <p>{signal.category_label || signal.category}</p>
        </div>
        <Badge tone={signal.is_simulated ? 'warning' : 'positive'}>
          {signal.is_simulated ? 'Modelled' : 'Live'}
        </Badge>
      </div>
      <div className="signal-score">
        <span>{signal.display}</span>
        <strong>{score}/100</strong>
      </div>
      <div className="progress-track">
        <div className={`progress-fill fill-${tone}`} style={{ width: `${score}%` }} />
      </div>
      <p className="signal-copy">{signal.insight}</p>
      <footer className="signal-foot">
        <span>Weight {signal.weight_pct || `${Math.round((signal.weight || 0) * 100)}%`}</span>
        {signal.source_url && (
          <a href={signal.source_url} target="_blank" rel="noreferrer">
            Source <ExternalLink size={12} />
          </a>
        )}
      </footer>
    </article>
  )
}
