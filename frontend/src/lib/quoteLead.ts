import type { LeadTemperature, QuoteRead, QuoteStatus } from '@/api/client'

export const TEMP_LABELS: Record<LeadTemperature, string> = {
  frio: 'Frio',
  morno: 'Morno',
  quente: 'Quente',
}

/** Ordem visual dos cards: Quente → Morno → Frio (esquerda → direita). */
export const LEAD_ORDER: LeadTemperature[] = ['quente', 'morno', 'frio']

export const OPEN_QUOTE_STATUSES = ['draft', 'submitted', 'sent'] as const satisfies readonly QuoteStatus[]

export type OpenQuoteStatus = (typeof OPEN_QUOTE_STATUSES)[number]

export type LeadCircleClasses = {
  button: string
  icon: string
  glow: string
  label: string
  amount: string
  ink: string
}

/** Glass / semi-flat — texto branco nos 3; fundos saturados para contraste. */
export const LEAD_CIRCLE: Record<LeadTemperature, LeadCircleClasses> = {
  quente: {
    button:
      'border-2 border-aurora-orange-deep bg-gradient-to-br from-aurora-orange via-aurora-orange to-aurora-orange-deep text-white shadow-md',
    icon: 'text-white/95 drop-shadow-md',
    glow: 'lead-circle-glow-quente',
    label: 'text-white',
    amount: 'text-white',
    ink: 'lead-circle-ink-light',
  },
  morno: {
    button:
      'border-2 border-aurora-yellow bg-gradient-to-br from-aurora-yellow-deep via-aurora-amber to-aurora-amber text-white shadow-md',
    icon: 'text-white/95 drop-shadow-md',
    glow: 'lead-circle-glow-morno',
    label: 'text-white',
    amount: 'text-white',
    ink: 'lead-circle-ink-light',
  },
  frio: {
    button:
      'border-2 border-aurora-accent bg-gradient-to-br from-aurora-info via-aurora-info to-aurora-accent text-white shadow-md',
    icon: 'text-white/95 drop-shadow-md',
    glow: 'lead-circle-glow-frio',
    label: 'text-white',
    amount: 'text-white',
    ink: 'lead-circle-ink-light',
  },
}

export function isOpenPipelineStatus(status: QuoteStatus): status is OpenQuoteStatus {
  return (OPEN_QUOTE_STATUSES as readonly QuoteStatus[]).includes(status)
}

export function countByLead(quotes: QuoteRead[]): Record<LeadTemperature, number> {
  const counts: Record<LeadTemperature, number> = { frio: 0, morno: 0, quente: 0 }
  for (const quote of quotes) {
    if (!isOpenPipelineStatus(quote.status)) continue
    const temp = quote.lead_temperature
    if (temp === null) continue
    counts[temp] += 1
  }
  return counts
}

/** Soma `items[].total_value` dos orçamentos abertos por temperatura. */
export function sumByLead(quotes: QuoteRead[]): Record<LeadTemperature, number> {
  const sums: Record<LeadTemperature, number> = { frio: 0, morno: 0, quente: 0 }
  for (const quote of quotes) {
    if (!isOpenPipelineStatus(quote.status)) continue
    const temp = quote.lead_temperature
    if (temp === null) continue
    const total = quote.items.reduce((acc, item) => acc + item.total_value, 0)
    sums[temp] += total
  }
  return sums
}

export function hotPendingQuotes(quotes: QuoteRead[], limit = 5): QuoteRead[] {
  return quotes
    .filter(
      (quote) => isOpenPipelineStatus(quote.status) && quote.lead_temperature === 'quente',
    )
    .sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    )
    .slice(0, limit)
}
