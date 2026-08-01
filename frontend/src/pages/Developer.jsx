import { Code2, Copy, ExternalLink } from 'lucide-react'

import { API_BASE } from '../api/client'
import Badge from '../components/common/Badge'
import PageHeader from '../components/common/PageHeader'

const endpoints = [
  ['POST', '/api/auth/signup', 'Create account'],
  ['POST', '/api/auth/login', 'Issue bearer token'],
  ['POST', '/api/auth/logout', 'Record logout audit event'],
  ['POST', '/api/auth/change-password', 'Rotate password and invalidate sessions'],
  ['POST', '/api/auth/request-password-reset', 'Issue reset instructions'],
  ['POST', '/api/auth/reset-password', 'Reset password with token'],
  ['POST', '/api/auth/request-email-verification', 'Issue verification instructions'],
  ['POST', '/api/auth/verify-email', 'Verify email with token'],
  ['GET', '/api/auth/me', 'Current user'],
  ['GET', '/api/compliance/status', 'Production readiness status'],
  ['GET', '/api/metrics', 'Bearer-token protected metrics'],
  ['GET', '/api/score?company=NAME', 'Backward-compatible report'],
  ['POST', '/api/score', 'Legal-entity report request'],
  ['GET', '/api/providers', 'Licensed provider readiness'],
  ['GET', '/api/compare?companies=A,B', 'Peer comparison'],
  ['GET', '/api/watchlist', 'Saved companies'],
  ['GET', '/api/history', 'Search history'],
  ['PATCH', '/api/settings', 'Workspace settings'],
]

export default function Developer() {
  const copy = (value) => navigator.clipboard?.writeText(value)

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="API"
        title="Developer"
        actions={<a className="btn btn-ghost" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">Swagger <ExternalLink size={16} /></a>}
      >
        Use bearer tokens from login/signup for authenticated workspace endpoints.
      </PageHeader>
      <section className="panel">
        <div className="panel-head">
          <div><div className="eyebrow">Base URL</div><h2>{API_BASE}</h2></div>
          <button className="icon-button" onClick={() => copy(API_BASE)} aria-label="Copy API base"><Copy size={16} /></button>
        </div>
        <pre className="code-block">{`curl -X POST "${API_BASE}/api/score" \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{"legal_name":"Acme Manufacturing LLC","country_code":"US","registration_number":"A-123"}'`}</pre>
      </section>
      <section className="table-card">
        <table>
          <thead><tr><th>Method</th><th>Endpoint</th><th>Description</th></tr></thead>
          <tbody>
            {endpoints.map(([method, path, description]) => (
              <tr key={`${method}-${path}`}>
                <td><Badge tone={method === 'GET' ? 'positive' : 'accent'}>{method}</Badge></td>
                <td className="mono">{path}</td>
                <td className="muted">{description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="notice notice-info">
        <Code2 size={17} />
        Only entity-resolved, fresh licensed observations can set <code>used_in_score=true</code>. Public context and unavailable inputs are excluded.
      </section>
    </div>
  )
}
