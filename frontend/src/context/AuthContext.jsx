import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import * as authApi from '../api/auth'
import { getToken, setToken } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => getToken())
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getToken()))
  const [flashMessage, setFlashMessage] = useState('')

  const persistSession = useCallback((session) => {
    setToken(session.access_token)
    setTokenState(session.access_token)
    setUser(session.user)
    setFlashMessage('')
  }, [])

  const refreshUser = useCallback(async () => {
    if (!getToken()) {
      setLoading(false)
      return null
    }
    try {
      const nextUser = await authApi.getMe()
      setUser(nextUser)
      return nextUser
    } catch {
      setToken(null)
      setTokenState(null)
      setUser(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  useEffect(() => {
    const expire = () => {
      setToken(null)
      setTokenState(null)
      setUser(null)
    }
    window.addEventListener('privatelens:session-expired', expire)
    return () => window.removeEventListener('privatelens:session-expired', expire)
  }, [])

  const signup = useCallback(async (payload) => {
    const session = await authApi.signup(payload)
    persistSession(session)
    return session.user
  }, [persistSession])

  const login = useCallback(async (payload) => {
    const session = await authApi.login(payload)
    persistSession(session)
    return session.user
  }, [persistSession])

  const logout = useCallback(async (remote = true) => {
    if (remote) {
      try {
        if (getToken()) await authApi.logout()
      } catch {
        // Local logout still wins if the network is gone or the token is already invalid.
      }
    }
    setToken(null)
    setTokenState(null)
    setUser(null)
  }, [])

  const updateUser = useCallback(async (payload) => {
    const nextUser = await authApi.updateMe(payload)
    setUser(nextUser)
    return nextUser
  }, [])

  const value = useMemo(() => ({
    token,
    user,
    loading,
    isAuthenticated: Boolean(token && user),
    signup,
    login,
    logout,
    refreshUser,
    updateUser,
    flashMessage,
    showFlashMessage: setFlashMessage,
  }), [token, user, loading, signup, login, logout, refreshUser, updateUser, flashMessage])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) {
    throw new Error('useAuth must be used inside AuthProvider.')
  }
  return value
}
