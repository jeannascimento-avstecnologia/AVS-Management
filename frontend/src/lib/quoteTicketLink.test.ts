import { describe, expect, it } from 'vitest'
import {
  groupQuotesByTicketLink,
  matchesTicketLinkFilter,
  sortQuotesByTicketLink,
  ticketLinkRank,
  ticketRefreshSignature,
  followupStaleLabel,
} from '@/lib/quoteTicketLink'
import { makeQuote } from '@/test/quoteFixture'

describe('quoteTicketLink', () => {
  it('ranks R5 order', () => {
    const quotes = [
      makeQuote({ id: 4, ticket_link_status: 'rejeitado', tiflux_ticket_number: '4' }),
      makeQuote({ id: 2, ticket_link_status: 'novo', tiflux_ticket_number: '2' }),
      makeQuote({ id: 3, ticket_link_status: 'aprovado', tiflux_ticket_number: '3' }),
      makeQuote({ id: 1 }),
    ]
    expect(sortQuotesByTicketLink(quotes).map((q) => q.id)).toEqual([1, 2, 3, 4])
    expect(quotes.map(ticketLinkRank)).toEqual([3, 1, 2, 0])
  })

  it('filters each category', () => {
    const none = makeQuote({ id: 1 })
    const linked = makeQuote({ id: 2, ticket_link_status: 'novo', tiflux_ticket_number: '2' })
    const approved = makeQuote({ id: 3, ticket_link_status: 'aprovado', tiflux_ticket_number: '3' })
    const rejected = makeQuote({ id: 4, ticket_link_status: 'rejeitado', tiflux_ticket_number: '4' })
    const all = [none, linked, approved, rejected]
    expect(all.filter((q) => matchesTicketLinkFilter(q, 'none')).map((q) => q.id)).toEqual([1])
    expect(all.filter((q) => matchesTicketLinkFilter(q, 'linked')).map((q) => q.id)).toEqual([2])
    expect(all.filter((q) => matchesTicketLinkFilter(q, 'approved')).map((q) => q.id)).toEqual([3])
    expect(all.filter((q) => matchesTicketLinkFilter(q, 'rejected')).map((q) => q.id)).toEqual([4])
    expect(all.filter((q) => matchesTicketLinkFilter(q, 'all'))).toHaveLength(4)
  })

  it('groups quotes into ticket bands', () => {
    const quotes = [
      makeQuote({ id: 4, ticket_link_status: 'rejeitado', tiflux_ticket_number: '4' }),
      makeQuote({ id: 2, ticket_link_status: 'novo', tiflux_ticket_number: '2' }),
      makeQuote({ id: 5, ticket_link_status: 'rejeitado', tiflux_ticket_number: '5' }),
      makeQuote({ id: 3, ticket_link_status: 'aprovado', tiflux_ticket_number: '3' }),
      makeQuote({ id: 1 }),
    ]
    const groups = groupQuotesByTicketLink(quotes)
    expect(groups.none.map((q) => q.id)).toEqual([1])
    expect(groups.linked.map((q) => q.id)).toEqual([2])
    expect(groups.approved.map((q) => q.id)).toEqual([3])
    expect(groups.rejected.map((q) => q.id)).toEqual([5, 4])
  })

  it('builds refresh signature only for novo', () => {
    expect(ticketRefreshSignature(makeQuote({ id: 1 }))).toBeNull()
    expect(
      ticketRefreshSignature(
        makeQuote({ id: 2, ticket_link_status: 'novo', tiflux_ticket_number: '88' }),
      ),
    ).toBe('2:88')
    expect(
      ticketRefreshSignature(
        makeQuote({ id: 3, ticket_link_status: 'aprovado', tiflux_ticket_number: '88' }),
      ),
    ).toBeNull()
  })

  it('labels only stale follow-up', () => {
    expect(
      followupStaleLabel(makeQuote({ id: 1, followup_stale: true, followup_idle_days: 8 })),
    ).toBe('Sem retorno há 8 dias')
    expect(
      followupStaleLabel(makeQuote({ id: 2, followup_stale: false, followup_idle_days: 2 })),
    ).toBeNull()
  })
})
