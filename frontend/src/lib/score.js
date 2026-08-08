// Single source of truth for deciding whether a record carries a published
// PrivateScore. The API returns scoring_status; older rows may only carry a
// rating string, so both are checked rather than guessing from the number.

const UNRATED_RATINGS = new Set(['Preliminary', 'Validation hold', 'Unrated'])

export function isRated(item) {
  if (!item) return false
  if (item.scoring_status) return item.scoring_status === 'rated'
  if (item.rating && UNRATED_RATINGS.has(item.rating)) return false
  return Number.isFinite(Number(item.private_score))
}

// Returns the score only when it is a real published number. `0` is a valid
// score, so presence is checked rather than truthiness.
export function displayScore(item, fallback = 'N/A') {
  if (!isRated(item)) return fallback
  const score = Number(item?.private_score)
  return Number.isFinite(score) ? score : fallback
}

export function displayRating(item, fallback = 'Unrated') {
  if (!item?.rating) return fallback
  return UNRATED_RATINGS.has(item.rating) ? 'Unrated' : item.rating
}

export function averageScore(items) {
  const scores = (items || [])
    .filter(isRated)
    .map((item) => Number(item.private_score))
    .filter(Number.isFinite)
  if (!scores.length) return null
  return Math.round(scores.reduce((sum, value) => sum + value, 0) / scores.length)
}
