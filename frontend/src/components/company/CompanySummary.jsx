import { Activity, Clock3, Database, Gauge, Shield } from 'lucide-react'

import MetricCard from '../common/MetricCard'
import ScoreBand from '../common/ScoreBand'
import { displayRating, displayScore, isRated, ratingTone } from '../../lib/score'

const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`

function coverageFrom(result) {
  const nested = result.dataCoverage || result.meta?.data_coverage || {}
  return {
    live: nested.liveSignals ?? nested.live ?? 0,
    modelled: nested.modelledSignals ?? nested.modelled ?? 0,
    unavailable: nested.unavailableSignals ?? nested.unavailable ?? 0,
    notApplicable: nested.notApplicableSignals ?? nested.notApplicable ?? 0,
    total: nested.totalSignals ?? result.meta?.total_signals ?? 0,
    percent: nested.coveragePercent,
  }
}

function entityLabel(type) {
  const labels = {
    company: 'Company',
    parent_company: 'Parent company',
    subsidiary: 'Subsidiary',
    brand: 'Brand',
    family: 'Family / historical entity',
    person: 'Person',
    organization: 'Organization',
    nonprofit: 'Nonprofit',
    government: 'Government',
    unknown: 'Unknown',
  }
  return labels[type] || type || 'Unknown'
}

function formatStamp(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString()
}

function qualityLabel(value) {
  const labels = {
    high: 'High',
    medium: 'Medium',
    low: 'Low',
    modelled: 'Modelled',
    unavailable: 'Unavailable',
  }
  return labels[value] || 'Low'
}

export default function CompanySummary({ result }) {
  const meta = result.meta || {}
  const nested = result.score || {}
  const rated = isRated(result)
  const tone = ratingTone(result)
  const scoreValue = displayScore(result, '—')
  const confidence = nested.confidence ?? meta.confidence
  const coverage = nested.coverage ?? meta.evidence_coverage
  const quality = nested.evidenceQuality || meta.evidence_quality || 'unavailable'
  const limited = result.scoring_status === 'limited'
  const counts = coverageFrom(result)
  const coverageDisplay = Number.isFinite(Number(counts.percent))
    ? `${Math.round(counts.percent)}%`
    : percent(coverage)

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
          <div className="eyebrow">{rated ? (limited ? 'PrivateScore · limited evidence' : 'PrivateScore') : 'Coverage check'}</div>
          <h2>{result.company?.canonicalName || result.canonical_name || result.company_name}</h2>
          <p className="report-entity-type">{entityLabel(result.company?.entityType || result.entity?.entity_type)}</p>
          <p>{result.summary}</p>
          {result.resolution?.limited_identification && (
            <p className="report-note">Limited company identification. Remaining public signals were still scored.</p>
          )}
          <div className="report-meta">
            <span>Score ≠ confidence</span>
            <span>{qualityLabel(quality)} evidence quality</span>
            <span>{counts.live} live · {counts.modelled} modelled · {counts.unavailable} unavailable</span>
            <span>Model {result.report?.model_version || result.meta?.model_version || result.metadata?.modelVersion || 'public-v2'}</span>
            <span>Updated {formatStamp(result.report?.last_updated || result.metadata?.generatedAt || result.meta?.computed_at)}</span>
          </div>
          <p className="report-disclaimer">{result.report?.disclaimer || result.meta?.legal_disclaimer}</p>
        </div>
      </div>
      <div className="metric-grid compact evidence-metrics">
        <MetricCard
          icon={Gauge}
          label="Confidence"
          value={percent(confidence)}
          detail="How much reliable evidence we have — separate from the score"
        />
        <MetricCard
          icon={Database}
          label="Data coverage"
          value={coverageDisplay}
          detail={`${counts.live} live, ${counts.modelled} modelled, ${counts.unavailable} unavailable`}
        />
        <MetricCard
          icon={Shield}
          label="Evidence quality"
          value={qualityLabel(quality)}
          detail={limited ? 'Thin public sources only' : 'Quality of the inputs that were scored'}
        />
        <MetricCard
          icon={Activity}
          label="Live signals"
          value={String(counts.live)}
          detail={`${counts.modelled} modelled · ${counts.unavailable} missing`}
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
