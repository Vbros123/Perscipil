export const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

let accessToken = null
// Remove legacy persistent credentials. New bearer sessions last only in memory.
localStorage.removeItem('privatelens.token')
export function getToken() { return accessToken }

export function setToken(token) { accessToken = token || null }

export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {})
  const isFormData = options.body instanceof FormData
  const token = getToken()

  if (!headers.has('Content-Type') && options.body && !isFormData) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  })

  if (response.status === 204) {
    return null
  }

  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await response.json() : await response.text()

  if (!response.ok) {
    const message = typeof payload === 'string' ? payload : payload?.detail || 'Perscipil API request failed.'
    if (response.status === 401) {
      setToken(null)
      window.dispatchEvent(new CustomEvent('privatelens:session-expired'))
    }
    throw new ApiError(message, response.status, payload)
  }

  return payload
}
