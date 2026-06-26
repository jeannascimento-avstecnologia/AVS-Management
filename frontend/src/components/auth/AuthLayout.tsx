import { Link } from 'react-router-dom'
import { Logo } from '@/components/brand/Logo'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { linkClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

export function AuthLayout({
  children,
  title,
  subtitle,
  tagline,
  showBackLink = true,
}: {
  children: React.ReactNode
  title: string
  subtitle?: string
  tagline?: string
  showBackLink?: boolean
}) {
  return (
    <div className="aurora-sidebar-pattern relative flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <Logo variant="auth" className={tagline ? 'mb-4' : 'mb-7'} />
      {tagline && (
        <p className="mb-7 max-w-sm text-center text-sm font-medium leading-relaxed text-white">
          {tagline}
        </p>
      )}
      <div className="hub-panel-enter w-full max-w-sm rounded-2xl border border-aurora-border bg-aurora-surface p-8 shadow-lg">
        <h2 className="text-xl font-bold tracking-tight text-aurora-fg">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-aurora-muted">{subtitle}</p>}
        <div className="mt-6">{children}</div>

        {showBackLink && (
          <p className="mt-6 text-center text-sm text-aurora-muted">
            <Link to="/login" className={cn(linkClass)}>
              Voltar ao login
            </Link>
          </p>
        )}
      </div>
      <div className="fixed bottom-4 right-4 z-10">
        <ThemeToggle />
      </div>
    </div>
  )
}
