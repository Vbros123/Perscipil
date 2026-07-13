import { Clock3, Database, ShieldCheck } from 'lucide-react'

import MetricCard from '../common/MetricCard'
import ScoreDial from '../common/ScoreDial'

const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`

export default function CompanySummary({ result }) {
  const meta = result.meta || {}

  return (
    <section className="report-hero">
      <div className="report-score-panel">
        <ScoreDial score={result.private_score} rating={result.rating} color={result.color} size={188} />
        <div>
          <div className="eyebrow">PrivateScore</div>
          <h2>{result.company_name}</h2>
          <p>{result.summary}</p>
          <div className="report-meta">
            <span>{meta.real_signals || 0} live signals</span>
            <span>{meta.simulated_signals || 0} modelled signals</span>
            <span>{percent(meta.confidence)} confidence</span>
          </div>
        </div>
      </div>
      <div className="metric-grid compact">
        <MetricCard icon={ShieldCheck} label="Research risk" value={result.report?.risk_level || result.rating} detail="Screening profile" tone="positive" />
        <MetricCard icon={Database} label="Signals" value={meta.total_signals || 14} detail="Weighted model inputs" tone="accent" />
        <MetricCard icon={Clock3} label="Latency" value={`${result.elapsed_seconds || 0}s`} detail={meta.cached ? 'Cached response' : 'Fresh run'} tone="neutral" />
      </div>
    </section>
  )
}
