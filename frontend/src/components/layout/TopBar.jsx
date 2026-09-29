import { ArrowRight, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from '../../router'

import { useAuth } from '../../context/AuthContext'

const titles = {
  '/dashboard': 'Dashboard',
  '/compare': 'Peer compare',
  '/watchlist': 'Watchlist',
  '/history': 'History',
  '/settings': 'Settings',
  '/account': 'Account',
  '/developer': 'Developer',
  '/pricing': 'Pricing',
}

export default function TopBar() {
  const [query, setQuery] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const title = useMemo(() => {
    if (location.pathname.startsWith('/reports')) return 'Company report'
    return titles[location.pathname] || 'Perspicil'
  }, [location.pathname])

  const submit = (event) => {
    event.preventDefault()
    if (!query.trim()) return
    navigate(`/reports/${encodeURIComponent(query.trim())}`)
    setQuery('')
  }

  return (
    <header className="topbar">
      <div>
        <div className="eyebrow">Research desk</div>
        <h1>{title}</h1>
      </div>
      <form className="top-search" onSubmit={submit}>
        <Search size={15} />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Look up a company" aria-label="Look up a company" />
        <button aria-label="Run lookup"><ArrowRight size={15} /></button>
      </form>
      <div className="user-badge">
        <span>{user?.first_name?.[0] || user?.email?.[0] || 'P'}</span>
        <div>
          <strong>{user?.first_name || 'Workspace'}</strong>
          <small>{user?.company || 'Perspicil'}</small>
        </div>
      </div>
    </header>
  )
}
