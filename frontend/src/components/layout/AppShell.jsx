import {
  BarChart3,
  BookmarkCheck,
  Code2,
  CreditCard,
  Gauge,
  History,
  LayoutDashboard,
  LogOut,
  Settings,
  User,
} from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { API_BASE } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import TopBar from './TopBar'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/compare', label: 'Compare', icon: BarChart3 },
  { to: '/watchlist', label: 'Watchlist', icon: BookmarkCheck },
  { to: '/history', label: 'History', icon: History },
  { to: '/developer', label: 'Developer', icon: Code2 },
  { to: '/pricing', label: 'Pricing', icon: CreditCard },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function AppShell() {
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
          <span className="brand-mark"><Gauge size={19} /></span>
          <span>
            <strong>PrivateLens</strong>
            <small>Financial intelligence</small>
          </span>
        </NavLink>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                <Icon size={17} />
                {item.label}
              </NavLink>
            )
          })}
        </nav>
        <div className="side-footer">
          <a className="api-chip" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
            API docs
          </a>
          <NavLink className="profile-chip" to="/account">
            <User size={16} />
            <span>{user?.first_name || user?.email?.split('@')[0] || 'Account'}</span>
          </NavLink>
          <button className="nav-link logout" onClick={handleLogout}>
            <LogOut size={17} />
            Log out
          </button>
        </div>
      </aside>
      <main className="workspace">
        <TopBar />
        <Outlet />
      </main>
    </div>
  )
}
