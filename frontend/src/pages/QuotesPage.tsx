import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileDown, FileText, Plus, Send, Trash2, AlertCircle, Loader2, Boxes } from 'lucide-react'
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
import { Skeleton } from '@/components/ui/skeleton'
import { digitsOnly, formatCnpj, formatDate } from '@/lib/format'
import { TEMP_LABELS } from '@/lib/quoteLead'
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

export function QuotesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<QuoteStatus | 'all'>('all')
  const [leadFilter, setLeadFilter] = useState<LeadTemperature | 'all'>('all')
  const [showCreate, setShowCreate] = useState(false)
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
    queryKey: ['quotes', statusFilter, leadFilter],
    queryFn: () =>
      api.listQuotes({
        status: statusFilter === 'all' ? undefined : statusFilter,
        lead_temperature: leadFilter === 'all' ? undefined : leadFilter,
        limit: 100,
        offset: 0,
      }),
  })

  const pipelineQuery = useQuery({
    queryKey: ['quotes', 'pipeline-summary'],
    queryFn: () => api.listQuotes({ limit: 100, offset: 0 }),
  })

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
      navigate(`/orcamentos/${created.id}`, { state: { initialStep: 2 } })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao criar orçamento')
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

  const quotes = listQuery.data?.quotes ?? []

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-lg bg-aurora-green-muted px-3 py-1.5 text-aurora-green">
            <FileText className="h-4 w-4" />
            <span className="text-xs font-semibold uppercase tracking-wide">Hub · Comercial</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Orçamentos</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Liste rascunhos e abra o wizard (cliente TiFlux → itens → revisão).
          </p>
          <p
            className="mt-1 min-h-4 text-xs text-aurora-muted"
            aria-live="polite"
          >
            {leadFilter !== 'all'
              ? `Filtro lead ${TEMP_LABELS[leadFilter]} — só não aprovados.`
              : '\u00a0'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
            {/* #region agent log */}
            {(() => { fetch('http://127.0.0.1:7498/ingest/30ad15c1-c7b0-4774-9a80-dadc1d901feb',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'cb0cec'},body:JSON.stringify({sessionId:'cb0cec',runId:'post-fix',hypothesisId:'H5',location:'QuotesPage.tsx:toolbar',message:'list header buttons',data:{hasBlocos:true,hasOrcamentos:true,novoInSameWrapAsLibraries:false},timestamp:Date.now()})}).catch(()=>{}); return null })()}
            {/* #endregion */}
            <Select
              value={leadFilter}
              onValueChange={(v) => {
                if (!LEAD_FILTER_VALUES.has(v)) return
                setLeadFilter(v as LeadTemperature | 'all')
              }}
            >
              <SelectTrigger className="w-[160px]" aria-label="Filtrar por lead">
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
              <SelectTrigger className="w-[180px]" aria-label="Filtrar por status">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Status: todos</SelectItem>
                {(Object.keys(STATUS_LABELS) as QuoteStatus[]).map((s) => (
                  <SelectItem key={s} value={s}>
                    {STATUS_LABELS[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              type="button"
              className={btnGreenClass}
              onClick={() => setShowCreate((v) => !v)}
            >
              <Plus className="h-4 w-4" />
              Novo
            </Button>
          </div>
      </div>
      <div className="flex flex-wrap gap-2">
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
      </div>

      {showCreate && (
        <Card className="border-aurora-green/30 bg-aurora-surface shadow-sm hub-panel-enter">
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
                        leadTemperature === null && 'border-aurora-accent text-aurora-accent',
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
                          leadTemperature === t && 'border-aurora-accent text-aurora-accent',
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
        quotes={pipelineQuery.data?.quotes ?? []}
        loading={pipelineQuery.isPending}
        activeLead={leadFilter}
        onSelectLead={(t) => setLeadFilter(t)}
        onOpenQuote={(id) => navigate(`/orcamentos/${id}`)}
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

      {!listQuery.isPending && !listQuery.isError && quotes.length === 0 && (
        <EmptyState
          icon={FileText}
          title="Nenhum orçamento"
          description="Busque o cliente no TiFlux para criar um rascunho."
          action={{ label: 'Novo rascunho', onClick: () => setShowCreate(true) }}
        />
      )}

      {!listQuery.isPending && quotes.length > 0 && (
        <ul className="space-y-3">
          {quotes.map((quote) => (
            <li key={quote.id}>
              <Card
                className={cn(
                  'border-aurora-border bg-aurora-surface shadow-sm aurora-motion',
                  'cursor-pointer hover:border-aurora-green/50 hover:shadow-md',
                )}
                role="link"
                tabIndex={0}
                onClick={() => navigate(`/orcamentos/${quote.id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate(`/orcamentos/${quote.id}`)
                  }
                }}
              >
                <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium">
                        {formatCnpj(quote.cnpj)}
                      </span>
                      <Badge variant={statusVariant(quote.status)}>
                        {STATUS_LABELS[quote.status]}
                      </Badge>
                      {quote.lead_temperature ? (
                        <Badge variant="outline">{TEMP_LABELS[quote.lead_temperature]}</Badge>
                      ) : null}
                      <span className="text-xs text-muted-foreground">#{quote.id}</span>
                    </div>
                    <p className="truncate text-sm text-aurora-fg">
                      {quote.client_name || 'Cliente não informado'}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {quote.items.length} item(ns) ·{' '}
                      {quoteTotal(quote).toLocaleString('pt-BR', {
                        style: 'currency',
                        currency: 'BRL',
                      })}{' '}
                      · atualizado {formatDate(quote.updated_at)}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    {isQuoteSubmittable(quote.status) && (
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
    </div>
  )
}
