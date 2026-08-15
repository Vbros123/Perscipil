// Single source of truth for deciding whether a record carries a published
// PrivateScore. The API returns scoring_status; older rows may only carry a
// rating string, so both are checked rather than guessing from the number.

const UNRATED_RATINGS = new Set(['Preliminary', 'Validation hold', 'Unrated', 'Insufficient public evidence'])
const PUBLISHED_STATUSES = new Set(['rated', 'limited'])

export function isRated(item) {
  if (!item) return false
  if (item.scoring_status) return PUBLISHED_STATUSES.has(item.scoring_status)
  const nested = Number(item.score?.value)
  if (Number.isFinite(nested)) return true
  if (item.rating && UNRATED_RATINGS.has(item.rating)) return false
  return Number.isFinite(Number(item.private_score))
}

// Returns the score only when it is a real published number. `0` is a valid
// score, so presence is checked rather than truthiness.
export function displayScore(item, fallback = 'N/A') {
  if (!isRated(item)) return fallback
  const score = Number(item?.score?.value ?? item?.private_score)
  return Number.isFinite(score) ? score : fallback
}

export function displayRating(item, fallback = 'Unrated') {
  if (!isRated(item)) {
    if (item?.scoring_status === 'unrated' || item?.rating === 'Insufficient public evidence') {
      return 'Insufficient public evidence'
    }
    if (!item?.rating) return fallback
    return UNRATED_RATINGS.has(item.rating) ? 'Unrated' : fallback
  }
  if (item.scoring_status === 'limited') {
    return item.rating && !UNRATED_RATINGS.has(item.rating) ? item.rating : 'Limited coverage'
  }
  return item.rating || fallback
}

// Rating -> design-system tone. The API also ships a hex color per band, but
// those values were tuned for a dark theme and are not readable as text on the
// light UI, so presentation is owned here.
const RATING_TONES = {
  Exceptional: 'strong',
  Strong: 'strong',
  Adequate: 'steady',
  Weak: 'caution',
  Distressed: 'elevated',
  Critical: 'critical',
}

export function ratingTone(item) {
  if (!isRated(item)) return 'unrated'
  return RATING_TONES[item.rating] || 'steady'
}

export function averageScore(items) {
  const scores = (items || [])
    .filter(isRated)
    .map((item) => Number(item.score?.value ?? item.private_score))
    .filter(Number.isFinite)
  if (!scores.length) return null
  return Math.round(scores.reduce((sum, value) => sum + value, 0) / scores.length)
}
