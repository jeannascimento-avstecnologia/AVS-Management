import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../api/client'

type User = { email: string; name: string; dev_mode?: boolean }

type AuthCtx = {
  user: User | null
  loading: boolean
  logout: () => void
}

const Ctx = createContext<AuthCtx>({ user: null, loading: true, logout: () => {} })

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.me()
      .then((r) => setUser(r.user))
      .catch(() => { window.location.href = '/auth/login' })
      .finally(() => setLoading(false))
  }, [])

  const logout = () => { window.location.href = '/auth/logout' }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
      </div>
    )
  }

  return <Ctx.Provider value={{ user, loading, logout }}>{children}</Ctx.Provider>
}

export function useAuth() {
  return useContext(Ctx)
}
