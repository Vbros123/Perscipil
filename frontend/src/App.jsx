import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/auth/ProtectedRoute'
import PublicRoute from './components/auth/PublicRoute'
import AppShell from './components/layout/AppShell'
import Account from './pages/Account'
import CompanyReport from './pages/CompanyReport'
import Compare from './pages/Compare'
import Dashboard from './pages/Dashboard'
import Developer from './pages/Developer'
import ForgotPassword from './pages/ForgotPassword'
import History from './pages/History'
import Landing from './pages/Landing'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import Onboarding from './pages/Onboarding'
import Pricing from './pages/Pricing'
import ResetPassword from './pages/ResetPassword'
import Settings from './pages/Settings'
import Signup from './pages/Signup'
import Watchlist from './pages/Watchlist'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route element={<PublicRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
          </Route>
          <Route element={<ProtectedRoute />}>
            <Route path="/onboarding" element={<Onboarding />} />
            <Route element={<AppShell />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/reports/:company" element={<CompanyReport />} />
              <Route path="/compare" element={<Compare />} />
              <Route path="/watchlist" element={<Watchlist />} />
              <Route path="/history" element={<History />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/account" element={<Account />} />
              <Route path="/developer" element={<Developer />} />
              <Route path="/pricing" element={<Pricing />} />
            </Route>
          </Route>
          <Route path="/app" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
