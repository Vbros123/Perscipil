import { BookmarkPlus, RefreshCw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from '../router'

import { getScore } from '../api/companies'
import { addWatchlist } from '../api/watchlist'
import Badge from '../components/common/Badge'
import ErrorNotice from '../components/common/ErrorNotice'
import PageHeader from '../components/common/PageHeader'
import CompanySummary from '../components/company/CompanySummary'
import EvidencePanel from '../components/company/EvidencePanel'
import SignalCard from '../components/company/SignalCard'

const SCOREABLE = new Set(['company', 'parent_company', 'subsidiary', 'brand'])

function loadingStages(name) {
  const label = name || 'company'
  return [
    `Resolving ${label}…`,
    `Analyzing ${label}…`,
    'Building PrivateScore…',
  ]
}

function entityLabel(type) {
  const labels = {
    company: 'Company',
    parent_company: 'Parent company',
    subsidiary: 'Subsidiary',
    brand: 'Brand',
    family: 'Family / historical entity',
    person: 'Person',
    organization: 'Organization',
    nonprofit: 'Nonprofit',
    government: 'Government',
    unknown: 'Unknown',
  }
  return labels[type] || type || 'Unknown'
}

function confidenceLabel(value) {
  const score = Number(value || 0)
  if (score >= 75) return 'High confidence'
  if (score >= 40) return 'Medium confidence'
  return 'Low relevance'
}

export default function CompanyReport() {
  const { company } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const companyName = decodeURIComponent(company || '')
  const selectedTitle = searchParams.get('selected') || ''
  const identity = {
    country_code: searchParams.get('country_code') || 'US',
    registration_number: searchParams.get('registration_number') || '',
    postal_code: searchParams.get('postal_code') || '',
  }
  const requestKey = [companyName, identity.country_code, identity.registration_number, identity.postal_code, selectedTitle].join('|')
  const stages = loadingStages(companyName)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [stage, setStage] = useState(stages[0])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const reportRequest = useRef({ company: '', promise: null })

  useEffect(() => {
    if (!loading) return undefined
    let index = 0
    setStage(stages[0])
    const timer = setInterval(() => {
      index = Math.min(index + 1, stages.length - 1)
      setStage(stages[index])
    }, 900)
    return () => clearInterval(timer)
  }, [loading, companyName])

  useEffect(() => {
    let mounted = true
    async function load() {
      setLoading(true)
      setError('')
      setMessage('')
      try {
        if (reportRequest.current.company !== requestKey) {
          reportRequest.current = {
            company: requestKey,
            promise: getScore(companyName, identity, false, selectedTitle),
          }
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
  }, [companyName, identity.country_code, identity.registration_number, identity.postal_code, selectedTitle])

  const save = async () => {
    if (!result) return
    setSaving(true)
    setMessage('')
    try {
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

  const chooseCandidate = async (candidate) => {
    const title = candidate.name || candidate.canonicalName
    const params = new URLSearchParams()
    params.set('country_code', identity.country_code || 'US')
    if (identity.registration_number) params.set('registration_number', identity.registration_number)
    if (identity.postal_code) params.set('postal_code', identity.postal_code)
    params.set('selected', title)
    setLoading(true)
    setError('')
    try {
      const data = await getScore(companyName, identity, true, title)
      setResult(data)
      reportRequest.current = { company: `${requestKey.split('|').slice(0, 4).join('|')}|${title}`, promise: Promise.resolve(data) }
      navigate(`/reports/${encodeURIComponent(companyName)}?${params.toString()}`, { replace: true })
    } catch (err) {
      setError(err.message || 'Unable to generate report.')
    } finally {
      setLoading(false)
    }
  }

  const warnings = result?.meta?.warnings || []
  const rankedCandidates = [...(result?.candidates || [])].sort((left, right) => {
    const leftScore = SCOREABLE.has(left.entityType) ? 1000 : 0
    const rightScore = SCOREABLE.has(right.entityType) ? 1000 : 0
    return (rightScore + Number(right.confidence || 0)) - (leftScore + Number(left.confidence || 0))
  })

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Company report"
        title={result?.company_name || companyName}
        actions={(
          <div className="report-actions">
            <button
              className="btn"
              onClick={() => {
                reportRequest.current = { company: '', promise: null }
                setLoading(true)
                getScore(companyName, identity, true, selectedTitle)
                  .then(setResult)
                  .catch((err) => setError(err.message || 'Unable to refresh report.'))
                  .finally(() => setLoading(false))
              }}
              disabled={loading}
            >
              <RefreshCw size={16} />
              Refresh
            </button>
            <button className="btn btn-primary" onClick={save} disabled={!result || saving || result.scoring_status === 'needs_disambiguation'}>
              <BookmarkPlus size={16} />
              {saving ? 'Saving' : 'Save'}
            </button>
          </div>
        )}
      >
        Research PrivateScore from available public and licensed signals. Not credit, investment, or lending advice.
      </PageHeader>

      {loading && (
        <div className="panel loading-panel">
          <RefreshCw className="spin" size={18} />
          <div>
            <strong>{stage}</strong>
            <div className="loading-stages">
              {stages.map((item) => (
                <span key={item} className={item === stage ? 'is-active' : ''}>{item}</span>
              ))}
            </div>
          </div>
        </div>
      )}
      <ErrorNotice message={error} />
      {message && <div className="notice notice-success">{message}</div>}
      {warnings.map((warning) => (
        <div key={warning} className="notice">{warning}</div>
      ))}

      {result?.scoring_status === 'needs_disambiguation' && !loading && (
        <section className="panel">
          <div className="panel-head">
            <div><div className="eyebrow">Choose a company</div><h2>More than one company matches this name</h2></div>
          </div>
          <div className="candidate-grid">
            {rankedCandidates.map((candidate) => {
              const scoreable = SCOREABLE.has(candidate.entityType)
              return (
                <button
                  key={candidate.url || candidate.name}
                  type="button"
                  className={`candidate-card ${scoreable ? 'is-preferred' : 'is-low-relevance'}`}
                  onClick={() => chooseCandidate(candidate)}
                >
                  <strong>{candidate.name || candidate.canonicalName}</strong>
                  <span>{entityLabel(candidate.entityType)}</span>
                  <span>{candidate.description || candidate.industry || 'No description'}</span>
                  {candidate.domain && <span>{candidate.domain}</span>}
                  <span>{confidenceLabel(candidate.confidence)}</span>
                </button>
              )
            })}
          </div>
        </section>
      )}

      {result && !loading && result.scoring_status !== 'needs_disambiguation' && (
        <>
          <CompanySummary result={result} />
          <EvidencePanel result={result} />
          <section className="panel">
            <div className="panel-head">
              <div><div className="eyebrow">Report narrative</div><h2>{result.report?.headline}</h2></div>
              <Badge tone="neutral">Model {result.meta?.model_version || result.metadata?.modelVersion}</Badge>
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
