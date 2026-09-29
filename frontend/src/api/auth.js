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

export function logout() {
  return apiRequest('/api/auth/logout', { method: 'POST' })
}

export function getMe() {
  // A sleeping/unreachable API must not keep public auth pages loading forever.
  return apiRequest('/api/auth/me', { signal: AbortSignal.timeout(15000) })
}

export function updateMe(payload) {
  return apiRequest('/api/users/me', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function requestPasswordReset(payload) {
  return apiRequest('/api/auth/request-password-reset', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function resetPassword(payload) {
  return apiRequest('/api/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function changePassword(payload) {
  return apiRequest('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function requestEmailVerification() {
  return apiRequest('/api/auth/request-email-verification', { method: 'POST' })
}

export function verifyEmail(payload) {
  return apiRequest('/api/auth/verify-email', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
