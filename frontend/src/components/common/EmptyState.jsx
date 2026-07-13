export default function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <section className="empty-state">
      {Icon && <div className="empty-icon"><Icon size={22} /></div>}
      <h2>{title}</h2>
      {children && <p>{children}</p>}
      {action && <div className="empty-action">{action}</div>}
    </section>
  )
}
