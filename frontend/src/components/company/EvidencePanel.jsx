import { CheckCircle2, CircleX, DatabaseZap, Fingerprint } from 'lucide-react'

import Badge from '../common/Badge'
import { displayRating, isRated } from '../../lib/score'

const gateLabels = {
  coverage: '70% licensed coverage',
  entity_identity: 'Legal entity verified',
  provider_diversity: 'Two provider minimum',
  model_approval: 'Model validation approved',
}

export default function EvidencePanel({ result }) {
  const meta = result.meta || {}
  const gates = meta.gates || {}
  const entity = result.entity || {}
  const providers = meta.providers_used || []
  const hash = meta.input_snapshot_hash || ''
  const publicTrack = meta.scoring_track === 'public'
  const published = isRated(result)

  return (
    <section className="panel evidence-panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">{publicTrack ? 'Score provenance' : 'Evidence controls'}</div>
          <h2>{publicTrack ? 'Public-track rating' : 'Rating release gates'}</h2>
        </div>
        <Badge tone={published ? 'positive' : 'warning'}>
          {result.scoring_status === 'validation_hold' ? 'Shadow mode' : displayRating(result)}
        </Badge>
      </div>
      <div className="evidence-layout">
        <div className="gate-list">
          {Object.entries(gateLabels).map(([key, label]) => {
            const passed = Boolean(gates[key])
            const Icon = passed ? CheckCircle2 : CircleX
            return (
              <div key={key} className={passed ? 'gate-pass' : 'gate-fail'}>
                <Icon size={17} />
                <span>{label}</span>
                <strong>{publicTrack ? (passed ? 'Pass' : 'Not required') : (passed ? 'Pass' : 'Blocked')}</strong>
              </div>
            )
          })}
        </div>
        <dl className="evidence-details">
          <div><dt><Fingerprint size={15} /> Legal entity</dt><dd>{result.company?.canonicalName || entity.legal_name || result.company_name}</dd></div>
          <div><dt>Country / registration</dt><dd>{entity.country_code || 'US'} / {entity.registration_number || 'Not supplied'}</dd></div>
          <div><dt><DatabaseZap size={15} /> Providers</dt><dd>{providers.length ? providers.join(', ') : 'No licensed evidence accepted'}</dd></div>
          <div><dt>Evidence snapshot</dt><dd className="mono">{hash ? hash.slice(0, 16) : 'Not available'}</dd></div>
        </dl>
      </div>
    </section>
  )
}
