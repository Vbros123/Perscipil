import { apiRequest } from './client'

export function signup(payload) {
  return apiRequest('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function login(payload) {
  return apiRequest('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getMe() {
  return apiRequest('/api/auth/me')
}

export function updateMe(payload) {
  return apiRequest('/api/users/me', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}
