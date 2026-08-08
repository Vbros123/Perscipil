import { Clock3, Database, ShieldCheck } from 'lucide-react'

import MetricCard from '../common/MetricCard'
import ScoreBand from '../common/ScoreBand'
import { ratingTone } from '../../lib/score'

const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`

export default function CompanySummary({ result }) {
  const meta = result.meta || {}
  const rated = result.scoring_status === 'rated'
  const tone = ratingTone(result)

  return (
    <section className="report-hero">
      <div className="report-score-panel">
        <div className="report-score-figure">
          <div className={`report-score-value tone-${tone}`}>
            {rated ? result.private_score : '—'}
            {rated && <small> / 1000</small>}
          </div>
          <div className={`report-score-rating tone-${tone}`}>
            {rated ? result.rating : 'Unrated'}
          </div>
          <ScoreBand score={result.private_score} rated={rated} />
        </div>
        <div>
          <div className="eyebrow">{rated ? 'PrivateScore' : 'Verified coverage check'}</div>
          <h2>{result.company_name}</h2>
          <p>{result.summary}</p>
          <div className="report-meta">
            <span>{meta.scored_signals || 0} of 5 verified inputs</span>
            <span>{meta.provider_diversity || 0} licensed providers</span>
            <span>{percent(meta.evidence_coverage)} model coverage</span>
            <span>{percent(meta.confidence)} evidence confidence</span>
          </div>
        </div>
      </div>
      <div className="metric-grid compact">
        <MetricCard
          icon={ShieldCheck}
          label="Risk rating"
          value={result.report?.risk_level || result.rating}
          detail={rated ? 'Screening profile' : 'Coverage threshold not met'}
        />
        <MetricCard
          icon={Database}
          label="Evidence"
          value={percent(meta.evidence_coverage)}
          detail={`${meta.scored_signals || 0} verified inputs`}
        />
        <MetricCard
          icon={Clock3}
          label="Run time"
          value={`${result.elapsed_seconds || 0}s`}
          detail={meta.cached ? 'Cached response' : 'Fresh run'}
        />
      </div>
    </section>
  )
}
