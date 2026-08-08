import { BookmarkPlus, RefreshCw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams } from '../router'

import { getScore } from '../api/companies'
import { addWatchlist } from '../api/watchlist'
import Badge from '../components/common/Badge'
import ErrorNotice from '../components/common/ErrorNotice'
import PageHeader from '../components/common/PageHeader'
import CompanySummary from '../components/company/CompanySummary'
import EvidencePanel from '../components/company/EvidencePanel'
import SignalCard from '../components/company/SignalCard'

export default function CompanyReport() {
  const { company } = useParams()
  const [searchParams] = useSearchParams()
  const companyName = decodeURIComponent(company || '')
  const identity = {
    country_code: searchParams.get('country_code') || 'US',
    registration_number: searchParams.get('registration_number') || '',
    postal_code: searchParams.get('postal_code') || '',
  }
  const requestKey = [companyName, identity.country_code, identity.registration_number, identity.postal_code].join('|')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const reportRequest = useRef({ company: '', promise: null })

  useEffect(() => {
    let mounted = true
    async function load() {
      setLoading(true)
      setError('')
      setMessage('')
      try {
        if (reportRequest.current.company !== requestKey) {
          reportRequest.current = { company: requestKey, promise: getScore(companyName, identity) }
        }
        const data = await reportRequest.current.promise
        if (mounted) setResult(data)
      } catch (err) {
        if (mounted) setError(err.message || 'Unable to generate report.')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    if (companyName) load()
    return () => { mounted = false }
  }, [companyName, identity.country_code, identity.registration_number, identity.postal_code])

  const save = async () => {
    if (!result) return
    setSaving(true)
    setMessage('')
    try {
      // Score, rating, and status are resolved server-side from the stored
      // report; the client only supplies its own annotations.
      await addWatchlist({
        company_name: result.company_name,
        notes: result.report?.headline,
        tags: [result.report?.risk_level || result.rating],
      })
      setMessage('Saved to watchlist.')
    } catch (err) {
      setError(err.message || 'Unable to save company.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Company report"
        title={companyName}
        actions={(
          <button className="btn btn-primary" onClick={save} disabled={!result || saving}>
            <BookmarkPlus size={16} />
            {saving ? 'Saving' : 'Save'}
          </button>
        )}
      >
        PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice.
      </PageHeader>

      {loading && <div className="panel loading-panel"><RefreshCw className="spin" size={18} /> Generating company report</div>}
      <ErrorNotice message={error} />
      {message && <div className="notice notice-success">{message}</div>}

      {result && !loading && (
        <>
          <CompanySummary result={result} />
          <EvidencePanel result={result} />
          <section className="panel">
            <div className="panel-head">
              <div><div className="eyebrow">Report narrative</div><h2>{result.report?.headline}</h2></div>
              <Badge tone="neutral">Model {result.meta?.model_version}</Badge>
            </div>
            <div className="report-columns">
              <div>
                <h3>Recommended next steps</h3>
                <ul className="clean-list">
                  {result.report?.recommended_next_steps?.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
              <div>
                <h3>Limitations</h3>
                <ul className="clean-list">
                  {result.report?.limitations?.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
            </div>
          </section>
          {result.report?.categories?.length > 0 && (
            <section className="panel">
              <div className="panel-head">
                <div><div className="eyebrow">Category health</div><h2>Risk domains</h2></div>
              </div>
              <div className="category-grid">
                {result.report.categories.map((category) => (
                  <article key={category.key}>
                    <span>{category.label}</span>
                    <strong>{Math.round(category.score)}/100</strong>
                    <div className="progress-track"><div className="progress-fill fill-accent" style={{ width: `${category.score}%` }} /></div>
                    <small>{category.signal_count} signals</small>
                  </article>
                ))}
              </div>
            </section>
          )}
          <section className="signal-grid">
            {result.breakdown?.map((signal) => <SignalCard key={signal.signal} signal={signal} />)}
          </section>
        </>
      )}
    </div>
  )
}
