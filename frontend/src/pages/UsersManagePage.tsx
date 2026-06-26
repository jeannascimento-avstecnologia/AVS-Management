import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Mail, Plus, Search, Shield, Trash2, KeyRound } from 'lucide-react'
import { api, type PermissionKey, type UserPermissions } from '@/api/client'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { SpotlightSelectable } from '@/components/ui/SpotlightSelectable'
import { formatDate } from '@/lib/format'
import { btnPrimaryClass, inputClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

const PERMISSION_ORDER: PermissionKey[] = [
  'cadastrar',
  'inativar',
  'consultar',
  'empresas_inativas',
  'manage_users',
]

export function UsersManagePage() {
  const { user: currentUser } = useAuth()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState('users')
  const [createOpen, setCreateOpen] = useState(false)
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [newEmail, setNewEmail] = useState('')
  const [newName, setNewName] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [adminPassword, setAdminPassword] = useState('')
  const [permissionDraft, setPermissionDraft] = useState<UserPermissions | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  const usersQuery = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => api.adminListUsers(),
  })

  const auditQuery = useQuery({
    queryKey: ['admin-audit'],
    queryFn: () => api.adminAuditLog({ limit: 100 }),
  })

  const users = usersQuery.data?.users ?? []
  const labels = usersQuery.data?.permission_labels ?? {}
  const activeUsers = users.filter((u) => u.is_active)
  const filteredUsers = useMemo(() => {
    const q = searchTerm.trim().toLowerCase()
    if (!q) return activeUsers
    return activeUsers.filter(
      (u) => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q),
    )
  }, [activeUsers, searchTerm])
  const selected = activeUsers.find((u) => u.id === selectedId) ?? null

  useEffect(() => {
    if (selected?.permissions) {
      setPermissionDraft({ ...selected.permissions })
    } else {
      setPermissionDraft(null)
    }
  }, [selected?.id])

  const userAuditQuery = useQuery({
    queryKey: ['admin-audit-user', selected?.id],
    queryFn: () => api.adminUserAuditLog(selected!.id, { limit: 50 }),
    enabled: Boolean(selected?.id),
  })

  const createMutation = useMutation({
    mutationFn: () => api.adminCreateUser({ email: newEmail, name: newName, password: newPassword || undefined }),
    onSuccess: (created) => {
      toast.success('Usuário criado')
      if (created.temporary_password) {
        toast.message(`Senha temporária: ${created.temporary_password}`, { duration: 12000 })
      }
      setCreateOpen(false)
      setNewEmail('')
      setNewName('')
      setNewPassword('')
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setSelectedId(created.id)
      setActiveTab('permissions')
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao criar usuário'),
  })

  const permissionsMutation = useMutation({
    mutationFn: ({ id, permissions }: { id: number; permissions: UserPermissions }) =>
      api.adminUpdatePermissions(id, permissions),
    onSuccess: (data) => {
      toast.success('Permissões atualizadas')
      setPermissionDraft({ ...data.permissions })
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao salvar permissões'),
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: number) => api.adminDeactivateUser(id),
    onSuccess: () => {
      toast.success('Usuário inativado')
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao inativar'),
  })

  const passwordMutation = useMutation({
    mutationFn: () => api.adminSetPassword(selected!.id, adminPassword),
    onSuccess: () => {
      toast.success('Senha definida')
      setPasswordOpen(false)
      setAdminPassword('')
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao definir senha'),
  })

  const resetEmailMutation = useMutation({
    mutationFn: (id: number) => api.adminSendResetEmail(id),
    onSuccess: (res) => toast.success(res.message),
    onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao enviar e-mail'),
  })

  const hasPermissionChanges = useMemo(() => {
    if (!selected?.permissions || !permissionDraft) return false
    return PERMISSION_ORDER.some((key) => permissionDraft[key] !== selected.permissions[key])
  }, [permissionDraft, selected?.permissions])

  function updatePermission(key: PermissionKey, enabled: boolean) {
    setPermissionDraft((prev) => (prev ? { ...prev, [key]: enabled } : prev))
  }

  function savePermissions() {
    if (!selected || !permissionDraft) return
    permissionsMutation.mutate({ id: selected.id, permissions: permissionDraft })
  }

  function openUserPermissions(userId: number) {
    setSelectedId(userId)
    setActiveTab('permissions')
  }

  function handleSearch(e?: FormEvent) {
    e?.preventDefault()
    setSearchTerm(searchInput.trim())
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-lg bg-aurora-purple/15 px-3 py-1.5 text-aurora-purple">
            <Shield className="h-4 w-4" />
            <span className="text-sm font-semibold uppercase tracking-wide">Administração</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Gerenciar usuários</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Contas, permissões por módulo e trilha de auditoria.
          </p>
        </div>

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button className={btnPrimaryClass}>
              <Plus className="h-4 w-4" />
              Novo usuário
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Adicionar usuário</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label htmlFor="new-email">E-mail</Label>
                <Input id="new-email" className={inputClass} value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="new-name">Nome</Label>
                <Input id="new-name" className={inputClass} value={newName} onChange={(e) => setNewName(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="new-password">Senha (opcional)</Label>
                <Input
                  id="new-password"
                  type="password"
                  className={inputClass}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Gerada automaticamente se vazio"
                />
              </div>
              <Button
                className={btnPrimaryClass}
                disabled={!newEmail.trim() || !newName.trim() || createMutation.isPending}
                onClick={() => createMutation.mutate()}
              >
                Criar
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="users">Usuários</TabsTrigger>
          <TabsTrigger value="permissions">Permissões</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="mt-4">
          <Card>
            <CardHeader className="space-y-4">
              <CardTitle className="text-base">Usuários ativos</CardTitle>
              <form onSubmit={handleSearch} className="flex flex-wrap gap-2">
                <Input
                  className={cn(inputClass, 'max-w-md flex-1')}
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="Buscar por nome ou e-mail…"
                  aria-label="Buscar usuário"
                />
                <Button
                  type="submit"
                  className="aurora-motion inline-flex items-center gap-2 rounded-lg bg-aurora-purple px-4 py-2 text-sm font-semibold text-white shadow-sm hover:brightness-110"
                >
                  <Search className="h-4 w-4" />
                  Pesquisar
                </Button>
                {searchTerm && (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setSearchInput('')
                      setSearchTerm('')
                    }}
                  >
                    Limpar
                  </Button>
                )}
              </form>
            </CardHeader>
            <CardContent className="space-y-2">
              {usersQuery.isPending && <p className="text-sm text-muted-foreground">Carregando…</p>}
              {filteredUsers.map((u) => (
                <SpotlightSelectable
                  key={u.id}
                  accent="purple"
                  selected={selectedId === u.id}
                  onClick={() => setSelectedId(u.id)}
                  className="cursor-pointer p-3"
                  innerClassName="flex flex-wrap items-center justify-between gap-3"
                >
                  <div>
                    <p className="font-medium">{u.name}</p>
                    <p className="text-sm text-muted-foreground">{u.email}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        openUserPermissions(u.id)
                      }}
                    >
                      Permissões
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        resetEmailMutation.mutate(u.id)
                      }}
                      disabled={resetEmailMutation.isPending}
                    >
                      <Mail className="h-3.5 w-3.5" />
                      Reset e-mail
                    </Button>
                    {u.id !== currentUser?.id && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-destructive"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (window.confirm(`Inativar ${u.email}?`)) deactivateMutation.mutate(u.id)
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Excluir
                      </Button>
                    )}
                  </div>
                </SpotlightSelectable>
              ))}
              {!usersQuery.isPending && activeUsers.length === 0 && (
                <p className="text-sm text-muted-foreground">Nenhum usuário ativo.</p>
              )}
              {!usersQuery.isPending && activeUsers.length > 0 && filteredUsers.length === 0 && (
                <p className="text-sm text-muted-foreground">Nenhum usuário encontrado para &quot;{searchTerm}&quot;.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="permissions" className="mt-4">
          {!selected ? (
            <p className="text-sm text-muted-foreground">Selecione um usuário na aba Usuários.</p>
          ) : (
            <Card>
              <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">{selected.name}</CardTitle>
                  <p className="text-sm text-muted-foreground">{selected.email}</p>
                </div>
                <Dialog open={passwordOpen} onOpenChange={setPasswordOpen}>
                  <DialogTrigger asChild>
                    <Button variant="outline" size="sm">
                      <KeyRound className="h-3.5 w-3.5" />
                      Definir senha
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Nova senha — {selected.email}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                      <Input
                        type="password"
                        className={inputClass}
                        value={adminPassword}
                        onChange={(e) => setAdminPassword(e.target.value)}
                      />
                      <Button
                        className={btnPrimaryClass}
                        disabled={!adminPassword || passwordMutation.isPending}
                        onClick={() => passwordMutation.mutate()}
                      >
                        Salvar senha
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent className="space-y-4">
                {PERMISSION_ORDER.map((key) => (
                  <div key={key} className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-aurora-border p-4">
                    <div>
                      <p className="font-medium">{labels[key] || key}</p>
                      <p className="text-xs text-muted-foreground">Pode acessar &quot;{labels[key] || key}&quot;?</p>
                    </div>
                    <RadioGroup
                      value={permissionDraft?.[key] ? 'yes' : 'no'}
                      onValueChange={(v) => updatePermission(key, v === 'yes')}
                      className="flex flex-row gap-4"
                      disabled={permissionsMutation.isPending}
                    >
                      <label className="flex items-center gap-2 text-sm">
                        <RadioGroupItem value="yes" id={`${key}-yes`} />
                        Sim
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <RadioGroupItem value="no" id={`${key}-no`} />
                        Não
                      </label>
                    </RadioGroup>
                  </div>
                ))}
                <div className="flex flex-wrap items-center justify-end gap-3 border-t border-aurora-border pt-4">
                  {hasPermissionChanges && (
                    <p className="mr-auto text-xs text-muted-foreground">Alterações não salvas</p>
                  )}
                  <Button
                    className={btnPrimaryClass}
                    disabled={!hasPermissionChanges || permissionsMutation.isPending}
                    onClick={savePermissions}
                  >
                    {permissionsMutation.isPending ? 'Salvando…' : 'Salvar permissões'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="logs" className="mt-4 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Log geral</CardTitle>
            </CardHeader>
            <CardContent>
              <AuditList entries={auditQuery.data?.entries ?? []} loading={auditQuery.isPending} />
            </CardContent>
          </Card>

          {selected && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Log — {selected.email}</CardTitle>
              </CardHeader>
              <CardContent>
                <AuditList entries={userAuditQuery.data?.entries ?? []} loading={userAuditQuery.isPending} />
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function AuditList({
  entries,
  loading,
}: {
  entries: Array<{
    id: number
    user_email: string
    action: string
    resource: string
    created_at: string
    detail: Record<string, unknown>
  }>
  loading: boolean
}) {
  if (loading) return <p className="text-sm text-muted-foreground">Carregando…</p>
  if (entries.length === 0) return <p className="text-sm text-muted-foreground">Nenhum registro.</p>

  return (
    <ul className="space-y-2">
      {entries.map((entry) => (
        <li key={entry.id} className="rounded-lg border border-aurora-border p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{entry.action}</Badge>
            <span className="text-muted-foreground">{formatDate(entry.created_at)}</span>
          </div>
          <p className="mt-1">
            <span className="font-medium">{entry.user_email || '—'}</span>
            {' · '}
            {entry.resource}
          </p>
        </li>
      ))}
    </ul>
  )
}
