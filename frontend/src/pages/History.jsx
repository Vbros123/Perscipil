import { History as HistoryIcon, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { clearHistory, deleteHistoryItem, getHistory } from '../api/companies'
import EmptyState from '../components/common/EmptyState'
import ErrorNotice from '../components/common/ErrorNotice'
import PageHeader from '../components/common/PageHeader'

function normalize(payload) {
  return Array.isArray(payload) ? payload : payload?.history || []
}

export default function History() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')

  const load = async () => {
    try {
      setItems(normalize(await getHistory(100)))
    } catch (err) {
      setError(err.message || 'Unable to load history.')
    }
  }

  useEffect(() => { load() }, [])

  const clear = async () => {
    try {
      await clearHistory()
      setItems([])
    } catch (err) {
      setError(err.message || 'Unable to clear history.')
    }
  }

  const remove = async (id) => {
    try {
      await deleteHistoryItem(id)
      setItems((current) => current.filter((item) => item.id !== id))
    } catch (err) {
      setError(err.message || 'Unable to remove history item.')
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Research trail"
        title="History"
        actions={items.length ? <button className="btn btn-ghost" onClick={clear}>Clear all</button> : null}
      >
        Company searches and compare runs saved to your account.
      </PageHeader>
      <ErrorNotice message={error} />
      {items.length ? (
        <div className="table-card">
          <table>
            <thead>
              <tr><th>Company</th><th>Score</th><th>Rating</th><th>Type</th><th /></tr>
            </thead>
            <tbody>
              {items.map((item, index) => (
                <tr key={item.id || `${item.company_name}-${index}`}>
                  <td><Link className="table-link" to={`/reports/${encodeURIComponent(item.company_name)}`}>{item.company_name}</Link></td>
                  <td className="mono" style={{ color: item.color }}>{item.rating === 'Preliminary' ? 'N/A' : item.private_score}</td>
                  <td>{item.rating === 'Preliminary' ? 'Unrated' : item.rating}</td>
                  <td className="muted">{item.query_type || 'score'}</td>
                  <td className="table-actions">
                    {item.id && (
                      <button className="icon-button" onClick={() => remove(item.id)} aria-label={`Remove ${item.company_name}`}>
                        <Trash2 size={15} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState icon={HistoryIcon} title="No history yet">Score a company to create your first saved report.</EmptyState>
      )}
    </div>
  )
}
