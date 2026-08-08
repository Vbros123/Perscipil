import { BookmarkCheck, Building2, Clock3, Database, LineChart } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from '../router'

import { getHistory, getSignals } from '../api/companies'
import { listWatchlist } from '../api/watchlist'
import EmptyState from '../components/common/EmptyState'
import ErrorNotice from '../components/common/ErrorNotice'
import MetricCard from '../components/common/MetricCard'
import PageHeader from '../components/common/PageHeader'
import SearchPanel from '../components/dashboard/SearchPanel'
import { averageScore, displayRating, displayScore, isRated } from '../lib/score'

function normalizeHistory(payload) {
  return Array.isArray(payload) ? payload : payload?.history || []
}

export default function Dashboard() {
  const [history, setHistory] = useState([])
  const [watchlist, setWatchlist] = useState([])
  const [signals, setSignals] = useState([])
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const openReport = (identity) => {
    const params = new URLSearchParams()
    if (identity.registration_number) params.set('registration_number', identity.registration_number)
    if (identity.postal_code) params.set('postal_code', identity.postal_code)
    params.set('country_code', identity.country_code || 'US')
    navigate(`/reports/${encodeURIComponent(identity.legal_name)}?${params.toString()}`)
  }

  useEffect(() => {
    let mounted = true
    async function load() {
      try {
        const [historyPayload, savedPayload, signalPayload] = await Promise.all([
          getHistory(8),
          listWatchlist(),
          getSignals(),
        ])
        if (!mounted) return
        setHistory(normalizeHistory(historyPayload))
        setWatchlist(savedPayload || [])
        setSignals(signalPayload?.signals || [])
      } catch (err) {
        if (mounted) setError(err.message || 'Unable to load dashboard.')
      }
    }
    load()
    return () => { mounted = false }
  }, [])

  const metrics = useMemo(() => {
    const last = history[0]
    const average = averageScore(history)
    const ratedCount = history.filter(isRated).length
    const uniqueCompanies = new Set(
      history.map((item) => (item.normalized_name || item.company_name || '').toLowerCase()),
    ).size
    return [
      { icon: Building2, label: 'Companies screened', value: uniqueCompanies, detail: 'Unique names in history', tone: 'accent' },
      { icon: BookmarkCheck, label: 'Saved companies', value: watchlist.length, detail: 'Active watchlist', tone: 'positive' },
      {
        icon: LineChart,
        label: 'Average score',
        value: average === null ? 'N/A' : average,
        detail: average === null ? 'No rated companies yet' : `Across ${ratedCount} rated ${ratedCount === 1 ? 'company' : 'companies'}`,
        tone: 'neutral',
      },
      { icon: Database, label: 'Signal library', value: signals.length, detail: 'Verified, context, and unavailable inputs', tone: 'warning' },
      { icon: Clock3, label: 'Last check', value: last?.company_name || '-', detail: displayRating(last, 'No history yet'), tone: 'neutral' },
    ]
  }, [history, watchlist, signals])

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Overview" title="Financial health workspace">
        Run company checks, monitor saved names, and keep diligence history tied to your account.
      </PageHeader>
      <SearchPanel onSearch={openReport} />
      <ErrorNotice message={error} />
      <section className="metric-grid dashboard-metrics">
        {metrics.map((item) => <MetricCard key={item.label} {...item} />)}
      </section>
      <section className="dashboard-grid">
        <div className="panel">
          <div className="panel-head">
            <div><div className="eyebrow">Recent research</div><h2>History</h2></div>
            <Link to="/history" className="text-link">View all</Link>
          </div>
          {history.length ? (
            <div className="activity-list">
              {history.slice(0, 6).map((item, index) => (
                <Link key={`${item.company_name}-${item.id || index}`} to={`/reports/${encodeURIComponent(item.company_name)}`}>
                  <span>{item.company_name}</span>
                  <strong style={{ color: item.color }}>{displayScore(item)}</strong>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState icon={Building2} title="No companies scored yet">Run your first search to populate the desk.</EmptyState>
          )}
        </div>
        <div className="panel">
          <div className="panel-head">
            <div><div className="eyebrow">Saved names</div><h2>Watchlist</h2></div>
            <Link to="/watchlist" className="text-link">Manage</Link>
          </div>
          {watchlist.length ? (
            <div className="activity-list">
              {watchlist.slice(0, 6).map((item) => (
                <Link key={item.id} to={`/reports/${encodeURIComponent(item.company_name)}`}>
                  <span>{item.company_name}</span>
                  <strong>{displayRating(item, '-')}</strong>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState icon={BookmarkCheck} title="No saved companies">Save companies from a report to build a monitor list.</EmptyState>
          )}
        </div>
      </section>
    </div>
  )
}
