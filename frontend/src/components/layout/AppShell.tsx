import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Menu, X, LayoutDashboard, UserPlus, UserX, Search, Clock, LogOut } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../../hooks/useAuth'
import { cn } from '../../lib/cn'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/cadastrar', label: 'Cadastrar', icon: UserPlus },
  { to: '/inativar', label: 'Inativar', icon: UserX },
  { to: '/consultar', label: 'Consultar', icon: Search },
  { to: '/empresas-inativas', label: 'Empresas inativas', icon: Clock },
]

const LOGO_SRC = '/logo-avs.png'

export function AppShell() {
  const [open, setOpen] = useState(false)
  const [desktopOpen, setDesktopOpen] = useState(true)
  const { user, logout } = useAuth()

  function toggleSidebar() {
    if (window.matchMedia('(min-width: 1024px)').matches) {
      setDesktopOpen((v) => !v)
    } else {
      setOpen((v) => !v)
    }
  }

  const sidebar = (
    <aside className="flex h-full flex-col p-4">
      <div className="mb-6 px-2">
        <p className="font-display text-lg font-bold text-avs-navy">Menu</p>
        <p className="text-xs text-slate-500">TiFlux · VHSYS · BrasilAPI</p>
      </div>
      <nav className="flex flex-1 flex-col gap-1">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition',
                isActive
                  ? 'bg-gradient-to-r from-avs-blue to-avs-accent text-white shadow-md'
                  : 'text-slate-600 hover:bg-white/80',
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto rounded-xl border border-slate-200 bg-white/80 p-3 text-sm">
        <p className="font-medium text-slate-800">{user?.name}</p>
        <p className="truncate text-xs text-slate-500">{user?.email}</p>
        <button onClick={logout} className="mt-2 flex items-center gap-1 text-xs text-red-600 hover:underline">
          <LogOut className="h-3 w-3" /> Sair
        </button>
      </div>
    </aside>
  )

  return (
    <div className={cn('min-h-screen', desktopOpen ? 'lg:grid lg:grid-cols-[260px_1fr]' : 'lg:block')}>
      {desktopOpen && (
        <div className="hidden lg:block glass border-r border-white/60">{sidebar}</div>
      )}

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-slate-900/40 lg:hidden"
            onClick={() => setOpen(false)}
          >
            <motion.div
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              className="h-full w-[260px] glass"
              onClick={(e) => e.stopPropagation()}
            >
              {sidebar}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex min-h-screen flex-col">
        <header className="glass sticky top-0 z-30 grid grid-cols-[auto_1fr_auto] items-center border-b border-white/60 px-4 py-3 lg:px-8">
          <button
            type="button"
            className="flex items-center gap-2 rounded-xl p-1.5 transition hover:bg-white/70"
            onClick={toggleSidebar}
            aria-label="Abrir menu"
          >
            <img src={LOGO_SRC} alt="AVS" className="h-10 w-10 rounded-lg object-contain" />
            <span className="sr-only">Menu</span>
            <span className="rounded-lg p-1.5 text-avs-navy lg:hidden">
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </span>
          </button>

          <div className="pointer-events-none flex justify-center">
            <h1 className="brand-title">AVS MANAGEMENT</h1>
          </div>

          <div className="hidden text-right text-xs text-slate-500 sm:block">
            Gestão integrada
          </div>
        </header>
        <main className="flex-1 p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
