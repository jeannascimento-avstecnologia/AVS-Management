import type { BadgeProps } from '@/components/ui/badge'
import type { QuoteRead, TicketLinkStatus } from '@/api/client'

export type TicketLinkFilter = 'all' | 'none' | 'linked' | 'approved' | 'rejected'

export type TicketBandId = Exclude<TicketLinkFilter, 'all'>

export const TICKET_BANDS: readonly { id: TicketBandId; title: string; empty: string }[] = [
  { id: 'none', title: 'Sem ticket', empty: 'Nenhum orçamento sem ticket.' },
  { id: 'linked', title: 'Com ticket', empty: 'Nenhum orçamento com ticket.' },
  { id: 'approved', title: 'Aprovados', empty: 'Nenhum orçamento com ticket aprovado.' },
  { id: 'rejected', title: 'Rejeitados', empty: 'Nenhum orçamento com ticket rejeitado.' },
]

export const TICKET_LINK_LABELS: Record<TicketLinkStatus, string> = {
  novo: 'Novo',
  aprovado: 'Aprovado',
  rejeitado: 'Rejeitado',
}

export function hasLinkedTicket(quote: QuoteRead): boolean {
  return Boolean(quote.tiflux_ticket_number)
}

export function ticketLinkRank(quote: QuoteRead): number {
  if (quote.ticket_link_status == null) return 0
  if (quote.ticket_link_status === 'novo') return 1
  if (quote.ticket_link_status === 'aprovado') return 2
  return 3
}

export function sortQuotesByTicketLink(quotes: QuoteRead[]): QuoteRead[] {
  return [...quotes].sort((a, b) => {
    const rankDiff = ticketLinkRank(a) - ticketLinkRank(b)
    if (rankDiff !== 0) return rankDiff
    return b.id - a.id
  })
}

export function matchesTicketLinkFilter(quote: QuoteRead, filter: TicketLinkFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'none') return quote.ticket_link_status == null
  if (filter === 'linked') return quote.ticket_link_status === 'novo'
  if (filter === 'approved') return quote.ticket_link_status === 'aprovado'
  return quote.ticket_link_status === 'rejeitado'
}

export function ticketBandId(quote: QuoteRead): TicketBandId {
  if (quote.ticket_link_status == null) return 'none'
  if (quote.ticket_link_status === 'novo') return 'linked'
  if (quote.ticket_link_status === 'aprovado') return 'approved'
  return 'rejected'
}

export function groupQuotesByTicketLink(
  quotes: QuoteRead[],
): Record<TicketBandId, QuoteRead[]> {
  const groups: Record<TicketBandId, QuoteRead[]> = {
    none: [],
    linked: [],
    approved: [],
    rejected: [],
  }
  for (const quote of sortQuotesByTicketLink(quotes)) {
    groups[ticketBandId(quote)].push(quote)
  }
  return groups
}

export function ticketLinkVariant(
  status: TicketLinkStatus | null | undefined,
): NonNullable<BadgeProps['variant']> {
  if (status === 'aprovado') return 'success'
  if (status === 'rejeitado') return 'destructive'
  if (status === 'novo') return 'info'
  return 'outline'
}

export function isTerminalTicketLink(status: TicketLinkStatus | null | undefined): boolean {
  return status === 'aprovado' || status === 'rejeitado'
}

export function ticketRefreshSignature(quote: QuoteRead): string | null {
  if (quote.ticket_link_status !== 'novo' || !quote.tiflux_ticket_number) return null
  return `${quote.id}:${quote.tiflux_ticket_number}`
}

export function followupStaleLabel(quote: Pick<QuoteRead, 'followup_stale' | 'followup_idle_days'>): string | null {
  if (!quote.followup_stale) return null
  const days = quote.followup_idle_days ?? 5
  return `Sem retorno há ${days} dias`
}
