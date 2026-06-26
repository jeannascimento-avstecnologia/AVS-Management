import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { ActionCard } from '@/components/ui/ActionCard'
import { StatTile } from '@/components/data/StatTile'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { api } from '@/api/client'
import { formatDate } from '@/lib/format'
import { UserPlus, UserX, Search, Clock, Users, Database, BarChart3, AlertCircle, Shield } from 'lucide-react'
import type { PermissionKey } from '@/hooks/useAuth'

const cards: {
  to: string
  title: string
  desc: string
  icon: typeof UserPlus
  accent: 'accent' | 'red' | 'purple'
  permission: PermissionKey
}[] = [
  {
    to: '/cadastrar',
    title: 'Cadastrar cliente',
    desc: 'CNPJ, revisão e integração TiFlux + VHSYS',
    icon: UserPlus,
    accent: 'accent',
    permission: 'cadastrar',
  },
  {
    to: '/inativar',
    title: 'Inativar cliente',
    desc: 'Inativação no TiFlux por CNPJ ou nome',
    icon: UserX,
    accent: 'red',
    permission: 'inativar',
  },
  {
    to: '/consultar',
    title: 'Consultar status',
    desc: 'Relatório completo do cadastro nos sistemas',
    icon: Search,
    accent: 'accent',
    permission: 'consultar',
  },
  {
    to: '/empresas-inativas',
    title: 'Empresas sem atividade',
    desc: 'Sem ticket ou cobrança nos últimos 24 meses',
    icon: Clock,
    accent: 'red',
    permission: 'empresas_inativas',
  },
  {
    to: '/usuarios',
    title: 'Gerenciar usuários',
    desc: 'Permissões, contas e auditoria de acessos',
    icon: Shield,
    accent: 'purple',
    permission: 'manage_users',
  },
]

function isStatsStale(computedAt: string | undefined, staleAfterSeconds: number | undefined): boolean {
  if (!computedAt || !staleAfterSeconds) return false
  const ageMs = Date.now() - new Date(computedAt).getTime()
  return ageMs > staleAfterSeconds * 1000
}

export function Dashboard() {
  const { user } = useAuth()
  const firstName = user?.name?.split(/\s+/)[0] || 'usuário'

  const visibleCards = cards.filter((c) => {
    if (user?.dev_mode) return true
    return Boolean(user?.permissions?.[c.permission])
  })

  const {
    data: stats,
    isPending: statsPending,
    isError: statsError,
    error: statsErr,
    isFetching,
  } = useQuery({
    queryKey: ['stats'],
    queryFn: () => api.stats(),
    staleTime: 5 * 60 * 1000,
    refetchInterval: (query) =>
      query.state.data?.dormant_status === 'pending' ? 15_000 : false,
  })

  const stale = isStatsStale(stats?.computed_at, stats?.stale_after_seconds)
  const dormantPending = stats?.dormant_status === 'pending' || stats?.dormant_status === 'stale'

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Bem-vindo, {firstName}</h1>
        <p className="mt-1 text-muted-foreground">Escolha uma operação para começar.</p>
      </div>

      <div>
        <div className="mb-4 flex items-center gap-2">
          <Users className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Operações</h2>
        </div>
        {visibleCards.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma operação disponível para seu perfil.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {visibleCards.map((c) => (
              <ActionCard key={c.to} {...c} />
            ))}
          </div>
        )}
      </div>

      <div>
        <div className="mb-4 flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Resumo</h2>
        </div>

        {statsError && (
          <Alert variant="destructive" className="mb-3">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Não foi possível carregar o resumo: {statsErr instanceof Error ? statsErr.message : 'erro desconhecido'}
            </AlertDescription>
          </Alert>
        )}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <StatTile label="Clientes TiFlux" value={stats?.tiflux_total} icon={Users} loading={statsPending} />
          <StatTile label="Clientes VHSYS (ativos)" value={stats?.vhsys_total} icon={Database} loading={statsPending} />
          <StatTile label="Cadastrados (30d)" value={stats?.registered_30d} icon={UserPlus} loading={statsPending} />
          <StatTile label="Inativados (30d)" value={stats?.inactivated_30d} icon={UserX} loading={statsPending} />
          <StatTile
            label="Sem atividade (TiFlux)"
            value={stats?.tiflux_dormant}
            icon={Clock}
            loading={statsPending}
            pending={dormantPending}
          />
        </div>

        {stats?.computed_at && (
          <p className="mt-3 text-xs text-muted-foreground">
            Atualizado em {formatDate(stats.computed_at)}
            {stale && ' · dados podem estar desatualizados'}
            {isFetching && !statsPending && ' · atualizando…'}
            {dormantPending && stats.tiflux_dormant == null && ' · contagem sem atividade em andamento'}
          </p>
        )}
      </div>

      {!user?.dev_mode && visibleCards.length === 0 && (
        <p className="text-sm text-muted-foreground">Entre em contato com um administrador para solicitar acesso.</p>
      )}
    </div>
  )
}
