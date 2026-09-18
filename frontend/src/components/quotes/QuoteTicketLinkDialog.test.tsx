import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { QuoteTicketLinkDialog } from '@/components/quotes/QuoteTicketLinkDialog'
import { makeQuote } from '@/test/quoteFixture'

const mocks = vi.hoisted(() => ({
  getTifluxTicket: vi.fn(),
  listTifluxTickets: vi.fn(),
  linkQuoteTicket: vi.fn(),
  unlinkQuoteTicket: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    api: {
      ...actual.api,
      getTifluxTicket: mocks.getTifluxTicket,
      listTifluxTickets: mocks.listTifluxTickets,
      linkQuoteTicket: mocks.linkQuoteTicket,
      unlinkQuoteTicket: mocks.unlinkQuoteTicket,
    },
  }
})

function renderDialog(quote = makeQuote({ id: 5 })) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <QuoteTicketLinkDialog quote={quote} open onOpenChange={() => undefined} />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('QuoteTicketLinkDialog', () => {
  it('lists commercial-desk tickets and links the selected one', async () => {
    mocks.listTifluxTickets.mockResolvedValue({
      tickets: [
        {
          ticket_number: '5790',
          subject: 'Proposta',
          client_name: 'Cliente AVS',
          status: 'Opened',
          catalog: null,
          closed: false,
          suggested_link_status: 'novo',
        },
      ],
      client_id: 1,
      desk_id: 36089,
    })
    mocks.linkQuoteTicket.mockResolvedValue(
      makeQuote({
        id: 5,
        tiflux_ticket_number: '5790',
        ticket_link_status: 'novo',
      }),
    )
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderDialog()
    expect(await screen.findByLabelText('Selecionar ticket 5790')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Vincular' }))
    await waitFor(() => expect(mocks.linkQuoteTicket).toHaveBeenCalledWith(5, '5790'))
  })

  it('searches and links a ticket by number', async () => {
    mocks.listTifluxTickets.mockResolvedValue({ tickets: [], client_id: 1, desk_id: 36089 })
    mocks.getTifluxTicket.mockResolvedValue({
      ticket_number: '5790',
      subject: 'Proposta',
      client_name: 'Cliente AVS',
      status: 'Opened',
      catalog: null,
      closed: false,
      suggested_link_status: 'novo',
    })
    mocks.linkQuoteTicket.mockResolvedValue(
      makeQuote({
        id: 5,
        tiflux_ticket_number: '5790',
        ticket_link_status: 'novo',
      }),
    )
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderDialog()
    await user.type(screen.getByLabelText('Outro número'), '5790')
    await user.click(screen.getByRole('button', { name: 'Buscar' }))
    expect(await screen.findByText('Proposta')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Vincular' }))
    await waitFor(() => expect(mocks.linkQuoteTicket).toHaveBeenCalledWith(5, '5790'))
  })

  it('unlinks an existing ticket', async () => {
    mocks.unlinkQuoteTicket.mockResolvedValue(makeQuote({ id: 5 }))
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderDialog(
      makeQuote({
        id: 5,
        tiflux_ticket_number: '5790',
        ticket_link_status: 'novo',
        ticket_link_snapshot: {
          ticket_number: '5790',
          subject: 'Proposta',
          client_name: 'Cliente AVS',
          status: 'Opened',
          catalog: null,
          closed: false,
          suggested_link_status: 'novo',
        },
      }),
    )
    expect(screen.getAllByText('Proposta').length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: 'Desvincular' }))
    await waitFor(() => expect(mocks.unlinkQuoteTicket).toHaveBeenCalledWith(5))
  })
})
