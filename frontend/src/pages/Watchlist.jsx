import { BookmarkCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { deleteWatchlistItem, listWatchlist } from '../api/watchlist'
import EmptyState from '../components/common/EmptyState'
import ErrorNotice from '../components/common/ErrorNotice'
import PageHeader from '../components/common/PageHeader'
import SearchPanel from '../components/dashboard/SearchPanel'
import WatchlistTable from '../components/watchlist/WatchlistTable'

export default function Watchlist() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const load = async () => {
    try {
      setItems(await listWatchlist())
    } catch (err) {
      setError(err.message || 'Unable to load watchlist.')
    }
  }

  useEffect(() => { load() }, [])

  const remove = async (id) => {
    try {
      await deleteWatchlistItem(id)
      setItems((current) => current.filter((item) => item.id !== id))
    } catch (err) {
      setError(err.message || 'Unable to remove company.')
    }
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Saved companies" title="Watchlist">
        Monitor companies you want to revisit after each score run.
      </PageHeader>
      <SearchPanel compact onSearch={(company) => navigate(`/reports/${encodeURIComponent(company)}`)} />
      <ErrorNotice message={error} />
      {items.length ? (
        <WatchlistTable items={items} onDelete={remove} />
      ) : (
        <EmptyState icon={BookmarkCheck} title="No saved companies">Save a company from any report to start a watchlist.</EmptyState>
      )}
    </div>
  )
}
