export default function StatusPill({ status = 'neutral', children }) {
  return (
    <span className={`status-pill status-${status}`}>
      <span aria-hidden="true" />
      {children}
    </span>
  )
}
