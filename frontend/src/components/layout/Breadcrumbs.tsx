import { useLocation, Link } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'
import { cn } from '@/lib/cn'

const LABELS: Record<string, string> = {
  '/': 'Dashboard',
  '/cadastrar': 'Cadastrar',
  '/inativar': 'Inativar',
  '/consultar': 'Consultar',
  '/empresas-inativas': 'Empresas inativas',
}

export function Breadcrumbs({ className }: { className?: string }) {
  const { pathname } = useLocation()
  const label = LABELS[pathname] || 'Página'

  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center gap-1 text-sm text-muted-foreground', className)}>
      <Link to="/" className="flex items-center gap-1 transition-colors hover:text-foreground">
        <Home className="h-3.5 w-3.5" />
        <span className="sr-only sm:not-sr-only">Início</span>
      </Link>
      {pathname !== '/' && (
        <>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="font-medium text-foreground">{label}</span>
        </>
      )}
    </nav>
  )
}
