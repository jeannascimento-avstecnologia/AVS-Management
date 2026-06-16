import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Sidebar } from '@/components/layout/Sidebar'
import { Topbar } from '@/components/layout/Topbar'
import { CommandPalette } from '@/components/command/CommandPalette'
import { Sheet, SheetContent } from '@/components/ui/sheet'
import { useShortcuts } from '@/hooks/useShortcuts'
import { cn } from '@/lib/cn'

const SIDEBAR_KEY = 'avs-sidebar-collapsed'

export function AppShell() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) === '1')
  const [mobileOpen, setMobileOpen] = useState(false)

  useShortcuts()
  const location = useLocation()

  function toggleCollapse() {
    setCollapsed((v) => {
      const next = !v
      localStorage.setItem(SIDEBAR_KEY, next ? '1' : '0')
      return next
    })
  }

  return (
    <div className="flex min-h-screen bg-background">
      <div className="hidden lg:block">
        <Sidebar collapsed={collapsed} onToggleCollapse={toggleCollapse} className="fixed inset-y-0 left-0 z-40" />
      </div>

      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-64 p-0">
          <Sidebar
            collapsed={false}
            onToggleCollapse={() => setMobileOpen(false)}
            onNavigate={() => setMobileOpen(false)}
            className="h-full w-full border-0"
          />
        </SheetContent>
      </Sheet>

      <div
        className={cn(
          'flex min-h-screen flex-1 flex-col transition-[margin] duration-300',
          collapsed ? 'lg:ml-[68px]' : 'lg:ml-64',
        )}
      >
        <Topbar onMenuClick={() => setMobileOpen(true)} showMenuButton />
        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="flex-1 p-4 md:p-6 lg:p-8"
        >
          <Outlet />
        </motion.main>
      </div>

      <CommandPalette />
    </div>
  )
}
