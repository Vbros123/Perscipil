import { BarChart3, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from '../router'

import { compareCompanies } from '../api/companies'
import ErrorNotice from '../components/common/ErrorNotice'
import PageHeader from '../components/common/PageHeader'
import ScoreDial from '../components/common/ScoreDial'

export default function Compare() {
  const [input, setInput] = useState('Cargill, Deloitte, Bechtel')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      setResult(await compareCompanies(input))
    } catch (err) {
      setError(err.message || 'Unable to compare companies.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Peer analysis" title="Compare companies">
        Compare two to four private companies using the same PrivateScore model.
      </PageHeader>
      <form className="panel compare-form" onSubmit={submit}>
        <label>Companies<input value={input} onChange={(event) => setInput(event.target.value)} /></label>
        <button className="btn btn-primary" disabled={loading}>
          {loading ? <Loader2 className="spin" size={16} /> : <BarChart3 size={16} />}
          Compare
        </button>
      </form>
      <ErrorNotice message={error} />
      {result && (
        <section className="page-stack">
          <div className="notice notice-info">{result.analysis}</div>
          {result.failed?.length > 0 && (
            <div className="notice notice-warning">
              {result.failed.length} of {result.requested?.length ?? '?'} companies could not be analysed
              and are missing from this comparison: {result.failed.join(', ')}.
            </div>
          )}
          <div className="compare-grid">
            {result.companies.map((company) => (
              <Link className="compare-card" key={company.company_name} to={`/reports/${encodeURIComponent(company.company_name)}`}>
                <ScoreDial score={company.private_score} rating={company.rating} color={company.color} />
                <h2>{company.company_name}</h2>
                <p>{company.report?.headline || company.summary}</p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
