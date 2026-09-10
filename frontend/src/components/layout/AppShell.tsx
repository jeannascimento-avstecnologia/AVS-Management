import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { Topbar } from '@/components/layout/Topbar'
import { CommandPalette } from '@/components/command/CommandPalette'
import { DebugReportProvider } from '@/features/debug-report/DebugReportProvider'
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
    <DebugReportProvider app="avs-management">
      <div className="flex min-h-screen bg-aurora-bg">
        <div className="hidden lg:block">
          <Sidebar collapsed={collapsed} onToggleCollapse={toggleCollapse} className="fixed inset-y-0 left-0 z-40" />
        </div>

        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="left" className="w-64 border-0 bg-transparent p-0 shadow-none [&>button]:text-white">
            <Sidebar
              collapsed={false}
              onToggleCollapse={() => setMobileOpen(false)}
              onNavigate={() => setMobileOpen(false)}
              className="h-full w-full"
            />
          </SheetContent>
        </Sheet>

        <div
          className={cn(
            'flex min-h-screen flex-1 flex-col transition-[margin] duration-300',
            collapsed ? 'lg:ml-16' : 'lg:ml-64',
          )}
        >
          <Topbar onMenuClick={() => setMobileOpen(true)} showMenuButton />
          <main key={location.pathname} className="hub-panel-enter flex-1 p-4 md:p-6">
            <Outlet />
          </main>
        </div>

        <CommandPalette />
      </div>
    </DebugReportProvider>
  )
}
