export default function MetricCard({ icon: Icon, label, value, detail, tone = 'neutral' }) {
  return (
    <article className={`metric-card tone-${tone}`}>
      {Icon && <div className="metric-icon"><Icon size={18} /></div>}
      <div>
        <div className="metric-label">{label}</div>
        <div className="metric-value">{value}</div>
        {detail && <div className="metric-detail">{detail}</div>}
      </div>
    </article>
  )
}
