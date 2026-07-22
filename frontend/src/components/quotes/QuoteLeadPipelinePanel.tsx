import { useState } from 'react'
import { Flame, Snowflake, Thermometer } from 'lucide-react'
import type { LeadTemperature, QuoteRead, QuoteStatus } from '@/api/client'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/cn'
import {
  countByLead,
  hotPendingQuotes,
  LEAD_CIRCLE,
  LEAD_ORDER,
  sumByLead,
  TEMP_LABELS,
} from '@/lib/quoteLead'

const LEAD_ICONS = {
  frio: Snowflake,
  morno: Thermometer,
  quente: Flame,
} as const

const STATUS_LABELS: Record<QuoteStatus, string> = {
  draft: 'Rascunho',
  submitted: 'Enviado',
  sent: 'Enviado ao cliente',
  approved: 'Aprovado',
  rejected: 'Rejeitado',
  contracted: 'Contratado',
}

export type QuoteLeadPipelinePanelProps = {
  quotes: QuoteRead[]
  loading: boolean
  activeLead: LeadTemperature | 'all'
  onSelectLead: (temp: LeadTemperature | 'all') => void
  onOpenQuote: (id: number) => void
}

function quoteTotal(quote: QuoteRead): number {
  return quote.items.reduce((sum, item) => sum + item.total_value, 0)
}

function formatBrl(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function QuoteLeadPipelinePanel({
  quotes,
  loading,
  activeLead,
  onSelectLead,
  onOpenQuote,
}: QuoteLeadPipelinePanelProps) {
  const counts = countByLead(quotes)
  const sums = sumByLead(quotes)
  const hotPending = hotPendingQuotes(quotes, 5)
  const [pressedLead, setPressedLead] = useState<LeadTemperature | null>(null)

  return (
    <section className="space-y-4" aria-label="Pipeline por temperatura de lead">
      <div className="flex flex-nowrap items-center justify-center gap-3 overflow-visible sm:gap-6">
        {loading
          ? LEAD_ORDER.map((temp) => (
              <div key={temp} className="lead-circle-slot">
                <Skeleton
                  className="h-32 w-32 rounded-full sm:h-36 sm:w-36"
                  aria-label={`Carregando lead ${TEMP_LABELS[temp]}`}
                />
              </div>
            ))
          : LEAD_ORDER.map((temp) => {
              const Icon = LEAD_ICONS[temp]
              const circle = LEAD_CIRCLE[temp]
              const count = counts[temp]
              const amount = sums[temp]
              const isActive = activeLead === temp

              return (
                <div
                  key={temp}
                  className={cn('lead-circle-slot', isActive && 'is-selected')}
                >
                  <span
                    className={cn('lead-circle-halo', circle.glow)}
                    aria-hidden
                  />
                  <button
                    type="button"
                    aria-label={`Lead ${TEMP_LABELS[temp].toLowerCase()}: ${count} orçamentos abertos, total ${formatBrl(amount)}`}
                    aria-pressed={isActive}
                    onClick={() => {
                      setPressedLead(temp)
                      onSelectLead(isActive ? 'all' : temp)
                    }}
                    onAnimationEnd={(e) => {
                      if (e.animationName === 'lead-circle-press' && pressedLead === temp) {
                        setPressedLead(null)
                      }
                    }}
                    className={cn(
                      'lead-circle-btn flex flex-col items-center justify-center rounded-full',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80',
                      circle.button,
                      pressedLead === temp && 'is-pressed',
                    )}
                  >
                    <span
                      className={cn(
                        'pointer-events-none absolute top-2 right-2 z-0 sm:top-2.5 sm:right-2.5',
                        circle.icon,
                      )}
                    >
                      <Icon className="h-11 w-11 sm:h-12 sm:w-12" strokeWidth={2.35} aria-hidden />
                    </span>
                    <span
                      className={cn(
                        'relative z-10 flex w-full flex-col items-center px-2',
                        circle.ink,
                      )}
                    >
                      <span className="whitespace-nowrap text-3xl font-bold tabular-nums leading-none text-white sm:text-4xl">
                        {count}
                      </span>
                      <span
                        className={cn(
                          'mt-1.5 whitespace-nowrap text-sm font-bold uppercase tracking-wide text-white sm:text-base',
                          circle.label,
                        )}
                      >
                        {TEMP_LABELS[temp]}
                      </span>
                      <span
                        className={cn(
                          'mt-1 max-w-[90%] truncate whitespace-nowrap text-xs font-bold tabular-nums leading-tight text-white sm:text-sm',
                          circle.amount,
                        )}
                      >
                        {formatBrl(amount)}
                      </span>
                    </span>
                  </button>
                </div>
              )
            })}
      </div>

      <div className="rounded-xl border border-aurora-border bg-aurora-surface/80 p-3 shadow-sm backdrop-blur-sm">
        <h3 className="mb-2 text-sm font-semibold text-aurora-fg">Quase fechados</h3>
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
          </div>
        ) : hotPending.length === 0 ? (
          <p className="text-sm text-aurora-muted">Nenhum lead quente pendente</p>
        ) : (
          <ul className="divide-y divide-aurora-border/80">
            {hotPending.map((quote) => (
              <li key={quote.id}>
                <button
                  type="button"
                  onClick={() => onOpenQuote(quote.id)}
                  className={cn(
                    'flex w-full items-center justify-between gap-3 rounded-lg px-2 py-2.5 text-left',
                    'aurora-motion hover:bg-aurora-surface-2/60',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-aurora-amber/40',
                  )}
                  aria-label={`Abrir orçamento ${quote.id}: ${quote.client_name ?? quote.cnpj}`}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-aurora-fg">
                      {quote.client_name?.trim() || quote.cnpj}
                    </span>
                    <span className="text-xs text-aurora-muted">
                      {STATUS_LABELS[quote.status]}
                    </span>
                  </span>
                  <span className="shrink-0 text-sm font-semibold tabular-nums text-aurora-fg">
                    {formatBrl(quoteTotal(quote))}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
