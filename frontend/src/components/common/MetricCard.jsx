export default function MetricCard({ icon: Icon, label, value, detail }) {
  return (
    <article className="metric-card">
      <div className="metric-label">
        {Icon && <Icon size={13} strokeWidth={2.2} />}
        {label}
      </div>
      <div className="metric-value" title={typeof value === 'string' ? value : undefined}>{value}</div>
      {detail && <div className="metric-detail">{detail}</div>}
    </article>
  )
}
