import { Loader2, Search } from 'lucide-react'
import { useState } from 'react'

const examples = ['Cargill', 'Deloitte', 'Bechtel', 'Mars Inc']

export default function SearchPanel({ onSearch, loading = false, compact = false }) {
  const [query, setQuery] = useState('')
  const [registrationNumber, setRegistrationNumber] = useState('')
  const [postalCode, setPostalCode] = useState('')

  const value = (legalName) => compact
    ? legalName
    : {
        legal_name: legalName,
        country_code: 'US',
        registration_number: registrationNumber.trim(),
        postal_code: postalCode.trim(),
      }

  const submit = (event) => {
    event.preventDefault()
    if (query.trim()) onSearch(value(query.trim()))
  }

  return (
    <section className={`search-panel ${compact ? 'search-compact' : ''}`}>
      <form className="search-form-grid" onSubmit={submit}>
        <div className="search-box">
          <Search size={18} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Legal company name"
            disabled={loading}
          />
          <button className="btn btn-primary" disabled={loading || !query.trim()}>
            {loading ? <Loader2 className="spin" size={16} /> : <Search size={16} />}
            Run
          </button>
        </div>
        {!compact && (
          <div className="identity-fields">
            <label>
              <span>Country</span>
              <select value="US" disabled aria-label="Country">
                <option value="US">United States</option>
              </select>
            </label>
            <label>
              <span>Registration number</span>
              <input
                value={registrationNumber}
                onChange={(event) => setRegistrationNumber(event.target.value)}
                placeholder="Optional"
                disabled={loading}
              />
            </label>
            <label>
              <span>Registered ZIP</span>
              <input
                value={postalCode}
                onChange={(event) => setPostalCode(event.target.value)}
                placeholder="Optional"
                disabled={loading}
              />
            </label>
          </div>
        )}
      </form>
      {!compact && (
        <div className="quick-set">
          {examples.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => onSearch({ legal_name: example, country_code: 'US', registration_number: '', postal_code: '' })}
              disabled={loading}
            >
              {example}
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
