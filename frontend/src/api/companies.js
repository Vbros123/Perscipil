import { apiRequest } from './client'

export function getScore(company, identity = {}, refresh = false) {
  return apiRequest('/api/score', {
    method: 'POST',
    body: JSON.stringify({
      legal_name: company,
      country_code: identity.country_code || 'US',
      ...(identity.registration_number ? { registration_number: identity.registration_number } : {}),
      ...(identity.postal_code ? { postal_code: identity.postal_code } : {}),
      ...(identity.address ? { address: identity.address } : {}),
      ...(refresh ? { refresh: true } : {}),
    }),
  })
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
