import { Menu, Search } from 'lucide-react'
import { Breadcrumbs } from '@/components/layout/Breadcrumbs'
import { BrandTitle } from '@/components/brand/BrandTitle'
import { UserMenu } from '@/components/layout/UserMenu'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { Button } from '@/components/ui/button'
import { useCommandPalette } from '@/hooks/useCommandPalette'

type Props = {
  onMenuClick: () => void
  showMenuButton?: boolean
}

export function Topbar({ onMenuClick, showMenuButton }: Props) {
  const { setOpen } = useCommandPalette()

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-avs-header/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-avs-header/80 lg:h-20 lg:px-6 relative">
      {showMenuButton && (
        <Button variant="ghost" size="icon" onClick={onMenuClick} aria-label="Abrir menu">
          <Menu className="h-5 w-5" />
        </Button>
      )}

      <Breadcrumbs className="hidden min-w-0 flex-1 xl:flex" />
      <div className="pointer-events-none absolute left-1/2 -translate-x-1/2">
        <BrandTitle size="lg" className="text-2xl lg:text-4xl" />
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          className="hidden h-8 gap-2 text-muted-foreground sm:flex"
          onClick={() => setOpen(true)}
        >
          <Search className="h-3.5 w-3.5" />
          <span className="text-xs">Buscar…</span>
          <kbd className="pointer-events-none ml-2 hidden rounded border border-border bg-muted px-1.5 font-mono text-[10px] lg:inline">
            Ctrl+K
          </kbd>
        </Button>
        <Button variant="ghost" size="icon" className="sm:hidden" onClick={() => setOpen(true)} aria-label="Buscar">
          <Search className="h-4 w-4" />
        </Button>
        <ThemeToggle />
        <div className="hidden lg:block">
          <UserMenu />
        </div>
      </div>
    </header>
  )
}
