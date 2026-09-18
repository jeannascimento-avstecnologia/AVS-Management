import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { ApiError, api, type QuoteRead, type TifluxTicketPreview } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  TICKET_LINK_LABELS,
  ticketLinkVariant,
} from '@/lib/quoteTicketLink'
import { btnDangerClass, btnGreenClass, btnSecondaryClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

type Props = {
  quote: QuoteRead | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function PreviewRows({ preview }: { preview: TifluxTicketPreview }) {
  const rows: Array<[string, string]> = [
    ['Número', `#${preview.ticket_number}`],
    ['Assunto', preview.subject || '—'],
    ['Cliente', preview.client_name || '—'],
    ['Status', preview.status || '—'],
    ['Catálogo', preview.catalog || '—'],
    ['Fechado', preview.closed ? 'Sim' : 'Não'],
  ]
  return (
    <dl className="space-y-2 rounded-lg border border-aurora-border bg-muted/40 p-3 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="flex min-w-0 justify-between gap-3">
          <dt className="shrink-0 text-muted-foreground">{label}</dt>
          <dd className="min-w-0 break-words text-right font-medium">{value}</dd>
        </div>
      ))}
      <div className="flex items-center justify-between gap-3 pt-1">
        <dt className="text-muted-foreground">Ticket</dt>
        <dd>
          <Badge variant={ticketLinkVariant(preview.suggested_link_status)}>
            Ticket: {TICKET_LINK_LABELS[preview.suggested_link_status]}
          </Badge>
        </dd>
      </div>
    </dl>
  )
}

export function QuoteTicketLinkDialog({ quote, open, onOpenChange }: Props) {
  const resetKey = [
    open ? 'open' : 'closed',
    quote?.id ?? 0,
    quote?.tiflux_ticket_number ?? '',
    quote?.ticket_link_status ?? '',
  ].join(':')
  return (
    <QuoteTicketLinkDialogBody
      key={resetKey}
      quote={quote}
      open={open}
      onOpenChange={onOpenChange}
    />
  )
}

function QuoteTicketLinkDialogBody({ quote, open, onOpenChange }: Props) {
  const queryClient = useQueryClient()
  const linked = Boolean(quote?.tiflux_ticket_number)
  const [mode, setMode] = useState<'linked' | 'search'>(linked ? 'linked' : 'search')
  const [ticketNumber, setTicketNumber] = useState('')
  const [preview, setPreview] = useState<TifluxTicketPreview | null>(null)
  const [searching, setSearching] = useState(false)

  const clientId = quote?.tiflux_client_id ?? null
  const listQuery = useQuery({
    queryKey: ['tiflux-tickets', clientId],
    queryFn: () => api.listTifluxTickets(clientId as number),
    enabled: open && mode === 'search' && clientId != null,
  })
  const listed = listQuery.data?.tickets ?? []
  const selectedPreview = preview ?? (listed.length === 1 ? listed[0] : null)
  const linkedSnapshot = quote?.ticket_link_snapshot ?? null

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['quotes'] })
    if (quote) {
      void queryClient.invalidateQueries({ queryKey: ['quote', quote.id] })
    }
  }

  const linkMutation = useMutation({
    mutationFn: (number: string) => {
      if (!quote) throw new Error('Orçamento inválido.')
      return api.linkQuoteTicket(quote.id, number)
    },
    onSuccess: (updated) => {
      toast.success(`Ticket #${updated.tiflux_ticket_number} vinculado`)
      invalidate()
      onOpenChange(false)
    },
    onError: (err: Error) => {
      if (err instanceof ApiError && err.status === 404) {
        toast.error('Ticket TiFlux não encontrado.')
        return
      }
      toast.error(err.message || 'Falha ao vincular ticket')
    },
  })

  const unlinkMutation = useMutation({
    mutationFn: () => {
      if (!quote) throw new Error('Orçamento inválido.')
      return api.unlinkQuoteTicket(quote.id)
    },
    onSuccess: () => {
      toast.success('Ticket desvinculado')
      invalidate()
      onOpenChange(false)
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Falha ao desvincular ticket')
    },
  })

  async function handleSearch() {
    const number = ticketNumber.trim()
    if (!number || !/^\d+$/.test(number)) {
      toast.error('Informe o número do ticket (somente dígitos).')
      return
    }
    setSearching(true)
    try {
      const found = await api.getTifluxTicket(number)
      setPreview(found)
    } catch (err) {
      setPreview(null)
      if (err instanceof ApiError && err.status === 404) {
        toast.error('Ticket TiFlux não encontrado.')
        return
      }
      toast.error(err instanceof Error ? err.message : 'Falha ao buscar ticket')
    } finally {
      setSearching(false)
    }
  }

  if (!quote) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[min(90vh,36rem)] w-[calc(100vw-1.5rem)] min-w-0 max-w-lg flex-col overflow-x-hidden overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        onPointerDown={(e) => e.stopPropagation()}
      >
        <DialogHeader>
          <DialogTitle>
            {mode === 'linked' ? 'Ticket vinculado' : 'Associar a um Ticket'}
          </DialogTitle>
          <DialogDescription>
            Orçamento #{quote.id}
            {quote.client_name ? ` · ${quote.client_name}` : ''}
          </DialogDescription>
        </DialogHeader>

        {mode === 'linked' ? (
          <div className="min-w-0 space-y-3">
            {linkedSnapshot ? (
              <PreviewRows preview={linkedSnapshot} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Ticket #{quote.tiflux_ticket_number} ·{' '}
                {quote.ticket_link_status
                  ? `Ticket: ${TICKET_LINK_LABELS[quote.ticket_link_status]}`
                  : 'sem classificação'}
              </p>
            )}
            <DialogFooter className="gap-2 sm:gap-2">
              <Button
                type="button"
                size="sm"
                className={btnSecondaryClass}
                onClick={() => {
                  setMode('search')
                  setPreview(null)
                  setTicketNumber('')
                }}
              >
                Trocar ticket
              </Button>
              <Button
                type="button"
                size="sm"
                className={btnDangerClass}
                disabled={unlinkMutation.isPending}
                onClick={() => unlinkMutation.mutate()}
              >
                {unlinkMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : null}
                Desvincular
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="min-w-0 space-y-3">
            {clientId == null ? (
              <p className="text-sm text-muted-foreground">
                Orçamento sem cliente TiFlux. Selecione o cliente no wizard para listar os tickets
                da mesa Comercial.
              </p>
            ) : listQuery.isPending ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Carregando tickets da mesa Comercial…
              </div>
            ) : listQuery.isError ? (
              <p className="text-sm text-aurora-danger">
                {listQuery.error instanceof Error
                  ? listQuery.error.message
                  : 'Não foi possível listar os tickets TiFlux.'}
              </p>
            ) : listed.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nenhum ticket na mesa Comercial para este cliente.
              </p>
            ) : (
              <ul className="max-h-56 min-w-0 space-y-1 overflow-y-auto overflow-x-hidden rounded-lg border border-aurora-border p-1">
                {listed.map((ticket) => {
                  const active = selectedPreview?.ticket_number === ticket.ticket_number
                  return (
                    <li key={ticket.ticket_number} className="min-w-0">
                      <button
                        type="button"
                        data-ticket-row
                        className={cn(
                          'flex w-full min-w-0 items-center justify-between gap-2 rounded-md px-2 py-2 text-left text-sm',
                          active ? 'bg-aurora-green-muted' : 'hover:bg-muted/60',
                        )}
                        aria-pressed={active}
                        aria-label={`Selecionar ticket ${ticket.ticket_number}`}
                        onClick={() => setPreview(ticket)}
                      >
                        <span className="min-w-0 flex-1 truncate">
                          <span className="font-mono font-medium">#{ticket.ticket_number}</span>
                          <span className="ml-2 text-muted-foreground">
                            {ticket.subject || 'Sem assunto'}
                          </span>
                        </span>
                        <Badge className="shrink-0" variant={ticketLinkVariant(ticket.suggested_link_status)}>
                          {TICKET_LINK_LABELS[ticket.suggested_link_status]}
                        </Badge>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
            <div className="min-w-0 space-y-1">
              <Label htmlFor="tiflux-ticket-number">Outro número</Label>
              <div className="flex min-w-0 gap-2">
                <Input
                  id="tiflux-ticket-number"
                  className="min-w-0 flex-1"
                  inputMode="numeric"
                  value={ticketNumber}
                  placeholder="Ex.: 12345"
                  onChange={(e) => setTicketNumber(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      void handleSearch()
                    }
                  }}
                />
                <Button
                  type="button"
                  size="sm"
                  className={btnSecondaryClass}
                  disabled={searching}
                  onClick={() => void handleSearch()}
                >
                  {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Buscar
                </Button>
              </div>
            </div>
            {selectedPreview ? <PreviewRows preview={selectedPreview} /> : null}
            <DialogFooter>
              <Button
                type="button"
                size="sm"
                className={btnGreenClass}
                disabled={!selectedPreview || linkMutation.isPending}
                onClick={() => {
                  if (!selectedPreview) return
                  linkMutation.mutate(selectedPreview.ticket_number)
                }}
              >
                {linkMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : null}
                Vincular
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
