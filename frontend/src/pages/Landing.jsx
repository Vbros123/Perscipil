import { ArrowRight, BarChart3, CheckCircle2, Database, Gauge, LockKeyhole, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

import ScoreDial from '../components/common/ScoreDial'

export default function Landing() {
  return (
    <main className="public-page">
      <nav className="public-nav">
        <Link to="/" className="brand public-brand">
          <span className="brand-mark"><Gauge size={19} /></span>
          <span><strong>PrivateLens</strong><small>Private company intelligence</small></span>
        </Link>
        <div>
          <Link to="/login" className="btn btn-ghost">Log in</Link>
          <Link to="/signup" className="btn btn-primary">Start workspace</Link>
        </div>
      </nav>

      <section className="landing-hero">
        <div className="hero-copy">
          <div className="eyebrow">Private market research dashboard</div>
          <h1>PrivateLens</h1>
          <p>
            A financial health workspace for private-company diligence: scoring, reports,
            watchlists, search history, and peer comparison in one institutional dashboard.
          </p>
          <div className="hero-actions">
            <Link to="/signup" className="btn btn-primary">Create account <ArrowRight size={16} /></Link>
            <Link to="/login" className="btn btn-ghost">Open dashboard</Link>
          </div>
          <div className="trust-row">
            <span><CheckCircle2 size={15} /> 14 signal model</span>
            <span><CheckCircle2 size={15} /> SQLite or Postgres ready</span>
            <span><CheckCircle2 size={15} /> Render + Vercel deployable</span>
          </div>
        </div>

        <div className="terminal-preview" aria-label="PrivateLens dashboard preview">
          <header>
            <span />
            <span />
            <span />
            <strong>company_report.json</strong>
          </header>
          <div className="preview-grid">
            <ScoreDial score={742} rating="Strong" color="#2dd4bf" />
            <div className="preview-stack">
              <div><small>Company</small><strong>Acme Manufacturing</strong></div>
              <div><small>Risk level</small><strong>Moderate</strong></div>
              <div><small>Live signals</small><strong>5 / 14</strong></div>
            </div>
          </div>
          <div className="preview-bars">
            {[
              ['Cash flow', 78],
              ['Legal risk', 62],
              ['Hiring velocity', 84],
              ['Market sentiment', 68],
            ].map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <div><i style={{ width: `${value}%` }} /></div>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-band">
        {[
          [ShieldCheck, 'Research-grade scoring', 'Weighted signal model with live and modelled data clearly separated.'],
          [Database, 'Persistent workspace', 'Users keep history, reports, settings, and saved company lists.'],
          [BarChart3, 'Peer comparison', 'Compare up to four companies and spot outlier risk faster.'],
          [LockKeyhole, 'JWT authentication', 'Account-based API access with deployment-friendly environment config.'],
        ].map(([Icon, title, copy]) => (
          <article key={title}>
            <Icon size={20} />
            <h2>{title}</h2>
            <p>{copy}</p>
          </article>
        ))}
      </section>

      <footer className="public-footer">
        <span>PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice.</span>
      </footer>
    </main>
  )
}
