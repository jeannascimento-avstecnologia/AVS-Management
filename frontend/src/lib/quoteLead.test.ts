import { describe, expect, it } from 'vitest'
import { countByLead, hotPendingQuotes, sumByLead } from '@/lib/quoteLead'
import { makeQuote } from '@/test/quoteFixture'

describe('quoteLead ticket link exclusion', () => {
  it('ignores approved and rejected ticket links', () => {
    const quotes = [
      makeQuote({ id: 1, lead_temperature: 'quente' }),
      makeQuote({
        id: 2,
        lead_temperature: 'quente',
        ticket_link_status: 'aprovado',
        tiflux_ticket_number: '2',
      }),
      makeQuote({
        id: 3,
        lead_temperature: 'quente',
        ticket_link_status: 'rejeitado',
        tiflux_ticket_number: '3',
      }),
      makeQuote({
        id: 4,
        lead_temperature: 'quente',
        ticket_link_status: 'novo',
        tiflux_ticket_number: '4',
      }),
    ]
    expect(countByLead(quotes).quente).toBe(2)
    expect(sumByLead(quotes).quente).toBe(200)
    expect(hotPendingQuotes(quotes).map((q) => q.id)).toEqual([1, 4])
  })
})
