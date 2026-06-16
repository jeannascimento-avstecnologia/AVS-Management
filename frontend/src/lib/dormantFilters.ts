import type { DormantClientRow } from './dormantReport'

export type ReasonFilter = 'all' | 'sem_ticket' | 'sem_cobranca' | 'sem_ambos'

export type SortKey = 'social' | 'cnpj' | 'last_ticket_at' | 'last_billing_at' | 'reasons'
export type SortDir = 'asc' | 'desc'

export function normalizeSearch(value: string): string {
  return value.trim().toLowerCase()
}

export function matchesSearch(row: DormantClientRow, query: string): boolean {
  const q = normalizeSearch(query)
  if (!q) return true
  const digits = q.replace(/\D/g, '')
  const name = `${row.social} ${row.name}`.toLowerCase()
  if (name.includes(q)) return true
  if (digits.length >= 3) {
    const cnpj = row.social_revenue.replace(/\D/g, '')
    return cnpj.includes(digits)
  }
  return false
}

export function matchesReasonFilter(row: DormantClientRow, filter: ReasonFilter): boolean {
  const codes = row.reasonCodes
  const hasTicket = codes.includes('sem_ticket_24m')
  const hasBilling = codes.includes('sem_cobranca_24m')
  switch (filter) {
    case 'sem_ticket':
      return hasTicket
    case 'sem_cobranca':
      return hasBilling
    case 'sem_ambos':
      return hasTicket && hasBilling
    default:
      return true
  }
}

function compareNullableDate(a: string | null, b: string | null, dir: SortDir): number {
  const ta = a ? new Date(a).getTime() : 0
  const tb = b ? new Date(b).getTime() : 0
  return dir === 'asc' ? ta - tb : tb - ta
}

export function sortDormantRows(
  rows: DormantClientRow[],
  key: SortKey,
  dir: SortDir,
): DormantClientRow[] {
  const mult = dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    switch (key) {
      case 'social': {
        const av = (a.social || a.name).toLowerCase()
        const bv = (b.social || b.name).toLowerCase()
        return av.localeCompare(bv, 'pt-BR') * mult
      }
      case 'cnpj':
        return a.social_revenue.localeCompare(b.social_revenue) * mult
      case 'last_ticket_at':
        return compareNullableDate(a.last_ticket_at, b.last_ticket_at, dir)
      case 'last_billing_at':
        return compareNullableDate(a.last_billing_at, b.last_billing_at, dir)
      case 'reasons':
        return a.reasonLabels.join(', ').localeCompare(b.reasonLabels.join(', '), 'pt-BR') * mult
      default:
        return 0
    }
  })
}

export function filterAndSortDormantRows(
  rows: DormantClientRow[],
  opts: { search: string; reasonFilter: ReasonFilter; sortKey: SortKey; sortDir: SortDir },
): DormantClientRow[] {
  const filtered = rows.filter(
    (r) => matchesSearch(r, opts.search) && matchesReasonFilter(r, opts.reasonFilter),
  )
  return sortDormantRows(filtered, opts.sortKey, opts.sortDir)
}
