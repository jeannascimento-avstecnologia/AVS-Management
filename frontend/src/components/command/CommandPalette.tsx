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
  Shield,
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
import type { PermissionKey } from '@/hooks/useAuth'

const NAV: {
  to: string
  label: string
  icon: typeof LayoutDashboard
  permission?: PermissionKey
}[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/cadastrar', label: 'Cadastrar cliente', icon: UserPlus, permission: 'cadastrar' },
  { to: '/inativar', label: 'Inativar cliente', icon: UserX, permission: 'inativar' },
  { to: '/consultar', label: 'Consultar status', icon: Search, permission: 'consultar' },
  { to: '/empresas-inativas', label: 'Empresas inativas', icon: Clock, permission: 'empresas_inativas' },
  { to: '/usuarios', label: 'Gerenciar usuários', icon: Shield, permission: 'manage_users' },
]

export function CommandPalette() {
  const { open, setOpen } = useCommandPalette()
  const navigate = useNavigate()
  const { setMode } = useTheme()
  const { logout, user } = useAuth()

  const navItems = NAV.filter((item) => {
    if (!item.permission) return true
    if (user?.dev_mode) return true
    return Boolean(user?.permissions?.[item.permission])
  })

  function go(path: string) {
    setOpen(false)
    navigate(path)
  }

  const canCadastrar = user?.dev_mode || user?.permissions?.cadastrar
  const canConsultar = user?.dev_mode || user?.permissions?.consultar

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Buscar páginas e ações…" />
      <CommandList>
        <CommandEmpty>Nenhum resultado.</CommandEmpty>
        <CommandGroup heading="Navegação">
          {navItems.map(({ to, label, icon: Icon }) => (
            <CommandItem key={to} onSelect={() => go(to)}>
              <Icon className="mr-2 h-4 w-4" />
              {label}
            </CommandItem>
          ))}
        </CommandGroup>
        {(canCadastrar || canConsultar) && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Ações rápidas">
              {canCadastrar && (
                <CommandItem onSelect={() => go('/cadastrar')}>
                  <UserPlus className="mr-2 h-4 w-4" />
                  Cadastrar por CNPJ
                </CommandItem>
              )}
              {canConsultar && (
                <CommandItem onSelect={() => go('/consultar')}>
                  <Search className="mr-2 h-4 w-4" />
                  Consultar cliente
                </CommandItem>
              )}
            </CommandGroup>
          </>
        )}
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
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Conta">
          <CommandItem onSelect={() => { logout(); setOpen(false) }}>
            <LogOut className="mr-2 h-4 w-4" />
            Sair
            <CommandShortcut>⇧⌘Q</CommandShortcut>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
