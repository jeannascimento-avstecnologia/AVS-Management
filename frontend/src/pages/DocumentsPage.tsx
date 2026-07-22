import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  ExternalLink,
  FileDown,
  FileText,
  FolderSearch,
  Loader2,
  Receipt,
  Search,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  ApiError,
  api,
  downloadBinaryBlob,
  type DocumentBillingHit,
  type DocumentPdfHit,
  type DocumentQuoteHit,
  type DocumentsSearchResponse,
} from '@/api/client'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { usePermission } from '@/hooks/useAuth'
import { formatCnpj, formatDate } from '@/lib/format'
import { btnAmberClass, btnSecondaryClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

type Selected =
  | { kind: 'quote'; item: DocumentQuoteHit }
  | { kind: 'billing'; item: DocumentBillingHit }
  | { kind: 'pdf'; item: DocumentPdfHit }

function formatBrl(value: number | null | undefined): string {
  if (value == null) return '—'
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function normalizeDocumentsResponse(
  data: DocumentsSearchResponse | undefined | null,
): DocumentsSearchResponse {
  return {
    query: typeof data?.query === 'string' ? data.query : '',
    quotes: Array.isArray(data?.quotes) ? data.quotes : [],
    pdfs: Array.isArray(data?.pdfs) ? data.pdfs : [],
    billing_runs: Array.isArray(data?.billing_runs) ? data.billing_runs : [],
    enrichment: data?.enrichment ?? {
      tiflux: 'skipped',
      vhsys: 'skipped',
      detail: null,
    },
  }
}

function billedByLabel(type: string | null | undefined, name: string | null | undefined): string {
  if (!type && !name) return '—'
  if (type && name) return `${type} · ${name}`
  return type || name || '—'
}

export function DocumentsPage() {
  const navigate = useNavigate()
  const canQuotes = usePermission('orcamentos')
  const canBilling = usePermission('faturar')
  const [query, setQuery] = useState('')
  const [searchResult, setSearchResult] = useState<DocumentsSearchResponse | null>(null)
  const [selected, setSelected] = useState<Selected | null>(null)
  const [pdfBusyId, setPdfBusyId] = useState<number | null>(null)

  const recentQuery = useQuery({
    queryKey: ['documents', 'recent'],
    queryFn: async () => normalizeDocumentsResponse(await api.listRecentDocuments(50)),
  })

  const searchMutation = useMutation({
    mutationFn: (q: string) => api.searchDocuments(q),
    onSuccess: (data) => {
      setSearchResult(normalizeDocumentsResponse(data))
      setSelected(null)
    },
    onError: (err: Error) => {
      if (err instanceof ApiError && err.status === 403) {
        toast.error('Sem permissão para consultar documentos.')
        return
      }
      toast.error(err.message || 'Falha na busca')
    },
  })

  const showingSearch = searchResult != null
  const result = showingSearch ? searchResult : (recentQuery.data ?? null)
  const listBusy = showingSearch ? searchMutation.isPending : recentQuery.isPending

  const defaultTab = useMemo(() => {
    if (!result) return canQuotes ? 'quotes' : 'billing'
    const quotes = result.quotes ?? []
    const billing = result.billing_runs ?? []
    const pdfs = result.pdfs ?? []
    if (canQuotes && quotes.length > 0) return 'quotes'
    if (canBilling && billing.length > 0) return 'billing'
    if (canQuotes && pdfs.length > 0) return 'pdfs'
    return canQuotes ? 'quotes' : 'billing'
  }, [result, canQuotes, canBilling])

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) {
      handleClearSearch()
      return
    }
    searchMutation.mutate(q)
  }

  function handleClearSearch() {
    setQuery('')
    setSearchResult(null)
    setSelected(null)
  }

  async function handleDownloadPdf(quoteId: number) {
    setPdfBusyId(quoteId)
    try {
      const { blob, filename } = await api.downloadQuotePdf(quoteId)
      downloadBinaryBlob(blob, filename)
      toast.success('PDF baixado')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Falha ao baixar PDF')
    } finally {
      setPdfBusyId(null)
    }
  }

  const enrichmentHint =
    showingSearch &&
    result &&
    (result.enrichment.tiflux === 'error' || result.enrichment.vhsys === 'error')
      ? result.enrichment.detail || 'Enriquecimento externo falhou; resultados locais mantidos.'
      : null

  const emptyDescription = showingSearch
    ? 'Tente outro CNPJ, nome ou ordem.'
    : 'Nenhum documento recente no hub ainda.'

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <div className="mb-2 inline-flex items-center gap-2 rounded-lg bg-aurora-amber-muted px-3 py-1.5 text-aurora-amber">
          <FolderSearch className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-wide">Hub · Consulta</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">Documentos</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Recentes do hub ou busca por empresa (CNPJ/nome) / ordem (M12, OS VHSYS).
        </p>
      </div>

      <Card className="border-aurora-border bg-aurora-surface shadow-sm hub-panel-enter">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base text-aurora-amber">
            <FolderSearch className="h-4 w-4" />
            Busca
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex flex-col gap-3 sm:flex-row">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="CNPJ, nome, M42, OS555…"
              aria-label="Buscar documentos"
              className="flex-1 focus-visible:border-aurora-amber focus-visible:ring-aurora-amber-muted"
              autoFocus
            />
            <div className="flex gap-2">
              <Button
                type="submit"
                className={cn(btnAmberClass, 'sm:w-auto')}
                disabled={searchMutation.isPending}
              >
                {searchMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Search className="mr-2 h-4 w-4" />
                )}
                Buscar
              </Button>
              {showingSearch && (
                <Button
                  type="button"
                  variant="outline"
                  className={btnSecondaryClass}
                  onClick={handleClearSearch}
                >
                  <X className="mr-2 h-4 w-4" />
                  Limpar
                </Button>
              )}
            </div>
          </form>
          {showingSearch && result && (
            <p className="mt-2 text-xs text-muted-foreground">
              Resultados para “{result.query}”. Limpar volta aos recentes.
            </p>
          )}
          {!showingSearch && (
            <p className="mt-2 text-xs text-muted-foreground">
              Exibindo documentos mais recentes (atualizado → mais antigo).
            </p>
          )}
        </CardContent>
      </Card>

      {enrichmentHint && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{enrichmentHint}</AlertDescription>
        </Alert>
      )}

      {recentQuery.isError && !showingSearch && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {recentQuery.error instanceof Error
              ? recentQuery.error.message
              : 'Falha ao carregar recentes.'}
          </AlertDescription>
        </Alert>
      )}

      {listBusy && !result && (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Carregando documentos…
        </div>
      )}

      {result && (
        <Tabs key={`${showingSearch ? result.query : 'recent'}-${defaultTab}`} defaultValue={defaultTab}>
          <TabsList>
            {canQuotes && (
              <TabsTrigger value="quotes">
                Orçamentos ({result.quotes.length})
              </TabsTrigger>
            )}
            {canBilling && (
              <TabsTrigger value="billing">
                Faturamentos ({result.billing_runs.length})
              </TabsTrigger>
            )}
            {canQuotes && (
              <TabsTrigger value="pdfs">PDFs ({result.pdfs.length})</TabsTrigger>
            )}
          </TabsList>

          {canQuotes && (
            <TabsContent value="quotes" className="mt-4">
              {result.quotes.length === 0 ? (
                <EmptyState
                  icon={FileText}
                  title="Nenhum orçamento"
                  description={emptyDescription}
                />
              ) : (
                <ul className="space-y-2">
                  {result.quotes.map((quote) => (
                    <li key={quote.id}>
                      <button
                        type="button"
                        className="flex w-full items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3 text-left aurora-motion hover:border-aurora-amber/40 hover:bg-aurora-amber-muted/40"
                        onClick={() => setSelected({ kind: 'quote', item: quote })}
                      >
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">{quote.display_id}</span>
                            <Badge variant="secondary">{quote.status}</Badge>
                            {quote.has_pdf && <Badge variant="info">PDF</Badge>}
                          </div>
                          <p className="mt-0.5 truncate text-sm text-muted-foreground">
                            {quote.client_name || '—'} · {formatCnpj(quote.cnpj)} ·{' '}
                            {formatBrl(quote.value_total)}
                          </p>
                        </div>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {formatDate(quote.updated_at)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>
          )}

          {canBilling && (
            <TabsContent value="billing" className="mt-4">
              {result.billing_runs.length === 0 ? (
                <EmptyState
                  icon={Receipt}
                  title="Nenhum faturamento"
                  description={emptyDescription}
                />
              ) : (
                <ul className="space-y-2">
                  {result.billing_runs.map((run) => (
                    <li key={run.id}>
                      <button
                        type="button"
                        className="flex w-full items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3 text-left aurora-motion hover:border-aurora-amber/40 hover:bg-aurora-amber-muted/40"
                        onClick={() => setSelected({ kind: 'billing', item: run })}
                      >
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">#{run.id}</span>
                            <Badge variant="secondary">{run.status}</Badge>
                            <Badge variant="outline">{run.competence}</Badge>
                          </div>
                          <p className="mt-0.5 truncate text-sm text-muted-foreground">
                            {run.client_name || '—'} · {formatCnpj(run.cnpj)} ·{' '}
                            {formatBrl(run.net_total)}
                          </p>
                        </div>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {formatDate(run.updated_at)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>
          )}

          {canQuotes && (
            <TabsContent value="pdfs" className="mt-4">
              {result.pdfs.length === 0 ? (
                <EmptyState
                  icon={FileDown}
                  title="Nenhum PDF"
                  description="PDFs aparecem quando o orçamento já tem arquivo gerado."
                />
              ) : (
                <ul className="space-y-2">
                  {result.pdfs.map((pdf) => (
                    <li key={pdf.quote_id}>
                      <button
                        type="button"
                        className="flex w-full items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3 text-left aurora-motion hover:border-aurora-amber/40 hover:bg-aurora-amber-muted/40"
                        onClick={() => setSelected({ kind: 'pdf', item: pdf })}
                      >
                        <div className="min-w-0">
                          <span className="font-medium">{pdf.display_id}</span>
                          <p className="mt-0.5 truncate text-sm text-muted-foreground">
                            {pdf.client_name || '—'} · {formatCnpj(pdf.cnpj)} ·{' '}
                            {formatBrl(pdf.value_total)}
                          </p>
                        </div>
                        <FileDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>
          )}
        </Tabs>
      )}

      <Sheet open={selected != null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-md">
          {selected?.kind === 'quote' && (
            <>
              <SheetHeader>
                <SheetTitle>Orçamento {selected.item.display_id}</SheetTitle>
              </SheetHeader>
              <div className="mt-6 space-y-4 text-sm">
                <DetailRow label="Tipo" value="Orçamento" />
                <DetailRow label="Cliente" value={selected.item.client_name || '—'} />
                <DetailRow label="CNPJ" value={formatCnpj(selected.item.cnpj)} />
                <DetailRow label="Status" value={selected.item.status} />
                <DetailRow label="Valor total" value={formatBrl(selected.item.value_total)} />
                <DetailRow label="Implantação (líq.)" value={formatBrl(selected.item.implant_net)} />
                <DetailRow label="Mensalidade (líq.)" value={formatBrl(selected.item.monthly_net)} />
                <DetailRow
                  label="Temperatura"
                  value={selected.item.lead_temperature || '—'}
                />
                <DetailRow
                  label="Faturado por"
                  value={billedByLabel(selected.item.billed_by_type, selected.item.billed_by_name)}
                />
                <DetailRow label="OS VHSYS" value={selected.item.vhsys_os_id || '—'} />
                <DetailRow
                  label="Ticket TiFlux"
                  value={selected.item.tiflux_ticket_number || '—'}
                />
                <DetailRow label="PDF" value={selected.item.has_pdf ? 'Sim' : 'Não'} />
                <DetailRow label="Criado" value={formatDate(selected.item.created_at)} />
                <DetailRow label="Atualizado" value={formatDate(selected.item.updated_at)} />
                <div className="flex flex-col gap-2 pt-2">
                  {selected.item.has_pdf && (
                    <Button
                      type="button"
                      className={btnSecondaryClass}
                      disabled={pdfBusyId === selected.item.id}
                      onClick={() => void handleDownloadPdf(selected.item.id)}
                    >
                      {pdfBusyId === selected.item.id ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <FileDown className="mr-2 h-4 w-4" />
                      )}
                      Baixar PDF
                    </Button>
                  )}
                  <Button
                    type="button"
                    className={btnAmberClass}
                    onClick={() => navigate(`/orcamentos/${selected.item.id}`)}
                  >
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Abrir em Orçamentos
                  </Button>
                </div>
              </div>
            </>
          )}

          {selected?.kind === 'billing' && (
            <>
              <SheetHeader>
                <SheetTitle>Faturamento #{selected.item.id}</SheetTitle>
              </SheetHeader>
              <div className="mt-6 space-y-4 text-sm">
                <DetailRow label="Tipo" value="Faturamento" />
                <DetailRow label="Cliente" value={selected.item.client_name || '—'} />
                <DetailRow label="CNPJ" value={formatCnpj(selected.item.cnpj)} />
                <DetailRow label="Competência" value={selected.item.competence} />
                <DetailRow label="Status" value={selected.item.status} />
                <DetailRow label="Valor líquido" value={formatBrl(selected.item.net_total)} />
                <DetailRow label="Valor bruto" value={formatBrl(selected.item.gross_total)} />
                <DetailRow
                  label="Vencimento"
                  value={selected.item.due_date ? formatDate(selected.item.due_date) : '—'}
                />
                <DetailRow
                  label="Pagamento"
                  value={selected.item.payment_method || '—'}
                />
                <DetailRow label="NF VHSYS" value={selected.item.vhsys_nf_id || '—'} />
                <DetailRow label="CR VHSYS" value={selected.item.vhsys_cr_id || '—'} />
                <DetailRow
                  label="Ticket TiFlux"
                  value={selected.item.tiflux_ticket_number || '—'}
                />
                <DetailRow label="Criado" value={formatDate(selected.item.created_at)} />
                <DetailRow label="Atualizado" value={formatDate(selected.item.updated_at)} />
                <div className="pt-2">
                  <Button
                    type="button"
                    className={btnAmberClass}
                    onClick={() => navigate(`/faturamento/${selected.item.id}`)}
                  >
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Abrir faturamento
                  </Button>
                </div>
              </div>
            </>
          )}

          {selected?.kind === 'pdf' && (
            <>
              <SheetHeader>
                <SheetTitle>PDF {selected.item.display_id}</SheetTitle>
              </SheetHeader>
              <div className="mt-6 space-y-4 text-sm">
                <DetailRow label="Tipo" value="PDF" />
                <DetailRow label="Cliente" value={selected.item.client_name || '—'} />
                <DetailRow label="CNPJ" value={formatCnpj(selected.item.cnpj)} />
                <DetailRow label="Status orçamento" value={selected.item.status || '—'} />
                <DetailRow
                  label="Valor (orçamento pai)"
                  value={formatBrl(selected.item.value_total)}
                />
                <DetailRow
                  label="Temperatura"
                  value={selected.item.lead_temperature || '—'}
                />
                <DetailRow
                  label="Faturado por"
                  value={billedByLabel(selected.item.billed_by_type, selected.item.billed_by_name)}
                />
                <DetailRow label="OS VHSYS" value={selected.item.vhsys_os_id || '—'} />
                <DetailRow
                  label="Ticket TiFlux"
                  value={selected.item.tiflux_ticket_number || '—'}
                />
                <DetailRow label="Arquivo" value={selected.item.pdf_path} />
                <DetailRow
                  label="Criado"
                  value={selected.item.created_at ? formatDate(selected.item.created_at) : '—'}
                />
                <DetailRow
                  label="Atualizado"
                  value={selected.item.updated_at ? formatDate(selected.item.updated_at) : '—'}
                />
                <div className="flex flex-col gap-2 pt-2">
                  <Button
                    type="button"
                    className={btnSecondaryClass}
                    disabled={pdfBusyId === selected.item.quote_id}
                    onClick={() => void handleDownloadPdf(selected.item.quote_id)}
                  >
                    {pdfBusyId === selected.item.quote_id ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <FileDown className="mr-2 h-4 w-4" />
                    )}
                    Baixar PDF
                  </Button>
                  <Button
                    type="button"
                    className={btnAmberClass}
                    onClick={() => navigate(`/orcamentos/${selected.item.quote_id}`)}
                  >
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Abrir em Orçamentos
                  </Button>
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-medium text-foreground">{value}</p>
    </div>
  )
}
