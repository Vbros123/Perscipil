import { Loader2, Search } from 'lucide-react'
import { useState } from 'react'

const examples = ['Cargill', 'Deloitte', 'Bechtel', 'Mars Inc']

export default function SearchPanel({ onSearch, loading = false, compact = false }) {
  const [query, setQuery] = useState('')

  const submit = (event) => {
    event.preventDefault()
    if (query.trim()) onSearch(query.trim())
  }

  return (
    <section className={`search-panel ${compact ? 'search-compact' : ''}`}>
      <form className="search-box" onSubmit={submit}>
        <Search size={18} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search private company"
          disabled={loading}
        />
        <button className="btn btn-primary" disabled={loading || !query.trim()}>
          {loading ? <Loader2 className="spin" size={16} /> : <Search size={16} />}
          Run
        </button>
      </form>
      {!compact && (
        <div className="quick-set">
          {examples.map((example) => (
            <button key={example} type="button" onClick={() => onSearch(example)} disabled={loading}>
              {example}
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
