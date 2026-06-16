import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  UserPlus,
  UserX,
  Search,
  Clock,
  PanelLeftClose,
  PanelLeft,
} from 'lucide-react'
import { Logo } from '@/components/brand/Logo'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { UserMenu } from '@/components/layout/UserMenu'
import { cn } from '@/lib/cn'

const NAV: { to: string; label: string; icon: typeof LayoutDashboard; end?: boolean }[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/cadastrar', label: 'Cadastrar', icon: UserPlus },
  { to: '/inativar', label: 'Inativar', icon: UserX },
  { to: '/consultar', label: 'Consultar', icon: Search },
  { to: '/empresas-inativas', label: 'Empresas inativas', icon: Clock },
] 

type Props = {
  collapsed: boolean
  onToggleCollapse: () => void
  onNavigate?: () => void
  className?: string
}

export function Sidebar({ collapsed, onToggleCollapse, onNavigate, className }: Props) {
  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'flex h-full flex-col border-r border-border bg-avs-sidebar transition-[width] duration-300',
          collapsed ? 'w-[68px]' : 'w-64',
          className,
        )}
      >
        <div className={cn('flex items-center gap-2 p-4', collapsed && 'justify-center')}>
          <Logo size={collapsed ? 'sm' : 'md'} />
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-foreground">AVS Management</p>
              <p className="truncate text-xs text-muted-foreground">TiFlux · VHSYS</p>
            </div>
          )}
        </div>

        <Separator />

        <nav className="flex-1 space-y-1 p-2">
          {NAV.map(({ to, label, icon: Icon, end }) => {
            const link = (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                    collapsed && 'justify-center px-2',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <motion.span
                        layoutId="nav-indicator"
                        className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-full bg-brand-red"
                      />
                    )}
                    <Icon className="h-4 w-4 shrink-0" />
                    {!collapsed && <span>{label}</span>}
                  </>
                )}
              </NavLink>
            )

            if (collapsed) {
              return (
                <Tooltip key={to}>
                  <TooltipTrigger asChild>{link}</TooltipTrigger>
                  <TooltipContent side="right">{label}</TooltipContent>
                </Tooltip>
              )
            }
            return link
          })}
        </nav>

        <div className="border-t border-border p-2">
          <div className={cn('flex items-center gap-2', collapsed ? 'flex-col' : 'justify-between')}>
            {!collapsed && <UserMenu />}
            <Button variant="ghost" size="icon" onClick={onToggleCollapse} aria-label="Alternar sidebar">
              {collapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </aside>
    </TooltipProvider>
  )
}
