import React, { useState, useRef, useCallback, useEffect } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  Building2,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Database,
  ExternalLink,
  Gauge,
  History,
  Landmark,
  Layers3,
  LayoutGrid,
  LineChart,
  Loader2,
  Mail,
  Network,
  Scale,
  Search,
  ShieldCheck,
  Table2,
  Target,
  TrendingUp,
  X,
} from 'lucide-react'
import './styles/App.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const clamp = (value, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, value))
const examples = ['Cargill', 'Koch Industries', 'Deloitte', 'Bechtel', 'Publix', 'Mars Inc']

const categoryMeta = {
  financial: { label: 'Financial health', icon: CircleDollarSign },
  operational: { label: 'Operations', icon: Activity },
  legal: { label: 'Legal and regulatory', icon: Scale },
  sentiment: { label: 'Market sentiment', icon: LineChart },
  digital: { label: 'Digital presence', icon: Network },
}

const sourceStack = ['SEC EDGAR', 'Wikipedia', 'Indeed', 'DuckDuckGo + HN', 'USASpending']

function getCategoryMeta(category = '') {
  return categoryMeta[category] || { label: category || 'Signal', icon: Layers3 }
}

function formatPercent(value) {
  if (Number.isNaN(Number(value))) return '0%'
  return `${Math.round(Number(value) * 100)}%`
}

function StatusDot({ status = 'online' }) {
  return <span className={`status-dot status-${status}`} aria-hidden="true" />
}

function ApiStatus({ status }) {
  const label = status === 'online' ? 'API online' : status === 'offline' ? 'API offline' : 'Checking API'
  return (
    <span className={`api-status api-${status}`}>
      <StatusDot status={status === 'online' ? 'online' : status === 'offline' ? 'offline' : 'checking'} />
      {label}
    </span>
  )
}

function Sidebar({ history, onSelect, apiStatus }) {
  return (
    <aside className="sidebar">
      <div className="brand-lockup">
        <div className="brand-mark">
          <Gauge size={20} strokeWidth={2.4} />
        </div>
        <div>
          <div className="brand-name">PrivateLens</div>
          <div className="brand-sub">Private market credit intelligence</div>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="PrivateLens navigation">
        <span className="nav-item active"><LayoutGrid size={16} /> Score console</span>
        <span className="nav-item"><Database size={16} /> Signal library</span>
        <span className="nav-item"><ShieldCheck size={16} /> Risk review</span>
      </nav>

      <section className="sidebar-section">
        <div className="sidebar-heading">
          <History size={14} />
          Recent checks
        </div>
        {history?.length ? (
          <div className="history-list">
            {history.map((item, index) => (
              <button key={`${item.company_name}-${index}`} className="history-item" onClick={() => onSelect(item.company_name)}>
                <span className="history-name">{item.company_name}</span>
                <span className="history-score" style={{ color: item.color }}>{item.private_score}</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="empty-history">No checks in this session</div>
        )}
      </section>

      <div className="sidebar-footer">
        <ApiStatus status={apiStatus} />
        <span className="footer-target">Target: {API.replace(/^https?:\/\//, '')}</span>
      </div>
    </aside>
  )
}

function SearchCommand({ query, setQuery, loading, onSearch, inputRef }) {
  return (
    <section className="command-center">
      <div className="command-copy">
        <div className="eyebrow">PrivateScore console</div>
        <h1>Score private companies with lender-grade signal coverage.</h1>
        <p>
          PrivateLens blends public, commercial, legal, operating, and sentiment signals into a single
          0-1000 health score for private-company diligence.
        </p>
      </div>

      <form className="search-form" onSubmit={(event) => { event.preventDefault(); onSearch() }}>
        <div className="search-box">
          <Search className="search-icon" size={18} />
          <input
            ref={inputRef}
            className="search-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search a US private company"
            disabled={loading}
            autoFocus
          />
          {query && (
            <button type="button" className="icon-btn clear-btn" onClick={() => setQuery('')} aria-label="Clear search">
              <X size={16} />
            </button>
          )}
          <button className="primary-action" type="submit" disabled={loading || !query.trim()}>
            {loading ? <Loader2 size={17} className="spin-icon" /> : <Search size={17} />}
            <span>Run score</span>
          </button>
        </div>

        <div className="example-pills">
          {examples.map((example) => (
            <button key={example} type="button" className="example-pill" onClick={() => onSearch(example)} disabled={loading}>
              {example}
            </button>
          ))}
        </div>
      </form>
    </section>
  )
}

function MetricCard({ icon: Icon, label, value, detail, tone = 'neutral' }) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <div className="metric-icon"><Icon size={18} /></div>
      <div>
        <div className="metric-label">{label}</div>
        <div className="metric-value">{value}</div>
        {detail && <div className="metric-detail">{detail}</div>}
      </div>
    </div>
  )
}

function EmptyDashboard() {
  return (
    <div className="empty-dashboard fade-up">
      <div className="metric-grid">
        <MetricCard icon={Layers3} label="Signal model" value="14 factors" detail="Weighted across five risk domains" tone="blue" />
        <MetricCard icon={Database} label="Live sources" value="5 active" detail="Public data already connected" tone="green" />
        <MetricCard icon={Building2} label="Market coverage" value="30M+" detail="US private companies" tone="gold" />
        <MetricCard icon={Target} label="Score range" value="0-1000" detail="Built for screening and diligence" tone="neutral" />
      </div>

      <div className="workspace-grid">
        <section className="workspace-panel source-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">Data coverage</div>
              <h2>Live signals are separated from modelled signals.</h2>
            </div>
            <CheckCircle2 size={22} />
          </div>
          <div className="source-list">
            {sourceStack.map((source) => (
              <div className="source-row" key={source}>
                <span><StatusDot status="online" />{source}</span>
                <span>Live</span>
              </div>
            ))}
          </div>
        </section>

        <section className="workspace-panel market-panel">
          <div className="panel-header compact">
            <div>
              <div className="panel-kicker">Signal stack</div>
              <h2>Coverage spans finance, operations, legal, sentiment, and digital footprint.</h2>
            </div>
          </div>
          <div className="signal-radar" aria-hidden="true">
            {[
              ['Financial', 88],
              ['Operations', 72],
              ['Legal', 64],
              ['Sentiment', 79],
              ['Digital', 58],
            ].map(([label, value]) => (
              <div className="radar-row" key={label}>
                <span>{label}</span>
                <div className="radar-track"><div style={{ width: `${value}%` }} /></div>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

function ScoreGauge({ score, color, rating }) {
  const radius = 84
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - score / 1000)

  return (
    <div className="gauge-wrap">
      <svg viewBox="0 0 220 220" width="220" height="220" role="img" aria-label={`PrivateScore ${score} out of 1000`}>
        <circle cx="110" cy="110" r={radius} fill="none" stroke="var(--surface-muted)" strokeWidth="14" />
        <circle
          cx="110"
          cy="110"
          r={radius}
          fill="none"
          stroke={color || 'var(--accent)'}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 110 110)"
          className="gauge-ring"
        />
        <text x="110" y="104" textAnchor="middle" fill="var(--text)" fontSize="44" fontWeight="800" fontFamily="Inter">{score}</text>
        <text x="110" y="128" textAnchor="middle" fill="var(--text-muted)" fontSize="14" fontFamily="Inter">of 1000</text>
        <text x="110" y="154" textAnchor="middle" fill={color || 'var(--accent)'} fontSize="15" fontWeight="700" fontFamily="Inter">{rating}</text>
      </svg>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="signal-card skeleton-card">
      <div className="skeleton skeleton-title" />
      <div className="skeleton skeleton-line wide" />
      <div className="skeleton skeleton-bar" />
      <div className="skeleton skeleton-line" />
    </div>
  )
}

function SkeletonOverview() {
  return (
    <div className="loading-state">
      <div className="score-overview skeleton-overview">
        <div className="skeleton skeleton-gauge" />
        <div className="score-copy">
          <div className="skeleton skeleton-heading" />
          <div className="skeleton skeleton-line wide" />
          <div className="skeleton skeleton-line medium" />
          <div className="skeleton-row">
            <div className="skeleton skeleton-chip" />
            <div className="skeleton skeleton-chip" />
            <div className="skeleton skeleton-chip" />
          </div>
        </div>
      </div>
      <div className="signals-grid">
        {Array.from({ length: 6 }).map((_, index) => <SkeletonCard key={index} />)}
      </div>
    </div>
  )
}

function SignalCard({ signal, idx }) {
  const pct = clamp(Number(signal.raw_score) || 0)
  const status = signal.is_simulated ? 'modelled' : 'live'
  const barColor = pct >= 70 ? 'var(--green)' : pct >= 45 ? 'var(--accent)' : pct >= 28 ? 'var(--gold)' : 'var(--red)'
  const meta = getCategoryMeta(signal.category)
  const Icon = meta.icon

  return (
    <article className="signal-card fade-up" style={{ animationDelay: `${idx * 28}ms` }}>
      <div className="signal-top">
        <span className="signal-icon"><Icon size={17} /></span>
        <div>
          <h3>{signal.signal}</h3>
          <p>{meta.label}</p>
        </div>
        <span className={`source-badge source-${status}`}>
          <StatusDot status={signal.is_simulated ? 'checking' : 'online'} />
          {signal.is_simulated ? 'Modelled' : 'Live'}
        </span>
      </div>

      <div className="signal-score-row">
        <span>{signal.display || 'Signal observed'}</span>
        <strong>{pct.toFixed(0)}/100</strong>
      </div>

      <div className="sig-bar-bg">
        <div className="sig-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
      </div>

      <p className="sig-insight">{signal.insight}</p>

      <div className="signal-footer">
        <span>Weight {signal.weight_pct || `${Math.round((signal.weight || 0) * 100)}%`}</span>
        {signal.source_url && (
          <a href={signal.source_url} target="_blank" rel="noopener noreferrer" className="sig-link">
            Source <ExternalLink size={12} />
          </a>
        )}
      </div>
    </article>
  )
}

function CategoryBar({ label, score, count }) {
  const pct = clamp(Number(score) || 0)
  const color = pct >= 70 ? 'var(--green)' : pct >= 45 ? 'var(--accent)' : pct >= 28 ? 'var(--gold)' : 'var(--red)'

  return (
    <div className="cat-bar">
      <div className="cat-label">
        <span>{label}</span>
        <strong style={{ color }}>{pct.toFixed(0)}/100</strong>
      </div>
      <div className="cat-track">
        <div className="cat-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="cat-count">{count} signal{count !== 1 ? 's' : ''}</div>
    </div>
  )
}

function RiskFlags({ flags }) {
  if (!flags?.length) return null

  return (
    <section className="risk-box">
      <div className="risk-title"><AlertTriangle size={18} /> Risk flags detected</div>
      {flags.map((flag, index) => (
        <div key={index} className="risk-item">{String(flag).replace(/^⚠️\s*/, '')}</div>
      ))}
    </section>
  )
}

function ComparePanel({ onCompare, loading }) {
  const [input, setInput] = useState('')

  return (
    <section className="compare-panel">
      <div>
        <div className="compare-label">Peer view</div>
        <h2>Compare up to four companies side by side.</h2>
      </div>
      <div className="compare-row">
        <input
          className="compare-input"
          placeholder="Cargill, Deloitte, Bechtel"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && input.trim() && onCompare(input)}
        />
        <button className="secondary-action" onClick={() => input.trim() && onCompare(input)} disabled={loading}>
          {loading ? <Loader2 size={16} className="spin-icon" /> : <BarChart3 size={16} />}
          Compare
        </button>
      </div>
    </section>
  )
}

function CompareResults({ data, onClose }) {
  if (!data) return null
  const max = Math.max(...data.companies.map((company) => company.private_score))

  return (
    <section className="compare-results fade-up">
      <div className="compare-header">
        <div>
          <div className="compare-label">Comparison result</div>
          <h2>{data.winner} leads the peer set.</h2>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close comparison">
          <X size={18} />
        </button>
      </div>
      <p className="compare-analysis">{data.analysis}</p>
      <div className="compare-grid">
        {data.companies.map((company, index) => (
          <article key={`${company.company_name}-${index}`} className={`compare-card ${company.private_score === max ? 'compare-winner' : ''}`}>
            <div className="compare-company">{company.company_name}</div>
            <div className="compare-score" style={{ color: company.color }}>{company.private_score}</div>
            <div className="compare-rating">{company.rating}</div>
            <div className="compare-bar-bg">
              <div className="compare-bar-fill" style={{ width: `${company.private_score / 10}%`, background: company.color }} />
            </div>
            {company.private_score === max && <div className="winner-badge">Leader</div>}
          </article>
        ))}
      </div>
    </section>
  )
}

function Results({ result, activeTab, setActiveTab }) {
  const meta = result.meta || {}
  const confidence = Number(meta.confidence || 0)
  const computedAt = meta.computed_at ? new Date(meta.computed_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : 'Live'

  return (
    <div className="results fade-up">
      <div className="results-topline">
        <div>
          <div className="eyebrow">Company risk profile</div>
          <h2>{result.company_name}</h2>
        </div>
        <span className="computed-pill"><Clock3 size={15} /> Updated {computedAt}</span>
      </div>

      <div className="score-grid">
        <section className="score-overview">
          <ScoreGauge score={result.private_score} color={result.color} rating={result.rating} />
          <div className="score-copy">
            <div className="score-label">PrivateScore assessment</div>
            <p className="score-summary">{result.summary}</p>
            <div className="meta-row">
              <span className="meta-pill live-pill"><StatusDot status="online" />{meta.real_signals || 0} live signals</span>
              <span className="meta-pill sim-pill"><StatusDot status="checking" />{meta.simulated_signals || 0} modelled</span>
              <span className="meta-pill">{formatPercent(confidence)} confidence</span>
              {meta.cached && <span className="meta-pill">Cached response</span>}
            </div>
            {meta.disclaimer && <p className="disclaimer">{meta.disclaimer}</p>}
          </div>
        </section>

        <div className="metric-grid result-metrics">
          <MetricCard icon={Database} label="Live signal mix" value={`${meta.real_signals || 0}/${meta.total_signals || 14}`} detail="Connected data sources" tone="green" />
          <MetricCard icon={Activity} label="Model coverage" value={formatPercent(confidence)} detail="Current live confidence" tone="blue" />
          <MetricCard icon={Clock3} label="Response time" value={`${result.elapsed_seconds}s`} detail="API scoring latency" tone="neutral" />
          <MetricCard icon={ShieldCheck} label="Rating band" value={result.rating} detail="Risk-screening output" tone="gold" />
        </div>
      </div>

      <RiskFlags flags={result.risk_flags} />

      <div className="tab-row" role="tablist" aria-label="Score details">
        <button className={`tab-btn ${activeTab === 'signals' ? 'active' : ''}`} onClick={() => setActiveTab('signals')}>
          <Table2 size={16} /> Signal breakdown
        </button>
        <button className={`tab-btn ${activeTab === 'categories' ? 'active' : ''}`} onClick={() => setActiveTab('categories')}>
          <TrendingUp size={16} /> Category analysis
        </button>
      </div>

      {activeTab === 'signals' && (
        <div className="signals-grid">
          {result.breakdown?.map((signal, index) => <SignalCard key={`${signal.signal}-${index}`} signal={signal} idx={index} />)}
        </div>
      )}

      {activeTab === 'categories' && (
        <section className="cat-section fade-in">
          {Object.entries(result.category_summary || {}).map(([key, value]) => (
            <CategoryBar key={key} label={value.label} score={value.score} count={value.signal_count} />
          ))}
        </section>
      )}

      <section className="funding-cta">
        <div>
          <div className="cta-kicker">Data unlock roadmap</div>
          <h2>Replacing modelled signals with licensed data turns the score into a real-time underwriting layer.</h2>
          <p>
            The next data unlocks are UCC filings, open banking cash-flow APIs, court records, payroll and review data,
            web traffic, and supply-chain risk feeds.
          </p>
        </div>
        <a href="mailto:vijithvelamuri@gmail.com?subject=PrivateLens%20Access%20Request" className="primary-action cta-btn">
          <Mail size={17} />
          Contact founder
        </a>
      </section>
    </div>
  )
}

export default function App() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState([])
  const [compareData, setCompareData] = useState(null)
  const [compareLoading, setCompareLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('signals')
  const [apiStatus, setApiStatus] = useState('checking')
  const inputRef = useRef(null)

  const checkApi = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/health`)
      setApiStatus(response.ok ? 'online' : 'offline')
    } catch {
      setApiStatus('offline')
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/history?limit=8`)
      if (response.ok) {
        const data = await response.json()
        setHistory(data.history || [])
      }
    } catch {
      setHistory([])
    }
  }, [])

  useEffect(() => {
    checkApi()
    fetchHistory()
  }, [checkApi, fetchHistory])

  const search = useCallback(async (name) => {
    const company = (name || query).trim()
    if (!company) return

    setQuery(company)
    setLoading(true)
    setResult(null)
    setError('')
    setCompareData(null)

    try {
      const response = await fetch(`${API}/api/score?company=${encodeURIComponent(company)}`)
      if (!response.ok) {
        const errorPayload = await response.json()
        throw new Error(errorPayload.detail || 'Scoring failed')
      }
      const data = await response.json()
      setResult(data)
      setApiStatus('online')
      fetchHistory()
    } catch (err) {
      setApiStatus('offline')
      setError(err.message || 'Failed to connect to PrivateLens API.')
    } finally {
      setLoading(false)
    }
  }, [query, fetchHistory])

  const handleCompare = async (input) => {
    setCompareLoading(true)
    setCompareData(null)
    setError('')

    try {
      const encoded = encodeURIComponent(input.trim())
      const response = await fetch(`${API}/api/compare?companies=${encoded}`)
      if (!response.ok) {
        const errorPayload = await response.json()
        throw new Error(errorPayload.detail || 'Comparison failed')
      }
      setCompareData(await response.json())
      setApiStatus('online')
    } catch (err) {
      setApiStatus('offline')
      setError(err.message || 'Failed to compare companies.')
    } finally {
      setCompareLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <Sidebar history={history} onSelect={search} apiStatus={apiStatus} />

      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="eyebrow">Private market desk</div>
            <h2>Financial health intelligence</h2>
          </div>
          <div className="topbar-actions">
            <ApiStatus status={apiStatus} />
            <span className="topbar-pill">Model v2.0</span>
            <a className="topbar-link" href={`${API}/docs`} target="_blank" rel="noopener noreferrer">
              API docs <ArrowUpRight size={14} />
            </a>
          </div>
        </header>

        <SearchCommand
          query={query}
          setQuery={(value) => {
            setQuery(value)
            if (!value) {
              setResult(null)
              setError('')
            }
          }}
          loading={loading}
          onSearch={search}
          inputRef={inputRef}
        />

        <ComparePanel onCompare={handleCompare} loading={compareLoading} />
        {compareData && <CompareResults data={compareData} onClose={() => setCompareData(null)} />}
        {error && <div className="error-box"><AlertTriangle size={18} /> {error}</div>}
        {loading && <SkeletonOverview />}
        {!result && !loading && <EmptyDashboard />}
        {result && !loading && <Results result={result} activeTab={activeTab} setActiveTab={setActiveTab} />}

        <footer className="footer">
          <span>PrivateLens 2026</span>
          <a href="https://github.com/Bruh-Gang/privatelens" target="_blank" rel="noopener noreferrer">GitHub</a>
          <span>Built by Vijith Velamuri</span>
        </footer>
      </main>
    </div>
  )
}
