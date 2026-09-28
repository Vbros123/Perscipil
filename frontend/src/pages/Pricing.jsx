import { CheckCircle2 } from 'lucide-react'

import { CAPABILITIES } from '../lib/brand'
import PageHeader from '../components/common/PageHeader'

const plans = [
  {
    name: 'Starter',
    price: '$0',
    detail: 'Founder demo workspace',
    points: ['Company scoring', 'Search history', 'Basic watchlist'],
  },
  {
    name: 'Analyst',
    price: '$49',
    detail: 'Individual research workflow',
    points: ['Saved reports', 'Peer comparison', 'Monitoring pilot (scheduler required)'],
  },
  {
    name: 'Institution',
    price: 'Custom',
    detail: 'Teams and data partnerships',
    points: ['Team accounts (planned)', 'Public-evidence API (pilot)', 'Licensed feeds (contract required)'],
  },
]

export default function Pricing() {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Commercial model" title="Pricing">
        Proposed packaging; paid plans and team workspaces are not generally available.
      </PageHeader>
      <section className="pricing-grid">
        {plans.map((plan) => (
          <article className="pricing-card" key={plan.name}>
            <h2>{plan.name}</h2>
            <div className="price">{plan.price}</div>
            <p>{plan.detail}</p>
            <ul className="clean-list">
              {plan.points.map((point) => <li key={point}><CheckCircle2 size={15} /> {point}</li>)}
            </ul>
          </article>
        ))}
      </section>
      <section className="panel"><h2>Capability status</h2>{CAPABILITIES.map(c => <p key={c.name}><strong>{c.name}: {c.status}</strong> — {c.note}</p>)}</section>
      <div className="notice notice-info">
        Perspicil is a research tool and does not provide credit, investment, legal, or lending advice.
      </div>
    </div>
  )
}
