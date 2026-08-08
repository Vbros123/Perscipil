import { ScanSearch } from 'lucide-react'
import { Link } from '../router'

export default function NotFound() {
  return (
    <main className="not-found">
      <ScanSearch size={34} />
      <h1>Page not found</h1>
      <p>This route is not part of the PrivateLens workspace.</p>
      <Link className="btn btn-primary" to="/dashboard">Back to dashboard</Link>
    </main>
  )
}
