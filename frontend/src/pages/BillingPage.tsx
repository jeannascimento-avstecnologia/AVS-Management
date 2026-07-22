import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Loader2, Plus, Receipt, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  api,
  type BillingRunRead,
  type BillingStatus,
  type TifluxBillingHistoryType,
} from '@/api/client'
import {
  TifluxBillingClientSearch,
  type TifluxBillingClient,
} from '@/components/billing/TifluxBillingClientSearch'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { digitsOnly, formatCnpj, formatDate } from '@/lib/format'
import { btnDangerClass, btnSecondaryClass, btnTealClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

const STATUS_LABELS: Record<BillingStatus, string> = {
  draft: 'Rascunho',
  approved: 'Aprovado',
  awaiting_prefeitura: 'Aguardando prefeitura',
  emitting: 'Emitindo',
  sent: 'Enviado',
  error: 'Erro',
}

type ListTab = 'tiflux' | 'local'
type ContractPick = {
  id: number
  name: string
  amount: number
  external_ref: string
  selected: boolean
}

function statusVariant(
  status: BillingStatus,
): 'secondary' | 'info' | 'success' | 'destructive' | 'warning' | 'outline' {
  switch (status) {
    case 'draft':
      return 'secondary'
    case 'awaiting_prefeitura':
    case 'emitting':
      return 'warning'
    case 'approved':
    case 'sent':
      return 'success'
    case 'error':
      return 'destructive'
    default:
      return 'outline'
  }
}

function formatBrl(value: number | null | undefined): string {
  if (value == null) return '—'
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function parseOptionalNumber(raw: string): number | null {
  const t = raw.trim().replace(',', '.')
  if (!t) return null
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}

function applyDiscount(subtotal: number, pct: number | null, value: number | null): {
  discount: number
  net: number
} {
  const base = Math.max(0, subtotal)
  const fromPct = base * (Math.min(Math.max(pct ?? 0, 0), 100) / 100)
  const fixed = Math.max(value ?? 0, 0)
  const discount = Math.round((fromPct + fixed) * 100) / 100
  const net = Math.round(Math.max(0, base - discount) * 100) / 100
  return { discount, net }
}

function runTotal(run: BillingRunRead): number {
  if (run.net_total != null) return run.net_total
  if (run.gross_total != null) return run.gross_total
  return run.items.reduce((sum, item) => sum + item.amount, 0)
}

function currentCompetence(): string {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}`
}

function todayIso(): string {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function BillingPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const createPanelRef = useRef<HTMLDivElement>(null)
  const [tab, setTab] = useState<ListTab>('tiflux')
  const [statusFilter, setStatusFilter] = useState<BillingStatus | 'all'>('all')
  const [showCreate, setShowCreate] = useState(false)
  const [createFocusKey, setCreateFocusKey] = useState(0)

  const [filterCompetence, setFilterCompetence] = useState(currentCompetence)
  const [filterDay, setFilterDay] = useState('')
  const [filterClient, setFilterClient] = useState<TifluxBillingClient | null>(null)
  const [filterClientSearch, setFilterClientSearch] = useState('')
  const [filterType, setFilterType] = useState<TifluxBillingHistoryType | 'all'>('all')

  const [search, setSearch] = useState('')
  const [selectedClient, setSelectedClient] = useState<TifluxBillingClient | null>(null)
  const [cnpj, setCnpj] = useState('')
  const [clientName, setClientName] = useState('')
  const [tifluxClientId, setTifluxClientId] = useState<number | null>(null)
  const [competence, setCompetence] = useState(currentCompetence)
  const [contracts, setContracts] = useState<ContractPick[]>([])
  const [contractsLoading, setContractsLoading] = useState(false)
  const [hasRetencao, setHasRetencao] = useState(false)
  const [discountPct, setDiscountPct] = useState('')
  const [discountValue, setDiscountValue] = useState('')

  useEffect(() => {
    if (!showCreate) return
    const panel = createPanelRef.current
    if (!panel) return
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' })
    const input = panel.querySelector<HTMLInputElement>(
      'input:not([type="checkbox"]):not([type="hidden"]):not([type="month"]):not([type="date"])',
    )
    input?.focus({ preventScroll: true })
  }, [showCreate, createFocusKey])

  const historyQuery = useQuery({
    queryKey: [
      'billing-tiflux-history',
      filterDay,
      filterCompetence,
      filterClient?.id,
      filterType,
    ],
    queryFn: () =>
      api.listTifluxBillingHistory({
        billing_day: filterDay.trim() || undefined,
        competence: filterDay.trim() ? undefined : filterCompetence.trim() || undefined,
        client_id: filterClient?.id,
        billing_type: filterType === 'all' ? undefined : filterType,
        limit: 100,
        offset: 1,
      }),
    enabled: tab === 'tiflux',
  })

  const listQuery = useQuery({
    queryKey: ['billing-runs', statusFilter],
    queryFn: () =>
      api.listBillingRuns({
        status: statusFilter === 'all' ? undefined : statusFilter,
        limit: 100,
        offset: 0,
      }),
    enabled: tab === 'local',
  })

  useEffect(() => {
    if (tifluxClientId == null) {
      setContracts([])
      return
    }
    let cancelled = false
    setContractsLoading(true)
    void api
      .listTifluxBillingContracts(tifluxClientId)
      .then((res) => {
        if (cancelled) return
        setContracts(
          res.contracts.map((c) => ({
            id: c.id,
            name: c.name,
            amount: c.amount,
            external_ref: c.external_ref,
            selected: c.amount > 0,
          })),
        )
      })
      .catch((err: Error) => {
        if (cancelled) return
        setContracts([])
        toast.error(err.message || 'Falha ao carregar contratos TiFlux')
      })
      .finally(() => {
        if (!cancelled) setContractsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tifluxClientId])

  const createMutation = useMutation({
    mutationFn: () => {
      const selected = contracts.filter((c) => c.selected)
      const items = selected.map((c, index) => ({
        source: 'contract' as const,
        description: c.name,
        amount: c.amount,
        external_ref: c.external_ref,
        sort_order: index,
      }))
      const gross = items.reduce((sum, i) => sum + i.amount, 0)
      const pct = parseOptionalNumber(discountPct)
      const val = parseOptionalNumber(discountValue)
      return api.createBillingRun({
        cnpj: digitsOnly(cnpj),
        client_name: clientName.trim() || null,
        tiflux_client_id: tifluxClientId,
        competence: competence.trim(),
        has_retencao: hasRetencao,
        payment_method: 'boleto',
        gross_total: gross,
        discount_pct: pct,
        discount_value: val,
        items,
      })
    },
    onSuccess: (created) => {
      toast.success('Fila criada com contratos TiFlux')
      resetCreateForm()
      setShowCreate(false)
      void queryClient.invalidateQueries({ queryKey: ['billing-runs'] })
      void queryClient.invalidateQueries({ queryKey: ['billing-tiflux-history'] })
      navigate(`/faturamento/${created.id}`)
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao criar faturamento')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteBillingRun(id),
    onSuccess: () => {
      toast.success('Rascunho removido')
      void queryClient.invalidateQueries({ queryKey: ['billing-runs'] })
      void queryClient.invalidateQueries({ queryKey: ['billing-tiflux-history'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao remover')
    },
  })

  function resetCreateForm() {
    setSearch('')
    setSelectedClient(null)
    setCnpj('')
    setClientName('')
    setTifluxClientId(null)
    setCompetence(currentCompetence())
    setContracts([])
    setHasRetencao(false)
    setDiscountPct('')
    setDiscountValue('')
  }

  /** Abre o painel e força scroll/foco (painel fica acima da lista longa). */
  function revealCreatePanel() {
    setShowCreate(true)
    setCreateFocusKey((k) => k + 1)
  }

  function handleSelectClient(client: TifluxBillingClient) {
    setSelectedClient(client)
    setSearch(client.name)
    setClientName(client.name)
    setTifluxClientId(client.id)
    if (client.cnpj) setCnpj(client.cnpj)
  }

  function openCreateForClient(client: TifluxBillingClient) {
    handleSelectClient(client)
    setCompetence(filterCompetence || currentCompetence())
    revealCreatePanel()
    if (client.cnpj) return
    void api
      .searchTifluxBillingClients(client.name, 10)
      .then((res) => {
        const match = res.clients.find((c) => c.id === client.id)
        if (match?.cnpj) {
          setCnpj(match.cnpj)
          setClientName(match.name)
        }
      })
      .catch(() => {
        /* CNPJ opcional até o usuário re-selecionar */
      })
  }

  function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (tifluxClientId == null) {
      toast.error('Selecione um cliente do TiFlux.')
      return
    }
    if (digitsOnly(cnpj).length !== 14) {
      toast.error('CNPJ inválido — selecione o cliente novamente ou corrija.')
      return
    }
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(competence.trim())) {
      toast.error('Competência deve ser YYYY-MM.')
      return
    }
    const selected = contracts.filter((c) => c.selected)
    if (selected.length === 0) {
      toast.error('Selecione ao menos um contrato TiFlux.')
      return
    }
    createMutation.mutate()
  }

  const selectedTotal = contracts
    .filter((c) => c.selected)
    .reduce((sum, c) => sum + c.amount, 0)
  const discountPreview = applyDiscount(
    selectedTotal,
    parseOptionalNumber(discountPct),
    parseOptionalNumber(discountValue),
  )
  const runs = listQuery.data?.runs ?? []
  const historyItems = historyQuery.data?.items ?? []

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-lg bg-aurora-teal-muted px-3 py-1.5 text-aurora-teal">
            <Receipt className="h-4 w-4" />
            <span className="text-xs font-semibold uppercase tracking-wide">Hub · Faturamento</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Faturamento</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Dados TiFlux (histórico) com filtros — pending/faturar indisponível na API.
            Filas locais para approve / prefeitura.
          </p>
        </div>
        <Button
          type="button"
          className={btnTealClass}
          onClick={() => {
            // Se já aberto (ex.: clique em linha fora da viewport), só revela — não fecha.
            if (showCreate) {
              setCreateFocusKey((k) => k + 1)
              return
            }
            revealCreatePanel()
          }}
        >
          <Plus className="h-4 w-4" />
          Nova fila
        </Button>
      </div>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Visão faturamento">
        <Button
          type="button"
          role="tab"
          aria-selected={tab === 'tiflux'}
          className={tab === 'tiflux' ? btnTealClass : btnSecondaryClass}
          onClick={() => setTab('tiflux')}
        >
          TiFlux
        </Button>
        <Button
          type="button"
          role="tab"
          aria-selected={tab === 'local'}
          className={tab === 'local' ? btnTealClass : btnSecondaryClass}
          onClick={() => setTab('local')}
        >
          Filas locais
        </Button>
      </div>

      {showCreate && (
        <Card
          ref={createPanelRef}
          className="scroll-mt-20 border-aurora-teal/30 bg-aurora-surface shadow-sm hub-panel-enter"
        >
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Nova fila do mês</CardTitle>
            <p className="text-xs text-muted-foreground">
              Busque o cliente no TiFlux — os contratos ativos são carregados automaticamente.
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="billing-client-search">Cliente TiFlux</Label>
                  <TifluxBillingClientSearch
                    value={search}
                    onChange={(v) => {
                      setSearch(v)
                      if (selectedClient && v !== selectedClient.name) {
                        setSelectedClient(null)
                        setTifluxClientId(null)
                        setContracts([])
                      }
                    }}
                    onSelect={handleSelectClient}
                  />
                  {tifluxClientId != null ? (
                    <p className="text-xs text-muted-foreground">
                      Selecionado: <strong>{clientName}</strong> · TiFlux #{tifluxClientId}
                      {cnpj ? ` · ${formatCnpj(cnpj)}` : ''}
                    </p>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Digite ao menos 2 caracteres (nome ou CNPJ).
                    </p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="billing-competence">Competência</Label>
                  <Input
                    id="billing-competence"
                    value={competence}
                    onChange={(e) => setCompetence(e.target.value)}
                    placeholder="YYYY-MM"
                    pattern="\d{4}-(0[1-9]|1[0-2])"
                    required
                  />
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 pb-2 text-sm">
                    <input
                      type="checkbox"
                      checked={hasRetencao}
                      onChange={(e) => setHasRetencao(e.target.checked)}
                      className="h-4 w-4 rounded border-aurora-border"
                    />
                    Possui retenção (NF prefeitura)
                  </label>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Label>Contratos TiFlux</Label>
                  {contracts.length > 0 ? (
                    <span className="text-xs tabular-nums text-muted-foreground">
                      Selecionados: {formatBrl(selectedTotal)}
                    </span>
                  ) : null}
                </div>
                {contractsLoading ? (
                  <div className="flex items-center gap-2 rounded-lg border border-aurora-border px-3 py-4 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Carregando contratos ativos…
                  </div>
                ) : tifluxClientId == null ? (
                  <p className="rounded-lg border border-dashed border-aurora-border px-3 py-4 text-sm text-muted-foreground">
                    Selecione um cliente para puxar os contratos.
                  </p>
                ) : contracts.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-aurora-border px-3 py-4 text-sm text-muted-foreground">
                    Nenhum contrato ativo encontrado para este cliente.
                  </p>
                ) : (
                  <ul className="divide-y divide-aurora-border rounded-lg border border-aurora-border">
                    {contracts.map((c) => (
                      <li key={c.id}>
                        <label className="flex cursor-pointer items-start gap-3 px-3 py-2.5 hover:bg-accent/40">
                          <input
                            type="checkbox"
                            className="mt-1 h-4 w-4 rounded border-aurora-border"
                            checked={c.selected}
                            onChange={(e) =>
                              setContracts((prev) =>
                                prev.map((row) =>
                                  row.id === c.id
                                    ? { ...row, selected: e.target.checked }
                                    : row,
                                ),
                              )
                            }
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium">{c.name}</span>
                            <span className="text-xs text-muted-foreground">
                              Contrato #{c.external_ref}
                            </span>
                          </span>
                          <span className="shrink-0 text-sm font-medium tabular-nums">
                            {formatBrl(c.amount)}
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="billing-discount-pct">Desconto %</Label>
                  <Input
                    id="billing-discount-pct"
                    type="number"
                    min={0}
                    max={100}
                    step="0.01"
                    inputMode="decimal"
                    value={discountPct}
                    onChange={(e) => setDiscountPct(e.target.value)}
                    placeholder="0"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="billing-discount-value">Desconto R$</Label>
                  <Input
                    id="billing-discount-value"
                    type="number"
                    min={0}
                    step="0.01"
                    inputMode="decimal"
                    value={discountValue}
                    onChange={(e) => setDiscountValue(e.target.value)}
                    placeholder="0,00"
                  />
                </div>
              </div>

              {selectedTotal > 0 ? (
                <div className="rounded-lg border border-aurora-border bg-muted/30 px-3 py-2 text-sm">
                  <p className="tabular-nums text-muted-foreground">
                    Bruto: {formatBrl(selectedTotal)}
                    {discountPreview.discount > 0
                      ? ` · Desconto: −${formatBrl(discountPreview.discount)}`
                      : ''}
                  </p>
                  <p className="font-medium tabular-nums">
                    Líquido: {formatBrl(discountPreview.net)}
                    {hasRetencao ? ' (retenção: líquido via prefeitura)' : ''}
                  </p>
                </div>
              ) : null}

              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  className={btnSecondaryClass}
                  onClick={() => {
                    setShowCreate(false)
                    resetCreateForm()
                  }}
                  disabled={createMutation.isPending}
                >
                  Cancelar
                </Button>
                <Button type="submit" className={btnTealClass} disabled={createMutation.isPending}>
                  {createMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Salvando…
                    </>
                  ) : (
                    'Criar fila'
                  )}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {tab === 'tiflux' && (
        <>
          <Card className="border-aurora-border bg-aurora-surface shadow-sm">
            <CardContent className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-2">
                <Label htmlFor="filter-competence">Competência</Label>
                <Input
                  id="filter-competence"
                  type="month"
                  value={filterCompetence}
                  onChange={(e) => setFilterCompetence(e.target.value)}
                  disabled={Boolean(filterDay.trim())}
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor="filter-day">Dia (opcional)</Label>
                  <button
                    type="button"
                    className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                    onClick={() => setFilterDay(todayIso())}
                  >
                    Hoje
                  </button>
                </div>
                <Input
                  id="filter-day"
                  type="date"
                  value={filterDay}
                  onChange={(e) => setFilterDay(e.target.value)}
                />
              </div>
              <div className="space-y-2 sm:col-span-2 lg:col-span-1">
                <Label>Empresa / cliente</Label>
                <TifluxBillingClientSearch
                  value={filterClientSearch}
                  onChange={(v) => {
                    setFilterClientSearch(v)
                    if (filterClient && v !== filterClient.name) setFilterClient(null)
                  }}
                  onSelect={(client) => {
                    setFilterClient(client)
                    setFilterClientSearch(client.name)
                  }}
                  placeholder="Filtrar por cliente…"
                />
                {filterClient ? (
                  <button
                    type="button"
                    className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                    onClick={() => {
                      setFilterClient(null)
                      setFilterClientSearch('')
                    }}
                  >
                    Limpar cliente
                  </button>
                ) : null}
              </div>
              <div className="space-y-2">
                <Label>Tipo</Label>
                <Select
                  value={filterType}
                  onValueChange={(v) => setFilterType(v as TifluxBillingHistoryType | 'all')}
                >
                  <SelectTrigger aria-label="Tipo faturamento TiFlux">
                    <SelectValue placeholder="Tipo" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos</SelectItem>
                    <SelectItem value="billed">Faturados</SelectItem>
                    <SelectItem value="paid">Pagos</SelectItem>
                    <SelectItem value="reversed">Estornados</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {historyQuery.data?.note ? (
            <p className="text-xs text-muted-foreground">{historyQuery.data.note}</p>
          ) : null}

          {historyQuery.isError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {historyQuery.error instanceof Error
                  ? historyQuery.error.message
                  : 'Falha ao carregar histórico TiFlux.'}
              </AlertDescription>
            </Alert>
          )}

          {historyQuery.isPending && (
            <div className="space-y-3" aria-busy="true">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          )}

          {!historyQuery.isPending && !historyQuery.isError && historyItems.length === 0 && (
            <EmptyState
              icon={Receipt}
              title="Nenhum faturamento TiFlux"
              description="Ajuste competência/dia ou cliente. Sem pending na API — lista = histórico."
              action={{ label: 'Nova fila', onClick: () => revealCreatePanel() }}
            />
          )}

          {!historyQuery.isPending && historyItems.length > 0 && (
            <ul className="space-y-3">
              {historyItems.map((item) => (
                <li key={item.billing_id}>
                  <Card className="border-aurora-border bg-aurora-surface shadow-sm">
                    <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate text-sm font-medium">
                            {item.client_name || `Cliente #${item.client_id ?? '—'}`}
                          </span>
                          {item.paid ? <Badge variant="success">Pago</Badge> : null}
                          {item.reversal ? <Badge variant="destructive">Estorno</Badge> : null}
                          {item.local_run_id != null ? (
                            <Badge variant="outline">Fila #{item.local_run_id}</Badge>
                          ) : null}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Fat. {item.billing_date || '—'} · Venc. {item.due_date || '—'}
                          {item.nfe_number != null ? ` · NFe ${item.nfe_number}` : ''}
                          {item.client_id != null ? ` · TiFlux #${item.client_id}` : ''}
                        </p>
                        <p className="text-sm font-medium tabular-nums">
                          {formatBrl(item.real_value)}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        {item.local_run_id != null ? (
                          <Button
                            type="button"
                            size="sm"
                            className={btnSecondaryClass}
                            onClick={() => navigate(`/faturamento/${item.local_run_id}`)}
                          >
                            Abrir fila
                          </Button>
                        ) : null}
                        {item.client_id != null ? (
                          <Button
                            type="button"
                            size="sm"
                            className={btnTealClass}
                            onClick={() =>
                              openCreateForClient({
                                id: item.client_id as number,
                                name: item.client_name || `Cliente #${item.client_id}`,
                                cnpj: null,
                              })
                            }
                          >
                            Nova fila
                          </Button>
                        ) : null}
                      </div>
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {tab === 'local' && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Select
              value={statusFilter}
              onValueChange={(v) => setStatusFilter(v as BillingStatus | 'all')}
            >
              <SelectTrigger className="w-full min-w-[180px] sm:w-[200px]" aria-label="Filtrar por status">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                {(Object.keys(STATUS_LABELS) as BillingStatus[]).map((s) => (
                  <SelectItem key={s} value={s}>
                    {STATUS_LABELS[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {listQuery.isError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {listQuery.error instanceof Error
                  ? listQuery.error.message
                  : 'Não foi possível carregar a fila de faturamento.'}
              </AlertDescription>
            </Alert>
          )}

          {listQuery.isPending && (
            <div className="space-y-3" aria-busy="true">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          )}

          {!listQuery.isPending && !listQuery.isError && runs.length === 0 && (
            <EmptyState
              icon={Receipt}
              title="Nenhuma fila"
              description="Busque um cliente TiFlux e importe os contratos do mês."
              action={{ label: 'Nova fila', onClick: () => revealCreatePanel() }}
            />
          )}

          {!listQuery.isPending && runs.length > 0 && (
            <ul className="space-y-3">
              {runs.map((run) => (
                <li key={run.id}>
                  <Card
                    className={cn(
                      'border-aurora-border bg-aurora-surface shadow-sm aurora-motion',
                      'cursor-pointer hover:border-aurora-teal/50 hover:shadow-md',
                    )}
                    role="link"
                    tabIndex={0}
                    onClick={() => navigate(`/faturamento/${run.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        navigate(`/faturamento/${run.id}`)
                      }
                    }}
                  >
                    <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-sm font-medium">
                            {formatCnpj(run.cnpj)}
                          </span>
                          <Badge variant={statusVariant(run.status)}>
                            {STATUS_LABELS[run.status]}
                          </Badge>
                          <span className="text-xs text-muted-foreground">#{run.id}</span>
                          {run.has_retencao && <Badge variant="outline">Retenção</Badge>}
                          {run.tiflux_client_id != null && (
                            <Badge variant="outline">TiFlux #{run.tiflux_client_id}</Badge>
                          )}
                        </div>
                        <p className="truncate text-sm text-aurora-fg">
                          {run.client_name || 'Cliente não informado'} · {run.competence}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {run.items.length} item(ns) · {formatBrl(runTotal(run))} · atualizado{' '}
                          {formatDate(run.updated_at)}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        {run.status === 'draft' && (
                          <Button
                            type="button"
                            size="sm"
                            className={cn(btnDangerClass)}
                            disabled={deleteMutation.isPending}
                            onClick={(e) => {
                              e.stopPropagation()
                              if (window.confirm(`Remover rascunho #${run.id}?`)) {
                                deleteMutation.mutate(run.id)
                              }
                            }}
                            aria-label={`Remover faturamento ${run.id}`}
                          >
                            <Trash2 className="h-4 w-4" />
                            Remover
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
