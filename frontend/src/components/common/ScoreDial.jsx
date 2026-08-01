const clamp = (value, low = 0, high = 1000) => Math.max(low, Math.min(high, Number(value) || 0))

export default function ScoreDial({ score = 0, rating, color = '#2dd4bf', size = 164 }) {
  const isUnrated = rating === 'Preliminary'
  const normalized = isUnrated ? 0 : clamp(score)
  const radius = 58
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - normalized / 1000)

  return (
    <div className="score-dial" style={{ width: size, height: size }}>
      <svg viewBox="0 0 160 160" role="img" aria-label={isUnrated ? 'Financial health rating unavailable' : `PrivateScore ${normalized} out of 1000`}>
        <circle cx="80" cy="80" r={radius} fill="none" stroke="rgba(148, 163, 184, 0.18)" strokeWidth="10" />
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="none"
          stroke={color}
          strokeLinecap="round"
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 80 80)"
        />
        <text x="80" y="76" textAnchor="middle" className="dial-score">{isUnrated ? 'N/A' : normalized}</text>
        <text x="80" y="98" textAnchor="middle" className="dial-label">{isUnrated ? 'Unrated' : (rating || 'Score')}</text>
      </svg>
    </div>
  )
}
