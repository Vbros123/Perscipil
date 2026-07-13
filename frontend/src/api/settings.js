import { apiRequest } from './client'

export function getSettings() {
  return apiRequest('/api/settings')
}

export function updateSettings(payload) {
  return apiRequest('/api/settings', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}
