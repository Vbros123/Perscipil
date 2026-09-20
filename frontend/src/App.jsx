import { Redirect, Route, Router, Switch } from './router'

import { AuthProvider, useAuth } from './context/AuthContext'
import AppShell from './components/layout/AppShell'
import Account from './pages/Account'
import Batch from './pages/Batch'
import ResearchControls from './pages/ResearchControls'
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
import VerifyEmail from './pages/VerifyEmail'
import Watchlist from './pages/Watchlist'

function Protected({ children, shell = true }) {
  const { isAuthenticated, loading } = useAuth()

  if (loading) return <div className="screen-loader">Loading PrivateLens</div>
  if (!isAuthenticated) return <Redirect to="/login" />
  return shell ? <AppShell>{children}</AppShell> : children
}

function PublicOnly({ children }) {
  const { isAuthenticated, loading } = useAuth()

  if (loading) return <div className="screen-loader">Loading PrivateLens</div>
  if (isAuthenticated) return <Redirect to="/dashboard" />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Switch>
          <Route path="/" component={Landing} />
          <Route path="/signup" component={Signup} />
          <Route path="/login"><PublicOnly><Login /></PublicOnly></Route>
          <Route path="/forgot-password"><PublicOnly><ForgotPassword /></PublicOnly></Route>
          <Route path="/reset-password"><PublicOnly><ResetPassword /></PublicOnly></Route>
          <Route path="/verify-email"><PublicOnly><VerifyEmail /></PublicOnly></Route>
          <Route path="/onboarding"><Protected shell={false}><Onboarding /></Protected></Route>
          <Route path="/dashboard"><Protected><Dashboard /></Protected></Route>
          <Route path="/reports/:company"><Protected><CompanyReport /></Protected></Route>
          <Route path="/research-review"><Protected><ResearchControls /></Protected></Route>
          <Route path="/batches"><Protected><Batch /></Protected></Route>
          <Route path="/compare"><Protected><Compare /></Protected></Route>
          <Route path="/watchlist"><Protected><Watchlist /></Protected></Route>
          <Route path="/history"><Protected><History /></Protected></Route>
          <Route path="/settings"><Protected><Settings /></Protected></Route>
          <Route path="/account"><Protected><Account /></Protected></Route>
          <Route path="/developer"><Protected><Developer /></Protected></Route>
          <Route path="/pricing"><Protected><Pricing /></Protected></Route>
          <Route path="/app"><Redirect to="/dashboard" /></Route>
          <Route><NotFound /></Route>
        </Switch>
      </Router>
    </AuthProvider>
  )
}
