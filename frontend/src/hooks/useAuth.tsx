import { createContext, useContext, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../api/client'

type User = { email: string; name: string; dev_mode?: boolean; id?: number }

type AuthCtx = {
  user: User | null
  loading: boolean
  logout: () => void
  refresh: () => Promise<User | null>
}

const Ctx = createContext<AuthCtx>({
  user: null,
  loading: true,
  logout: () => {},
  refresh: async () => null,
})

const PUBLIC_PATHS = ['/login', '/login/forgot', '/login/reset']

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const isPublic = PUBLIC_PATHS.some((p) => location.pathname === p || location.pathname.startsWith(`${p}/`))

  async function refresh() {
    try {
      const r = await api.me()
      setUser(r.user)
      return r.user
    } catch {
      setUser(null)
      throw new Error('Não autenticado.')
    }
  }

  useEffect(() => {
    if (isPublic) {
      setLoading(false)
      return
    }
    setLoading(true)
    api.me()
      .then((r) => setUser(r.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [isPublic, location.pathname])

  const logout = () => { window.location.href = '/auth/logout' }

  return (
    <Ctx.Provider value={{ user, loading, logout, refresh }}>
      {children}
    </Ctx.Provider>
  )
}

export function useAuth() {
  return useContext(Ctx)
}
