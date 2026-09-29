import { BRAND } from '../../lib/brand'
import { ratingTone } from '../../lib/score'

const clamp = (value, low = 0, high = 1000) => Math.max(low, Math.min(high, Number(value) || 0))

export default function ScoreDial({ score = 0, rating, size = 164 }) {
  const isUnrated = !rating || ['Preliminary', 'Validation hold', 'Unrated'].includes(rating)
  const tone = ratingTone({ rating, private_score: score, scoring_status: isUnrated ? 'insufficient_data' : 'rated' })
  const normalized = isUnrated ? 0 : clamp(score)
  const radius = 58
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - normalized / 1000)

  return (
    <div className={`score-dial tone-${tone}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 160 160" role="img" aria-label={isUnrated ? 'Financial health rating unavailable' : `${BRAND.score} ${normalized} out of 1000`}>
        <circle cx="80" cy="80" r={radius} fill="none" stroke="var(--surface-dim)" strokeWidth="8" />
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 80 80)"
        />
        <text x="80" y="78" textAnchor="middle" className="dial-score">{isUnrated ? '—' : normalized}</text>
        <text x="80" y="100" textAnchor="middle" className="dial-label">{isUnrated ? 'Unrated' : (rating || 'Score')}</text>
      </svg>
    </div>
  )
}
