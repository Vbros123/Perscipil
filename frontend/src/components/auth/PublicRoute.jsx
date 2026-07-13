import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../../context/AuthContext'

export default function PublicRoute() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return <div className="screen-loader">Loading PrivateLens</div>
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
