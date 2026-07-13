import { apiRequest } from './client'

export function listWatchlist() {
  return apiRequest('/api/watchlist')
}

export function addWatchlist(payload) {
  return apiRequest('/api/watchlist', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateWatchlistItem(id, payload) {
  return apiRequest(`/api/watchlist/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteWatchlistItem(id) {
  return apiRequest(`/api/watchlist/${id}`, { method: 'DELETE' })
}
