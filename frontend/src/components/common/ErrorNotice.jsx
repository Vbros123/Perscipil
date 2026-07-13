import { AlertTriangle } from 'lucide-react'

export default function ErrorNotice({ message }) {
  if (!message) return null
  return (
    <div className="notice notice-error">
      <AlertTriangle size={17} />
      <span>{message}</span>
    </div>
  )
}
