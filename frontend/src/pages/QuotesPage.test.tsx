import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { QuotesPage } from '@/pages/QuotesPage'
import { makeQuote } from '@/test/quoteFixture'
import type { QuoteRead } from '@/api/client'

const mocks = vi.hoisted(() => ({
  listQuotes: vi.fn(),
  refreshTicketLinks: vi.fn(),
  searchTifluxQuoteClients: vi.fn(),
  createQuote: vi.fn(),
  deleteQuote: vi.fn(),
  submitQuote: vi.fn(),
  generateQuotePdf: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    api: {
      ...actual.api,
      listQuotes: mocks.listQuotes,
      refreshTicketLinks: mocks.refreshTicketLinks,
      searchTifluxQuoteClients: mocks.searchTifluxQuoteClients,
      createQuote: mocks.createQuote,
      deleteQuote: mocks.deleteQuote,
      submitQuote: mocks.submitQuote,
      generateQuotePdf: mocks.generateQuotePdf,
    },
  }
})

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <QuotesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function clientNameOrder(): string[] {
  return screen
    .getAllByText(/^Empresa /)
    .filter((el) => el.tagName === 'P')
    .map((el) => el.textContent ?? '')
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('QuotesPage ticket link', () => {
  it('shows associate button after PDF when quote has no ticket', async () => {
    mocks.listQuotes.mockResolvedValue({ quotes: [makeQuote({ id: 11 })] })
    mocks.refreshTicketLinks.mockResolvedValue({ updated: [], failures: [] })
    renderPage()
    expect(await screen.findByLabelText('Gerar PDF orçamento 11')).toBeInTheDocument()
    const associate = await screen.findByLabelText('Associar ticket ao orçamento 11')
    const pdf = screen.getByLabelText('Gerar PDF orçamento 11')
    expect(associate.compareDocumentPosition(pdf) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy()
  })

  it('renders ticket chip by status', async () => {
    mocks.listQuotes.mockResolvedValue({
      quotes: [
        makeQuote({
          id: 12,
          tiflux_ticket_number: '88',
          ticket_link_status: 'aprovado',
        }),
      ],
    })
    mocks.refreshTicketLinks.mockResolvedValue({ updated: [], failures: [] })
    renderPage()
    expect(await screen.findByLabelText('Ticket 88')).toBeInTheDocument()
    expect(screen.getByText('#88')).toBeInTheDocument()
    expect(screen.getByText('Aprovado')).toBeInTheDocument()
    expect(screen.queryByLabelText('Associar ticket ao orçamento 12')).not.toBeInTheDocument()
  })

  it('orders quotes by ticket link rank', async () => {
    const quotes: QuoteRead[] = [
      makeQuote({ id: 4, client_name: 'Empresa Rejeitada', lead_temperature: 'frio', ticket_link_status: 'rejeitado', tiflux_ticket_number: '4' }),
      makeQuote({ id: 2, client_name: 'Empresa Nova', lead_temperature: 'frio', ticket_link_status: 'novo', tiflux_ticket_number: '2' }),
      makeQuote({ id: 3, client_name: 'Empresa Aprovada', lead_temperature: 'frio', ticket_link_status: 'aprovado', tiflux_ticket_number: '3' }),
      makeQuote({ id: 1, client_name: 'Empresa Sem Vinculo', lead_temperature: 'frio' }),
    ]
    mocks.listQuotes.mockResolvedValue({ quotes })
    mocks.refreshTicketLinks.mockResolvedValue({ updated: [], failures: [] })
    renderPage()
    await screen.findByText('Empresa Sem Vinculo')
    expect(clientNameOrder()).toEqual([
      'Empresa Sem Vinculo',
      'Empresa Nova',
      'Empresa Aprovada',
      'Empresa Rejeitada',
    ])
  })

  it('filters by ticket link category', async () => {
    mocks.listQuotes.mockResolvedValue({
      quotes: [
        makeQuote({ id: 1, client_name: 'Empresa Sem Vinculo', lead_temperature: 'frio' }),
        makeQuote({
          id: 2,
          client_name: 'Empresa Com Ticket',
          lead_temperature: 'frio',
          ticket_link_status: 'novo',
          tiflux_ticket_number: '2',
        }),
      ],
    })
    mocks.refreshTicketLinks.mockResolvedValue({ updated: [], failures: [] })
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage()
    await screen.findByText('Empresa Sem Vinculo')
    await user.click(screen.getByLabelText('Filtrar por vínculo de ticket'))
    await user.click(await screen.findByRole('option', { name: 'Sem ticket' }))
    expect(screen.getByText('Empresa Sem Vinculo')).toBeInTheDocument()
    expect(screen.queryByText('Empresa Com Ticket')).not.toBeInTheDocument()
  })

  it('refreshes novo tickets once', async () => {
    mocks.listQuotes.mockResolvedValue({
      quotes: [
        makeQuote({ id: 9, ticket_link_status: 'novo', tiflux_ticket_number: '77' }),
      ],
    })
    mocks.refreshTicketLinks.mockResolvedValue({ updated: [], failures: [] })
    renderPage()
    await waitFor(() => expect(mocks.refreshTicketLinks).toHaveBeenCalledTimes(1))
    expect(mocks.refreshTicketLinks).toHaveBeenCalledWith([9])
  })

  it('does not refresh when there is no novo ticket', async () => {
    mocks.listQuotes.mockResolvedValue({
      quotes: [
        makeQuote({ id: 9, ticket_link_status: 'aprovado', tiflux_ticket_number: '77' }),
      ],
    })
    mocks.refreshTicketLinks.mockResolvedValue({ updated: [], failures: [] })
    renderPage()
    await screen.findByLabelText('Ticket 77')
    await waitFor(() => expect(mocks.listQuotes).toHaveBeenCalled())
    expect(mocks.refreshTicketLinks).not.toHaveBeenCalled()
  })
})
