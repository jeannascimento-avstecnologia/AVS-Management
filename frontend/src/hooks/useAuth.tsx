import { createContext, useContext, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api, refreshCsrfToken } from '../api/client'

export type PermissionKey =
  | 'cadastrar'
  | 'inativar'
  | 'consultar'
  | 'empresas_inativas'
  | 'manage_users'

export type UserPermissions = Record<PermissionKey, boolean>

export type User = {
  email: string
  name: string
  dev_mode?: boolean
  id?: number
  permissions?: Partial<UserPermissions>
}

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
      await refreshCsrfToken()
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

    let cancelled = false
    setLoading(true)

    ;(async () => {
      try {
        const r = await api.me()
        if (cancelled) return
        setUser(r.user)
        await refreshCsrfToken()
      } catch {
        if (!cancelled) setUser(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
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

export function usePermission(key: PermissionKey): boolean {
  const { user } = useAuth()
  if (!user) return false
  if (user.dev_mode) return true
  return Boolean(user.permissions?.[key])
}
