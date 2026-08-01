import { ExternalLink, Trash2 } from 'lucide-react'
import { Link } from '../../router'

import Badge from '../common/Badge'

export default function WatchlistTable({ items, onDelete }) {
  return (
    <div className="table-card">
      <table>
        <thead>
          <tr>
            <th>Company</th>
            <th>Score</th>
            <th>Rating</th>
            <th>Notes</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const unrated = ['Preliminary', 'Validation hold', 'Unrated'].includes(item.rating)
            return (
            <tr key={item.id}>
              <td>
                <Link className="table-link" to={`/reports/${encodeURIComponent(item.company_name)}`}>
                  {item.company_name}
                  <ExternalLink size={13} />
                </Link>
              </td>
              <td className="mono">{unrated ? 'N/A' : (item.private_score || '-')}</td>
              <td>{item.rating ? <Badge tone="accent">{unrated ? 'Unrated' : item.rating}</Badge> : '-'}</td>
              <td className="muted">{item.notes || 'No notes'}</td>
              <td className="table-actions">
                <button className="icon-button" onClick={() => onDelete(item.id)} aria-label={`Remove ${item.company_name}`}>
                  <Trash2 size={15} />
                </button>
              </td>
            </tr>
          )})}
        </tbody>
      </table>
    </div>
  )
}
