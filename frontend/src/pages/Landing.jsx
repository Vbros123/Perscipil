import { ArrowRight, BarChart3, Database, ScanSearch, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import { Link } from '../router'

import ScoreBand from '../components/common/ScoreBand'

const SAMPLE_SIGNALS = [
  ['Commercial credit risk', 82, 'strong'],
  ['B2B payment behavior', 74, 'strong'],
  ['Cash flow & liquidity', 61, 'steady'],
  ['Identity & standing', 100, 'strong'],
  ['Liens & litigation', 88, 'strong'],
]

export default function Landing() {
  return (
    <main className="public-page">
      <nav className="public-nav">
        <Link to="/" className="brand">
          <span className="brand-mark"><ScanSearch size={17} /></span>
          <span><strong>PrivateLens</strong><small>Company intelligence</small></span>
        </Link>
        <div>
          <Link to="/login" className="btn btn-ghost">Log in</Link>
          <Link to="/signup" className="btn btn-primary">Create account</Link>
        </div>
      </nav>

      <section className="landing-hero">
        <div className="hero-copy">
          <div className="eyebrow">Private-company diligence</div>
          <h1>Financial health ratings, gated by evidence.</h1>
          <p>
            PrivateLens screens private companies with a deterministic scoring model.
            A rating is only released when entity identity, evidence coverage, provider
            diversity, and model validation all pass — otherwise it says so.
          </p>
          <div className="hero-actions">
            <Link to="/signup" className="btn btn-primary">Start researching <ArrowRight size={15} /></Link>
            <Link to="/login" className="btn btn-ghost">Open workspace</Link>
          </div>
          <div className="trust-row">
            <span><ShieldCheck size={14} /> Evidence release gates</span>
            <span><Database size={14} /> Licensed + public sources</span>
            <span><SlidersHorizontal size={14} /> Deterministic model</span>
          </div>
        </div>

        <div className="sample-report" aria-label="Illustrative sample report">
          <div className="sample-report-head">
            <div>
              <strong>Acme Manufacturing LLC</strong>
              <small>US &middot; Registration A-4821</small>
            </div>
            <span className="badge">Illustrative sample</span>
          </div>
          {/* 0.30*82 + 0.20*74 + 0.20*61 + 0.15*100 + 0.15*88 = 79.8 -> 798 */}
          <div className="sample-score">
            <strong className="tone-strong">798</strong>
            <span className="tone-strong">Strong</span>
            <small>/ 1000</small>
          </div>
          <ScoreBand score={798} rated />
          <div className="sample-rows">
            {SAMPLE_SIGNALS.map(([label, value, tone]) => (
              <div key={label}>
                <span>{label}</span>
                <div className="progress-track">
                  <div className={`progress-fill fill-${tone === 'strong' ? 'positive' : 'accent'}`} style={{ width: `${value}%` }} />
                </div>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <div className="sample-foot">
            <span>Coverage 100%</span>
            <span>3 licensed providers</span>
            <span>All release gates passed</span>
          </div>
        </div>
      </section>

      <section className="landing-band">
        {[
          [ShieldCheck, 'Evidence-gated scoring', 'Entity match, freshness, provider diversity, and model approval are enforced before any rating is released.'],
          [Database, 'Transparent provenance', 'Every signal names its source, observation date, and entity-match confidence. Nothing is invented to fill gaps.'],
          [BarChart3, 'Peer comparison', 'Compare up to four companies side by side under the same model and spot outlier risk faster.'],
          [ScanSearch, 'Persistent workspace', 'History, watchlists, saved reports, and settings stay tied to your account across sessions.'],
        ].map(([Icon, title, copy]) => (
          <article key={title}>
            <Icon size={18} />
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
