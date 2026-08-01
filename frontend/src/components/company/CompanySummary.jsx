import { Clock3, Database, ShieldCheck } from 'lucide-react'

import MetricCard from '../common/MetricCard'
import ScoreDial from '../common/ScoreDial'

const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`

export default function CompanySummary({ result }) {
  const meta = result.meta || {}
  const isPreliminary = result.scoring_status !== 'rated'

  return (
    <section className="report-hero">
      <div className="report-score-panel">
        <ScoreDial score={result.private_score} rating={result.rating} color={result.color} size={188} />
        <div>
          <div className="eyebrow">{isPreliminary ? 'Verified coverage check' : 'PrivateScore'}</div>
          <h2>{result.company_name}</h2>
          <p>{result.summary}</p>
          <div className="report-meta">
            <span>{meta.scored_signals || 0} verified inputs</span>
            <span>{meta.provider_diversity || 0} licensed providers</span>
            <span>{percent(meta.evidence_coverage)} model coverage</span>
            <span>{percent(meta.confidence)} evidence confidence</span>
          </div>
        </div>
      </div>
      <div className="metric-grid compact">
        <MetricCard icon={ShieldCheck} label="Risk rating" value={result.report?.risk_level || result.rating} detail={isPreliminary ? 'Coverage threshold not met' : 'Screening profile'} tone={isPreliminary ? 'warning' : 'positive'} />
        <MetricCard icon={Database} label="Evidence" value={`${Math.round(Number(meta.evidence_coverage || 0) * 100)}%`} detail={`${meta.scored_signals || 0} verified inputs`} tone="accent" />
        <MetricCard icon={Clock3} label="Latency" value={`${result.elapsed_seconds || 0}s`} detail={meta.cached ? 'Cached response' : 'Fresh run'} tone="neutral" />
      </div>
    </section>
  )
}
