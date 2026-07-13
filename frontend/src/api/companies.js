import { apiRequest } from './client'

export function getScore(company) {
  return apiRequest(`/api/score?company=${encodeURIComponent(company)}`)
}

export function compareCompanies(companies) {
  const value = Array.isArray(companies) ? companies.join(',') : companies
  return apiRequest(`/api/compare?companies=${encodeURIComponent(value)}`)
}

export function getHistory(limit = 25) {
  return apiRequest(`/api/history?limit=${limit}`)
}

export function clearHistory() {
  return apiRequest('/api/history', { method: 'DELETE' })
}

export function deleteHistoryItem(id) {
  return apiRequest(`/api/history/${id}`, { method: 'DELETE' })
}

export function getSignals() {
  return apiRequest('/api/signals')
}
