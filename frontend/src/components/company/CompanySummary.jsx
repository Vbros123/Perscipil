import { Clock3, Database, Gauge } from 'lucide-react'

import MetricCard from '../common/MetricCard'
import ScoreBand from '../common/ScoreBand'
import { displayRating, displayScore, isRated, ratingTone } from '../../lib/score'

const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`

export default function CompanySummary({ result }) {
  const meta = result.meta || {}
  const nested = result.score || {}
  const rated = isRated(result)
  const tone = ratingTone(result)
  const scoreValue = displayScore(result, '—')
  const confidence = nested.confidence ?? meta.confidence
  const coverage = nested.coverage ?? meta.evidence_coverage
  const limited = result.scoring_status === 'limited'

  return (
    <section className="report-hero">
      <div className="report-score-panel">
        <div className="report-score-figure">
          <div className={`report-score-value tone-${tone}`}>
            {scoreValue}
            {rated && <small> / 1000</small>}
          </div>
          <div className={`report-score-rating tone-${tone}`}>
            {displayRating(result)}
          </div>
          <ScoreBand score={Number(nested.value ?? result.private_score)} rated={rated} />
        </div>
        <div>
          <div className="eyebrow">{rated ? (limited ? 'PrivateScore · limited coverage' : 'PrivateScore') : 'Coverage check'}</div>
          <h2>{result.company?.canonicalName || result.canonical_name || result.company_name}</h2>
          <p>{result.summary}</p>
          {result.resolution?.limited_identification && (
            <p className="report-note">Limited company identification. Remaining public signals were still scored.</p>
          )}
          <div className="report-meta">
            <span>{meta.scored_signals || 0} usable inputs</span>
            <span>{percent(coverage)} data coverage</span>
            <span>{percent(confidence)} confidence</span>
            {meta.scoring_track === 'public' && <span>Public track</span>}
          </div>
        </div>
      </div>
      <div className="metric-grid compact">
        <MetricCard
          icon={Gauge}
          label="Confidence"
          value={percent(confidence)}
          detail={limited ? 'Fewer sources than a full run' : 'Separate from the score'}
        />
        <MetricCard
          icon={Database}
          label="Data coverage"
          value={percent(coverage)}
          detail={`${meta.scored_signals || 0} live or modelled inputs`}
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
