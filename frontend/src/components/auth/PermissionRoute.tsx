import { Navigate, useLocation } from 'react-router-dom'
import { toast } from 'sonner'
import { useEffect } from 'react'
import { useAuth, type PermissionKey } from '@/hooks/useAuth'

export function PermissionRoute({
  permission,
  children,
}: {
  permission: PermissionKey
  children: React.ReactNode
}) {
  const { user, loading } = useAuth()
  const location = useLocation()
  const allowed = Boolean(user?.dev_mode || user?.permissions?.[permission])

  useEffect(() => {
    if (!loading && user && !allowed) {
      toast.error('Sem permissão para acessar esta página.')
    }
  }, [loading, user, allowed])

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!allowed) {
    return <Navigate to="/" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
