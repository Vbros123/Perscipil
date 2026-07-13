import { CheckCircle2 } from 'lucide-react'

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
    points: ['Saved reports', 'Peer comparison', 'Weekly monitoring'],
  },
  {
    name: 'Institution',
    price: 'Custom',
    detail: 'Teams and data partnerships',
    points: ['Team accounts', 'API access', 'Licensed data feeds'],
  },
]

export default function Pricing() {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Commercial model" title="Pricing">
        Simple packaging for the current product stage.
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
      <div className="notice notice-info">
        PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice.
      </div>
    </div>
  )
}
