import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileDown, FileText, Plus, Send, Trash2, AlertCircle, Loader2, Boxes, ChevronDown, ChevronUp, Link2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  ApiError,
  api,
  downloadBinaryBlob,
  isQuoteSubmittable,
  type LeadTemperature,
  type QuoteItemWrite,
  type QuoteModule,
  type QuoteProposalTemplateRead,
  type QuoteRead,
  type QuoteStatus,
} from '@/api/client'
import { EmptyState } from '@/components/feedback/EmptyState'
import { QuoteLeadPipelinePanel } from '@/components/quotes/QuoteLeadPipelinePanel'
import { QuoteModuleTemplatesPanel } from '@/components/quotes/QuoteModuleTemplatesPanel'
import { QuoteProposalTemplatesPanel } from '@/components/quotes/QuoteProposalTemplatesPanel'
import { QuoteTicketLinkDialog } from '@/components/quotes/QuoteTicketLinkDialog'
import { TifluxQuoteClientSearch } from '@/components/quotes/TifluxQuoteClientSearch'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { digitsOnly, formatCnpj, formatDate } from '@/lib/format'
import { TEMP_LABELS } from '@/lib/quoteLead'
import {
  hasLinkedTicket,
  matchesTicketLinkFilter,
  sortQuotesByTicketLink,
  TICKET_LINK_LABELS,
  ticketLinkVariant,
  ticketRefreshSignature,
  type TicketLinkFilter,
} from '@/lib/quoteTicketLink'
import {
  QUOTE_TEMPLATE_PLACEHOLDER_CNPJ,
  QUOTE_TEMPLATE_PLACEHOLDER_NAME,
  isQuoteTemplatePlaceholderCnpj,
} from '@/lib/quoteTemplate'
import { btnDangerClass, btnGreenClass, btnSecondaryClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

const LEAD_FILTER_VALUES = new Set<string>(['all', ...Object.keys(TEMP_LABELS)])
const STATUS_FILTER_VALUES = new Set<string>([
  'all',
  'draft',
  'submitted',
  'sent',
  'approved',
  'rejected',
  'contracted',
])
const LINK_FILTER_VALUES = new Set<string>(['all', 'none', 'linked', 'approved', 'rejected'])

const STATUS_LABELS: Record<QuoteStatus, string> = {
  draft: 'Rascunho',
  submitted: 'Enviado',
  sent: 'Enviado ao cliente',
  approved: 'Aprovado',
  rejected: 'Rejeitado',
  contracted: 'Contratado',
}

function statusVariant(
  status: QuoteStatus,
): 'secondary' | 'info' | 'success' | 'destructive' | 'warning' | 'outline' {
  switch (status) {
    case 'draft':
      return 'secondary'
    case 'submitted':
    case 'sent':
      return 'info'
    case 'approved':
    case 'contracted':
      return 'success'
    case 'rejected':
      return 'destructive'
    default:
      return 'outline'
  }
}

function quoteTotal(quote: QuoteRead): number {
  return quote.items.reduce((sum, item) => sum + item.total_value, 0)
}

// #region agent log
function debugQuoteCardLayout(root: HTMLElement | null, quote: QuoteRead): void {
  if (!root) return
  const left = root.querySelector('[data-debug="quote-left"]') as HTMLElement | null
  const actions = root.querySelector('[data-debug="quote-actions"]') as HTMLElement | null
  const firstBtn = actions?.firstElementChild as HTMLElement | undefined
  const lastBtn = actions?.lastElementChild as HTMLElement | undefined
  const wrapped = Boolean(
    firstBtn && lastBtn && lastBtn.offsetTop - firstBtn.offsetTop > 4,
  )
  fetch('http://127.0.0.1:7624/ingest/4fbad495-1d4e-4120-8a74-d59ccbb75445', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '2c5947' },
    body: JSON.stringify({
      sessionId: '2c5947',
      runId: 'post-fix',
      hypothesisId: 'A-E',
      location: 'QuotesPage.tsx:card',
      message: 'quote card layout',
      data: {
        quoteId: quote.id,
        titleLen: (quote.title ?? '').length,
        clientLen: (quote.client_name ?? '').length,
        hasTitle: Boolean(quote.title),
        hasLead: Boolean(quote.lead_temperature),
        cardW: root.offsetWidth,
        leftW: left?.offsetWidth ?? 0,
        actionsW: actions?.offsetWidth ?? 0,
        actionsScrollW: actions?.scrollWidth ?? 0,
        actionsH: actions?.offsetHeight ?? 0,
        wrapped,
        firstBtnTop: firstBtn?.offsetTop ?? null,
        lastBtnTop: lastBtn?.offsetTop ?? null,
        innerW: window.innerWidth,
      },
      timestamp: Date.now(),
    }),
  }).catch(() => {})
}
// #endregion

export function QuotesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const openQuote = (id: number) => {
    navigate(`/orcamentos/${id}`)
  }
  const [statusFilter, setStatusFilter] = useState<QuoteStatus | 'all'>('all')
  const [leadFilter, setLeadFilter] = useState<LeadTemperature | 'all'>('all')
  const [linkFilter, setLinkFilter] = useState<TicketLinkFilter>('all')
  const [ticketDialogQuote, setTicketDialogQuote] = useState<QuoteRead | null>(null)
  const [clientFilter, setClientFilter] = useState('')
  const [numberFilter, setNumberFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [qFilter, setQFilter] = useState('')
  const [debouncedClient, setDebouncedClient] = useState('')
  const [debouncedNumber, setDebouncedNumber] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [filtersCollapsed, setFiltersCollapsed] = useState(false)
  const [cnpj, setCnpj] = useState('')
  const [clientName, setClientName] = useState('')
  const [clientSearch, setClientSearch] = useState('')
  const [tifluxClientId, setTifluxClientId] = useState<number | null>(null)
  const [leadTemperature, setLeadTemperature] = useState<LeadTemperature | null>(null)
  const [pdfId, setPdfId] = useState<number | null>(null)
  const [proposalLibraryOpen, setProposalLibraryOpen] = useState(false)
  const [moduleLibraryOpen, setModuleLibraryOpen] = useState(false)
  const [pendingProposal, setPendingProposal] = useState<{
    name: string
    modules: QuoteModule[]
    items: QuoteItemWrite[]
  } | null>(null)

  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebouncedClient(clientFilter)
      setDebouncedNumber(numberFilter)
      setDebouncedQ(qFilter)
    }, 300)
    return () => window.clearTimeout(t)
  }, [clientFilter, numberFilter, qFilter])

  function resetCreateForm() {
    setCnpj('')
    setClientName('')
    setClientSearch('')
    setTifluxClientId(null)
    setLeadTemperature(null)
  }

  function clearSelectedClient() {
    setTifluxClientId(null)
    setClientName('')
    setCnpj('')
  }

  const listQuery = useQuery({
    queryKey: [
      'quotes',
      statusFilter,
      leadFilter,
      debouncedClient,
      debouncedNumber,
      dateFrom,
      dateTo,
      debouncedQ,
    ],
    queryFn: () =>
      api.listQuotes({
        status: statusFilter === 'all' ? undefined : statusFilter,
        lead_temperature: leadFilter === 'all' ? undefined : leadFilter,
        client: debouncedClient.trim() || undefined,
        number: debouncedNumber.trim() || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        q: debouncedQ.trim() || undefined,
        limit: 100,
        offset: 0,
      }),
  })

  const pipelineQuery = useQuery({
    queryKey: ['quotes', 'pipeline-summary'],
    queryFn: () => api.listQuotes({ limit: 100, offset: 0 }),
  })

  const visibleQuotes = useMemo(() => {
    const source = listQuery.data?.quotes ?? []
    return sortQuotesByTicketLink(
      source.filter((quote) => matchesTicketLinkFilter(quote, linkFilter)),
    )
  }, [listQuery.data?.quotes, linkFilter])

  const refreshedSignatures = useRef<Set<string>>(new Set())
  useEffect(() => {
    const pool = [
      ...(listQuery.data?.quotes ?? []),
      ...(pipelineQuery.data?.quotes ?? []),
    ]
    const pending = new Map<number, string>()
    for (const quote of pool) {
      const sig = ticketRefreshSignature(quote)
      if (!sig || refreshedSignatures.current.has(sig)) continue
      pending.set(quote.id, sig)
    }
    if (pending.size === 0) return
    for (const sig of pending.values()) {
      refreshedSignatures.current.add(sig)
    }
    const ids = [...pending.keys()]
    void api
      .refreshTicketLinks(ids)
      .then((result) => {
        if (result.updated.length > 0) {
          void queryClient.invalidateQueries({ queryKey: ['quotes'] })
        }
        if (result.failures.length > 0) {
          toast.error(
            `Não foi possível atualizar ${result.failures.length} ticket(s) vinculado(s).`,
          )
        }
      })
      .catch((err: unknown) => {
        for (const sig of pending.values()) {
          refreshedSignatures.current.delete(sig)
        }
        toast.error(err instanceof Error ? err.message : 'Falha ao verificar tickets TiFlux')
      })
  }, [listQuery.data, pipelineQuery.data, queryClient])

  const createMutation = useMutation({
    mutationFn: () =>
      api.createQuote({
        cnpj: digitsOnly(cnpj),
        client_name: clientName.trim() || null,
        tiflux_client_id: tifluxClientId,
        lead_temperature: leadTemperature,
        items: pendingProposal?.items ?? [],
        modules: pendingProposal?.modules ?? [],
      }),
    onSuccess: (created) => {
      toast.success('Rascunho criado')
      resetCreateForm()
      setPendingProposal(null)
      setShowCreate(false)
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      navigate(`/orcamentos/${created.id}`)
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao criar orçamento')
    },
  })

  const createTemplateMutation = useMutation({
    mutationFn: () =>
      api.createQuote({
        cnpj: QUOTE_TEMPLATE_PLACEHOLDER_CNPJ,
        client_name: QUOTE_TEMPLATE_PLACEHOLDER_NAME,
        tiflux_client_id: null,
        lead_temperature: null,
        items: [],
        modules: [],
      }),
    onSuccess: (created) => {
      toast.success(
        'Modelo: rascunho sem cliente. Salve na biblioteca quando o canvas estiver pronto.',
      )
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      navigate(`/orcamentos/${created.id}`)
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao criar modelo')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteQuote(id),
    onSuccess: () => {
      toast.success('Rascunho removido')
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao remover')
    },
  })

  const submitMutation = useMutation({
    mutationFn: (id: number) => api.submitQuote(id),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      void queryClient.invalidateQueries({ queryKey: ['quote', result.id] })
      const dryNote = result.dry_run ? ' (dry-run — sem POST externo)' : ''
      toast.success(`Orçamento #${result.id} enviado${dryNote}`)
    },
    onError: (err: Error) => {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          toast.error('Sem permissão para enviar orçamento.')
          return
        }
        if (err.status === 409) {
          toast.error(err.message || 'Orçamento não elegível para envio.')
          return
        }
      }
      toast.error(err.message || 'Falha ao enviar orçamento')
    },
  })

  function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (tifluxClientId == null) {
      toast.error('Selecione um cliente no TiFlux.')
      return
    }
    if (digitsOnly(cnpj).length !== 14) {
      toast.error('Cliente sem CNPJ válido no TiFlux. Atualize o cadastro ou use Cadastrar no wizard.')
      return
    }
    createMutation.mutate()
  }

  async function handleGeneratePdf(id: number) {
    setPdfId(id)
    try {
      const { blob, filename } = await api.generateQuotePdf(id)
      downloadBinaryBlob(blob, filename)
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      toast.success('PDF gerado')
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          toast.error('Sem permissão para gerar PDF.')
          return
        }
        if (err.status === 404) {
          toast.error('Orçamento não encontrado.')
          return
        }
      }
      toast.error(err instanceof Error ? err.message : 'Falha ao gerar PDF')
    } finally {
      setPdfId(null)
    }
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-2 inline-flex items-center gap-2 rounded-lg bg-aurora-green-muted px-3 py-1.5 text-aurora-green">
            <FileText className="h-4 w-4" />
            <span className="text-xs font-semibold uppercase tracking-wide">Hub · Comercial</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Orçamentos</h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Liste rascunhos e abra o wizard (cliente TiFlux → itens → revisão).
          </p>
          <p
            className="mt-1 min-h-4 text-xs text-muted-foreground"
            aria-live="polite"
          >
            {leadFilter !== 'all'
              ? `Filtro lead ${TEMP_LABELS[leadFilter]} — só não aprovados.`
              : '\u00a0'}
          </p>
        </div>
        <Button
          type="button"
          className={cn(btnGreenClass, 'w-fit shrink-0')}
          onClick={() =>
            setShowCreate((v) => {
              const next = !v
              if (next) setFiltersCollapsed(true)
              else setFiltersCollapsed(false)
              return next
            })
          }
        >
          <Plus className="h-4 w-4" />
          Novo
        </Button>
      </header>
      <div className="flex flex-wrap gap-2" role="toolbar" aria-label="Bibliotecas de orçamento">
        <Button
          type="button"
          className={btnSecondaryClass}
          onClick={() => setModuleLibraryOpen(true)}
        >
          <Boxes className="h-4 w-4" />
          Biblioteca de Blocos
        </Button>
        <Button
          type="button"
          className={btnSecondaryClass}
          onClick={() => setProposalLibraryOpen(true)}
        >
          <FileText className="h-4 w-4" />
          Biblioteca de Orçamentos
        </Button>
        <Button
          type="button"
          className={btnSecondaryClass}
          disabled={createTemplateMutation.isPending}
          onClick={() => createTemplateMutation.mutate()}
        >
          {createTemplateMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
          Criar modelo de orçamento
        </Button>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base">Pesquisa</CardTitle>
          {filtersCollapsed ? (
            <Button
              type="button"
              variant="ghost"
              className="h-8 gap-1 text-xs text-muted-foreground"
              onClick={() => setFiltersCollapsed(false)}
            >
              <ChevronDown className="h-4 w-4" />
              Expandir filtros
            </Button>
          ) : showCreate ? (
            <Button
              type="button"
              variant="ghost"
              className="h-8 gap-1 text-xs text-muted-foreground"
              onClick={() => setFiltersCollapsed(true)}
            >
              <ChevronUp className="h-4 w-4" />
              Recolher
            </Button>
          ) : null}
        </CardHeader>
        {filtersCollapsed ? (
          <CardContent className="pb-3 pt-0">
            <p className="text-xs text-muted-foreground">
              Filtros recolhidos enquanto você cria o rascunho.
            </p>
          </CardContent>
        ) : (
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <Select
              value={leadFilter}
              onValueChange={(v) => {
                if (!LEAD_FILTER_VALUES.has(v)) return
                setLeadFilter(v as LeadTemperature | 'all')
              }}
            >
              <SelectTrigger className="w-full min-w-0" aria-label="Filtrar por lead">
                <SelectValue placeholder="Lead" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Lead: todos</SelectItem>
                {(Object.keys(TEMP_LABELS) as LeadTemperature[]).map((t) => (
                  <SelectItem key={t} value={t}>
                    Lead: {TEMP_LABELS[t]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={statusFilter}
              onValueChange={(v) => {
                if (!STATUS_FILTER_VALUES.has(v)) return
                setStatusFilter(v as QuoteStatus | 'all')
              }}
            >
              <SelectTrigger className="w-full min-w-0" aria-label="Filtrar por status">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Status: todos</SelectItem>
                {(Object.keys(STATUS_LABELS) as QuoteStatus[]).map((s) => (
                  <SelectItem key={s} value={s}>
                    Status: {STATUS_LABELS[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={linkFilter}
              onValueChange={(v) => {
                if (!LINK_FILTER_VALUES.has(v)) return
                setLinkFilter(v as TicketLinkFilter)
              }}
            >
              <SelectTrigger className="w-full min-w-0" aria-label="Filtrar por vínculo de ticket">
                <SelectValue placeholder="Ticket" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Ticket: todos</SelectItem>
                <SelectItem value="none">Sem ticket</SelectItem>
                <SelectItem value="linked">Com ticket (novo)</SelectItem>
                <SelectItem value="approved">Ticket: aprovados</SelectItem>
                <SelectItem value="rejected">Ticket: rejeitados</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground" htmlFor="quote-filter-client">
              Cliente
            </label>
            <Input
              id="quote-filter-client"
              value={clientFilter}
              placeholder="Nome ou CNPJ"
              onChange={(e) => setClientFilter(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground" htmlFor="quote-filter-number">
              Número
            </label>
            <Input
              id="quote-filter-number"
              value={numberFilter}
              placeholder="M123"
              onChange={(e) => setNumberFilter(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground" htmlFor="quote-filter-from">
              Data de
            </label>
            <Input
              id="quote-filter-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground" htmlFor="quote-filter-to">
              Data até
            </label>
            <Input
              id="quote-filter-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
          <div className="space-y-1 sm:col-span-2 lg:col-span-4">
            <label className="text-xs text-muted-foreground" htmlFor="quote-filter-q">
              Texto livre
            </label>
            <Input
              id="quote-filter-q"
              value={qFilter}
              placeholder="Nome, CNPJ, M123, item ou valor (ex.: 1.866,60)"
              onChange={(e) => setQFilter(e.target.value)}
            />
          </div>
          </div>
        </CardContent>
        )}
      </Card>

      {showCreate && (
        <Card className="hub-panel-enter">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Novo rascunho</CardTitle>
            <p className="text-xs text-muted-foreground">
              Busca TiFlux (CNPJ ou nome). Lead opcional no mesmo bloco.
              {pendingProposal
                ? ` Modelo vinculado: ${pendingProposal.name}.`
                : ''}
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-4">
              <fieldset className="space-y-3 rounded-lg border border-aurora-border p-3">
                <legend className="px-1 text-sm font-medium">Cliente</legend>
                <TifluxQuoteClientSearch
                  value={clientSearch}
                  onChange={(v) => {
                    setClientSearch(v)
                    if (tifluxClientId != null && v !== clientName) clearSelectedClient()
                  }}
                  onSelect={(client) => {
                    const clientCnpj = client.cnpj ? digitsOnly(client.cnpj) : ''
                    if (clientCnpj.length !== 14) {
                      toast.error('Cliente sem CNPJ válido no TiFlux.')
                      return
                    }
                    setClientSearch(client.name)
                    setClientName(client.name)
                    setTifluxClientId(client.id)
                    setCnpj(clientCnpj)
                    toast.success(`Cliente TiFlux #${client.id} selecionado`)
                  }}
                />
                {tifluxClientId != null ? (
                  <p className="text-xs text-muted-foreground">
                    <strong>{clientName}</strong> · TiFlux #{tifluxClientId} · {formatCnpj(cnpj)}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Digite ≥2 caracteres (nome ou CNPJ) e selecione na lista.
                  </p>
                )}
                <div className="flex flex-wrap items-center gap-2 border-t border-aurora-border/60 pt-3">
                  <span className="text-xs text-muted-foreground">Lead</span>
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Temperatura do lead">
                    <Button
                      type="button"
                      size="sm"
                      className={cn(
                        btnSecondaryClass,
                        leadTemperature === null && 'border-aurora-green text-aurora-green',
                      )}
                      onClick={() => setLeadTemperature(null)}
                    >
                      —
                    </Button>
                    {(Object.keys(TEMP_LABELS) as LeadTemperature[]).map((t) => (
                      <Button
                        key={t}
                        type="button"
                        size="sm"
                        className={cn(
                          btnSecondaryClass,
                          leadTemperature === t && 'border-aurora-green text-aurora-green',
                        )}
                        onClick={() => setLeadTemperature(t)}
                      >
                        {TEMP_LABELS[t]}
                      </Button>
                    ))}
                  </div>
                </div>
              </fieldset>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  className={btnSecondaryClass}
                  onClick={() => {
                    resetCreateForm()
                    setShowCreate(false)
                  }}
                  disabled={createMutation.isPending}
                >
                  Cancelar
                </Button>
                <Button
                  type="submit"
                  className={btnGreenClass}
                  disabled={createMutation.isPending || tifluxClientId == null}
                >
                  {createMutation.isPending ? 'Salvando…' : 'Criar'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <QuoteLeadPipelinePanel
        quotes={visibleQuotes}
        loading={listQuery.isPending}
        activeLead={leadFilter}
        onSelectLead={(t) => setLeadFilter(t)}
        onOpenQuote={(id) => openQuote(id)}
      />

      {listQuery.isError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {listQuery.error instanceof Error
              ? listQuery.error.message
              : 'Não foi possível carregar orçamentos.'}
          </AlertDescription>
        </Alert>
      )}

      {listQuery.isPending && (
        <div className="space-y-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      )}

      {!listQuery.isPending && !listQuery.isError && visibleQuotes.length === 0 && (
        <EmptyState
          icon={FileText}
          title="Nenhum orçamento"
          description={
            statusFilter !== 'all'
              ? `Nenhum orçamento com status ${STATUS_LABELS[statusFilter]}. Status do orçamento é independente do ticket TiFlux.`
              : linkFilter === 'approved'
                ? 'Nenhum orçamento com ticket aprovado.'
                : linkFilter === 'rejected'
                  ? 'Nenhum orçamento com ticket rejeitado.'
                  : linkFilter === 'linked'
                    ? 'Nenhum orçamento com ticket novo.'
                    : linkFilter === 'none'
                      ? 'Nenhum orçamento sem ticket.'
                      : leadFilter !== 'all'
                        ? `Nenhum lead ${TEMP_LABELS[leadFilter]} aberto.`
                        : 'Busque o cliente no TiFlux para criar um rascunho.'
          }
          action={{ label: 'Novo rascunho', onClick: () => setShowCreate(true) }}
        />
      )}

      {!listQuery.isPending && visibleQuotes.length > 0 && (
        <ul className="space-y-3">
          {visibleQuotes.map((quote) => (
            <li key={quote.id} className="min-w-0">
                  <Card
                className={cn(
                  'aurora-motion min-w-0 cursor-pointer overflow-hidden',
                  'hover:border-aurora-green/50 hover:shadow-md',
                )}
                role="link"
                tabIndex={0}
                onClick={() => openQuote(quote.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    openQuote(quote.id)
                  }
                }}
              >
                <CardContent
                  className="grid min-w-0 grid-cols-1 items-start gap-3 p-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center"
                  ref={(el) => {
                    // #region agent log
                    debugQuoteCardLayout(el, quote)
                    // #endregion
                  }}
                >
                  <div className="min-w-0 space-y-1 overflow-hidden" data-debug="quote-left">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium">
                        {isQuoteTemplatePlaceholderCnpj(quote.cnpj)
                          ? 'Sem cliente'
                          : formatCnpj(quote.cnpj)}
                      </span>
                      <Badge variant={statusVariant(quote.status)}>
                        {STATUS_LABELS[quote.status]}
                      </Badge>
                      {quote.lead_temperature ? (
                        <Badge variant="outline">{TEMP_LABELS[quote.lead_temperature]}</Badge>
                      ) : null}
                      <span className="text-xs text-muted-foreground">#{quote.id}</span>
                    </div>
                    {quote.title ? (
                      <p className="truncate text-xs text-muted-foreground" title={quote.title}>
                        {quote.title}
                      </p>
                    ) : null}
                    <p
                      className="truncate text-sm"
                      title={quote.client_name || undefined}
                    >
                      {quote.client_name || 'Cliente não informado'}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {quote.items.length} item(ns) ·{' '}
                      {quoteTotal(quote).toLocaleString('pt-BR', {
                        style: 'currency',
                        currency: 'BRL',
                      })}{' '}
                      · atualizado {formatDate(quote.updated_at)}
                    </p>
                  </div>
                  <div
                    className="flex w-full flex-wrap gap-2 lg:w-auto lg:shrink-0 lg:flex-nowrap lg:justify-end"
                    data-debug="quote-actions"
                  >
                    {isQuoteSubmittable(quote.status) &&
                    !isQuoteTemplatePlaceholderCnpj(quote.cnpj) && (
                      <Button
                        type="button"
                        size="sm"
                        className={btnGreenClass}
                        disabled={submitMutation.isPending && submitMutation.variables === quote.id}
                        onClick={(e) => {
                          e.stopPropagation()
                          submitMutation.mutate(quote.id)
                        }}
                        aria-label={`Enviar orçamento ${quote.id}`}
                      >
                        {submitMutation.isPending && submitMutation.variables === quote.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Send className="h-4 w-4" />
                        )}
                        Enviar
                      </Button>
                    )}
                    <Button
                      type="button"
                      size="sm"
                      className={btnSecondaryClass}
                      disabled={pdfId === quote.id}
                      onClick={(e) => {
                        e.stopPropagation()
                        void handleGeneratePdf(quote.id)
                      }}
                      aria-label={`Gerar PDF orçamento ${quote.id}`}
                    >
                      {pdfId === quote.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <FileDown className="h-4 w-4" />
                      )}
                      PDF
                    </Button>
                    {hasLinkedTicket(quote) ? (
                      <Button
                        type="button"
                        size="sm"
                        className={btnSecondaryClass}
                        onClick={(e) => {
                          e.stopPropagation()
                          setTicketDialogQuote(quote)
                        }}
                        aria-label={`Ticket ${quote.tiflux_ticket_number}`}
                      >
                        <span className="font-mono">#{quote.tiflux_ticket_number}</span>
                        <Badge variant={ticketLinkVariant(quote.ticket_link_status)}>
                          {quote.ticket_link_status
                            ? TICKET_LINK_LABELS[quote.ticket_link_status]
                            : 'Ticket'}
                        </Badge>
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        className={btnSecondaryClass}
                        onClick={(e) => {
                          e.stopPropagation()
                          setTicketDialogQuote(quote)
                        }}
                        aria-label={`Associar ticket ao orçamento ${quote.id}`}
                      >
                        <Link2 className="h-4 w-4" />
                        Associar a um Ticket
                      </Button>
                    )}
                    {quote.status === 'draft' && (
                      <Button
                        type="button"
                        size="sm"
                        className={cn(btnDangerClass)}
                        disabled={deleteMutation.isPending}
                        onClick={(e) => {
                          e.stopPropagation()
                          if (window.confirm(`Remover rascunho #${quote.id}?`)) {
                            deleteMutation.mutate(quote.id)
                          }
                        }}
                        aria-label={`Remover orçamento ${quote.id}`}
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

      <Dialog open={moduleLibraryOpen} onOpenChange={setModuleLibraryOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Biblioteca de Blocos</DialogTitle>
            <DialogDescription>
              Modelos de seção para inserir no wizard (itens + condições).
            </DialogDescription>
          </DialogHeader>
          <QuoteModuleTemplatesPanel embedded />
        </DialogContent>
      </Dialog>

      <Dialog open={proposalLibraryOpen} onOpenChange={setProposalLibraryOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Biblioteca de Orçamentos</DialogTitle>
            <DialogDescription>
              Escolha um modelo; ele será aplicado ao criar o próximo rascunho (após selecionar o cliente).
            </DialogDescription>
          </DialogHeader>
          <QuoteProposalTemplatesPanel
            embedded
            onSelect={(template: QuoteProposalTemplateRead) => {
              setPendingProposal({
                name: template.name,
                modules: template.modules,
                items: template.items,
              })
              setProposalLibraryOpen(false)
              setShowCreate(true)
              toast.success(`Modelo “${template.name}” vinculado ao novo rascunho`)
            }}
          />
        </DialogContent>
      </Dialog>

      <QuoteTicketLinkDialog
        quote={ticketDialogQuote}
        open={ticketDialogQuote != null}
        onOpenChange={(next) => {
          if (!next) setTicketDialogQuote(null)
        }}
      />
    </div>
  )
}
