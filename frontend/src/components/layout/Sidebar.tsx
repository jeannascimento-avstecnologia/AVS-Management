import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  UserPlus,
  UserX,
  Search,
  Clock,
  PanelLeftClose,
  PanelLeft,
  LogOut,
  Shield,
} from 'lucide-react'
import { Logo } from '@/components/brand/Logo'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { SpotlightSelectable, type SpotlightAccent } from '@/components/ui/SpotlightSelectable'
import { useAuth } from '@/hooks/useAuth'
import type { PermissionKey } from '@/hooks/useAuth'
import { cn } from '@/lib/cn'

const NAV: {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
  permission?: PermissionKey
  accent: SpotlightAccent
}[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true, accent: 'accent' },
  { to: '/cadastrar', label: 'Cadastrar', icon: UserPlus, permission: 'cadastrar', accent: 'accent' },
  { to: '/inativar', label: 'Inativar', icon: UserX, permission: 'inativar', accent: 'red' },
  { to: '/consultar', label: 'Consultar', icon: Search, permission: 'consultar', accent: 'accent' },
  { to: '/empresas-inativas', label: 'Empresas inativas', icon: Clock, permission: 'empresas_inativas', accent: 'red' },
  { to: '/usuarios', label: 'Usuários', icon: Shield, permission: 'manage_users', accent: 'purple' },
]

const sidebarGhostBtnClass =
  'bg-transparent shadow-none ring-0 hover:!bg-transparent hover:shadow-none focus-visible:!bg-transparent focus-visible:ring-0'

function SidebarNavItem({
  to,
  label,
  icon: Icon,
  end,
  accent,
  collapsed,
  onNavigate,
}: {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
  accent: SpotlightAccent
  collapsed: boolean
  onNavigate?: () => void
}) {
  return (
    <NavLink to={to} end={end} onClick={onNavigate} title={collapsed ? label : undefined} className="block">
      {({ isActive }) => (
        <SpotlightSelectable
          accent={accent}
          selected={isActive}
          variant="sidebar"
          className={cn(
            'text-sm font-medium',
            isActive ? 'text-aurora-sidebar-fg' : 'text-aurora-sidebar-muted hover:text-aurora-sidebar-fg',
          )}
          innerClassName={cn(
            'flex items-center',
            collapsed ? 'justify-center px-2 py-2.5' : 'gap-3 px-3 py-2.5',
          )}
        >
          <Icon className="h-4 w-4 shrink-0" />
          {!collapsed && <span>{label}</span>}
        </SpotlightSelectable>
      )}
    </NavLink>
  )
}

type Props = {
  collapsed: boolean
  onToggleCollapse: () => void
  onNavigate?: () => void
  className?: string
}

export function Sidebar({ collapsed, onToggleCollapse, onNavigate, className }: Props) {
  const { logout, user } = useAuth()

  const navItems = NAV.filter((item) => {
    if (!item.permission) return true
    if (user?.dev_mode) return true
    return Boolean(user?.permissions?.[item.permission])
  })

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'aurora-sidebar-pattern relative flex h-full flex-col overflow-hidden border-r border-aurora-sidebar-border text-aurora-sidebar-fg transition-[width] duration-300',
          collapsed ? 'w-16' : 'w-64',
          className,
        )}
      >
        <div className={cn('relative z-10 flex flex-col items-center gap-1 p-4', collapsed && 'px-2')}>
          <Logo variant="sidebar" collapsed={collapsed} />
          {!collapsed && (
            <p className="text-xs text-aurora-sidebar-muted">TiFlux · VHSYS</p>
          )}
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onToggleCollapse}
                  aria-label="Expandir sidebar"
                  className={cn('w-full text-aurora-sidebar-muted hover:text-aurora-sidebar-fg', sidebarGhostBtnClass)}
                >
                  <PanelLeft className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Expandir sidebar</TooltipContent>
            </Tooltip>
          ) : (
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleCollapse}
              aria-label="Recolher sidebar"
              className="w-full text-aurora-sidebar-muted hover:bg-white/10 hover:text-aurora-sidebar-fg"
            >
              <PanelLeftClose className="h-4 w-4" />
            </Button>
          )}
        </div>

        <Separator className="relative z-10 bg-aurora-sidebar-border" />

        <nav className="relative z-10 flex-1 space-y-1 p-2">
          {navItems.map((item) => (
            <SidebarNavItem key={item.to} {...item} collapsed={collapsed} onNavigate={onNavigate} />
          ))}
        </nav>

        <div className="relative z-10 space-y-2 border-t border-aurora-sidebar-border p-2">
          {!collapsed && (
            <Button
              type="button"
              onClick={logout}
              className="w-full bg-aurora-brand-red font-semibold text-white hover:brightness-110"
            >
              <LogOut className="mr-2 h-4 w-4" />
              Sair
            </Button>
          )}
          {collapsed && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon"
                  onClick={logout}
                  aria-label="Sair"
                  className="w-full bg-aurora-brand-red text-white hover:brightness-110"
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Sair</TooltipContent>
            </Tooltip>
          )}
        </div>
      </aside>
    </TooltipProvider>
  )
}
