import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, clearToken, getToken, setToken } from './api'
import type { User } from './types'

type AuthState = {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, fullName: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    api
      .me()
      .then(setUser)
      .catch(() => {
        clearToken()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      async login(email, password) {
        const token = await api.login(email, password)
        setToken(token.access_token)
        setUser(await api.me())
      },
      async register(email, fullName, password) {
        await api.register({ email, full_name: fullName, password })
        const token = await api.login(email, password)
        setToken(token.access_token)
        setUser(await api.me())
      },
      logout() {
        clearToken()
        setUser(null)
      },
    }),
    [user, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return value
}
