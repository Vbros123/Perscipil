import BrandMark from '../common/BrandMark'
import PolicyReview from '../common/PolicyReview'
import { BRAND } from '../../lib/brand'
import {
  BarChart3,
  BookmarkCheck,
  Code2,
  CreditCard,
  History,
  LayoutDashboard,
  LogOut,
  Settings,
  User,
} from 'lucide-react'
import { NavLink, useNavigate } from '../../router'

import { useAuth } from '../../context/AuthContext'
import TopBar from './TopBar'

const sections = [
  {
    label: 'Research',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/batches', label: 'Bulk screening', icon: BarChart3 },
      { to: '/compare', label: 'Compare', icon: BarChart3 },
      { to: '/watchlist', label: 'Watchlist', icon: BookmarkCheck },
      { to: '/research-review', label: 'Research review', icon: BookmarkCheck },
      { to: '/history', label: 'History', icon: History },
    ],
  },
  {
    label: 'Workspace',
    items: [
      { to: '/workspaces', label: 'Team workspaces', icon: User },
      { to: '/developer', label: 'Developer', icon: Code2 },
      { to: '/pricing', label: 'Pricing', icon: CreditCard },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

export default function AppShell({ children }) {
  const { logout, user } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/')
  }

  return (
    <div className="app-frame">
      <aside className="side-nav">
        <NavLink to="/dashboard" className="brand">
          <BrandMark />
          <span>
            <strong>{BRAND.name}</strong>
            <small>Company intelligence</small>
          </span>
        </NavLink>
        <nav aria-label="Primary">
          {sections.map((section) => (
            <div key={section.label} style={{ display: 'contents' }}>
              <div className="nav-section">{section.label}</div>
              {section.items.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                    <Icon size={16} />
                    {item.label}
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>
        <div className="side-footer">
          <a className="api-chip" href="/developer" target="_blank" rel="noreferrer">
            API documentation
          </a>
          <NavLink className="profile-chip" to="/account">
            <User size={15} />
            <span>{user?.first_name || user?.email?.split('@')[0] || 'Account'}</span>
          </NavLink>
          <button className="nav-link logout" onClick={handleLogout}>
            <LogOut size={16} />
            Log out
          </button>
        </div>
      </aside>
      <main className="workspace">
        <TopBar />
        <PolicyReview />{children}
      </main>
    </div>
  )
}
