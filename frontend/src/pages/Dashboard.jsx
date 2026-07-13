import { BookmarkCheck, Building2, Clock3, Database, LineChart } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { getHistory, getSignals } from '../api/companies'
import { listWatchlist } from '../api/watchlist'
import EmptyState from '../components/common/EmptyState'
import ErrorNotice from '../components/common/ErrorNotice'
import MetricCard from '../components/common/MetricCard'
import PageHeader from '../components/common/PageHeader'
import SearchPanel from '../components/dashboard/SearchPanel'

function normalizeHistory(payload) {
  return Array.isArray(payload) ? payload : payload?.history || []
}

export default function Dashboard() {
  const [history, setHistory] = useState([])
  const [watchlist, setWatchlist] = useState([])
  const [signals, setSignals] = useState([])
  const [error, setError] = useState('')
  const navigate = useNavigate()

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
    const avgScore = history.length
      ? Math.round(history.reduce((sum, item) => sum + Number(item.private_score || 0), 0) / history.length)
      : '-'
    return [
      { icon: Building2, label: 'Companies screened', value: history.length, detail: 'Workspace history', tone: 'accent' },
      { icon: BookmarkCheck, label: 'Saved companies', value: watchlist.length, detail: 'Active watchlist', tone: 'positive' },
      { icon: LineChart, label: 'Average score', value: avgScore, detail: 'Recent searches', tone: 'neutral' },
      { icon: Database, label: 'Signal library', value: signals.length || 14, detail: 'Live and modelled inputs', tone: 'warning' },
      { icon: Clock3, label: 'Last check', value: last?.company_name || '-', detail: last?.rating || 'No history yet', tone: 'neutral' },
    ]
  }, [history, watchlist, signals])

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Overview" title="Financial health workspace">
        Run company checks, monitor saved names, and keep diligence history tied to your account.
      </PageHeader>
      <SearchPanel onSearch={(company) => navigate(`/reports/${encodeURIComponent(company)}`)} />
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
                  <strong style={{ color: item.color }}>{item.private_score}</strong>
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
                  <strong>{item.rating || '-'}</strong>
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
