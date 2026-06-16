import { useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  UserPlus,
  UserX,
  Search,
  Clock,
  LogOut,
  Moon,
  Sun,
  Monitor,
} from 'lucide-react'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command'
import { useCommandPalette } from '@/hooks/useCommandPalette'
import { useTheme } from '@/contexts/ThemeProvider'
import { useAuth } from '@/hooks/useAuth'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/cadastrar', label: 'Cadastrar cliente', icon: UserPlus },
  { to: '/inativar', label: 'Inativar cliente', icon: UserX },
  { to: '/consultar', label: 'Consultar status', icon: Search },
  { to: '/empresas-inativas', label: 'Empresas inativas', icon: Clock },
]

export function CommandPalette() {
  const { open, setOpen } = useCommandPalette()
  const navigate = useNavigate()
  const { setMode } = useTheme()
  const { logout } = useAuth()

  function go(path: string) {
    setOpen(false)
    navigate(path)
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Buscar páginas e ações…" />
      <CommandList>
        <CommandEmpty>Nenhum resultado.</CommandEmpty>
        <CommandGroup heading="Navegação">
          {NAV.map(({ to, label, icon: Icon }) => (
            <CommandItem key={to} onSelect={() => go(to)}>
              <Icon className="mr-2 h-4 w-4" />
              {label}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Ações rápidas">
          <CommandItem onSelect={() => go('/cadastrar')}>
            <UserPlus className="mr-2 h-4 w-4" />
            Cadastrar por CNPJ
          </CommandItem>
          <CommandItem onSelect={() => go('/consultar')}>
            <Search className="mr-2 h-4 w-4" />
            Consultar cliente
          </CommandItem>
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Preferências">
          <CommandItem onSelect={() => { setMode('light'); setOpen(false) }}>
            <Sun className="mr-2 h-4 w-4" />
            Tema claro
          </CommandItem>
          <CommandItem onSelect={() => { setMode('dark'); setOpen(false) }}>
            <Moon className="mr-2 h-4 w-4" />
            Tema escuro
          </CommandItem>
          <CommandItem onSelect={() => { setMode('system'); setOpen(false) }}>
            <Monitor className="mr-2 h-4 w-4" />
            Tema do sistema
          </CommandItem>
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Conta">
          <CommandItem onSelect={() => { setOpen(false); logout() }}>
            <LogOut className="mr-2 h-4 w-4" />
            Sair
          </CommandItem>
        </CommandGroup>
      </CommandList>
      <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
        <CommandShortcut>Esc</CommandShortcut> fechar · <CommandShortcut>Ctrl+K</CommandShortcut> abrir
      </div>
    </CommandDialog>
  )
}
