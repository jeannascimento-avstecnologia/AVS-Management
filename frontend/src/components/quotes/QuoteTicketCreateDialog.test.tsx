import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { QuoteTicketCreateDialog } from '@/components/quotes/QuoteTicketCreateDialog'
import { makeQuote } from '@/test/quoteFixture'

const mocks = vi.hoisted(() => ({
  getQuoteTicketDefaults: vi.fn(),
  createQuoteTicket: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    api: {
      ...actual.api,
      getQuoteTicketDefaults: mocks.getQuoteTicketDefaults,
      createQuoteTicket: mocks.createQuoteTicket,
    },
  }
})

function renderDialog(quote = makeQuote({ id: 14, tiflux_client_id: 31116, title: 'Backup' })) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <QuoteTicketCreateDialog quote={quote} open onOpenChange={() => undefined} />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('QuoteTicketCreateDialog', () => {
  it('prefills comercial desk fields and creates ticket', async () => {
    mocks.getQuoteTicketDefaults.mockResolvedValue({
      desk_id: 36089,
      desk_name: 'Comercial',
      client_id: 31116,
      client_name: 'BCS',
      title: 'Backup',
      description: 'Orçamento M14',
      catalog_items: [{ id: 1, name: '1 - Triagem', area_name: 'Vendas', catalog_name: 'Comercial' }],
      default_catalog_item_id: 1,
      priorities: [{ id: 11, name: 'Baixa' }],
      default_priority_id: 11,
      requestors: [{ id: 77, name: 'Ana', email: 'ana@avs.com.br' }],
      default_requestor_id: 77,
    })
    mocks.createQuoteTicket.mockResolvedValue(
      makeQuote({ id: 14, tiflux_ticket_number: '65219', ticket_link_status: 'novo' }),
    )
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderDialog()
    expect(await screen.findByDisplayValue('Backup')).toBeInTheDocument()
    expect(screen.getByDisplayValue(/Comercial/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Criar e vincular' }))
    await waitFor(() =>
      expect(mocks.createQuoteTicket).toHaveBeenCalledWith(
        14,
        expect.objectContaining({
          title: 'Backup',
          services_catalogs_item_id: 1,
          priority_id: 11,
          requestor_id: 77,
        }),
      ),
    )
  })

  it('filters catalog and requestor by text', async () => {
    mocks.getQuoteTicketDefaults.mockResolvedValue({
      desk_id: 36089,
      desk_name: 'Comercial',
      client_id: 31116,
      client_name: 'BCS',
      title: 'Backup',
      description: 'Orçamento M14',
      catalog_items: [
        { id: 1, name: '1 - Triagem', area_name: 'Vendas', catalog_name: 'Comercial' },
        { id: 2, name: 'Contrato Renovado', area_name: 'Contratos', catalog_name: 'Comercial' },
      ],
      default_catalog_item_id: 1,
      priorities: [{ id: 11, name: 'Baixa' }],
      default_priority_id: 11,
      requestors: [
        { id: 77, name: 'Ana', email: 'ana@avs.com.br' },
        { id: 88, name: 'Bruno', email: 'bruno@avs.com.br' },
      ],
      default_requestor_id: 77,
    })
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderDialog()
    expect(await screen.findByLabelText('Catálogo')).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: '1 - Triagem · Vendas' })).not.toBeInTheDocument()
    await user.click(screen.getByLabelText('Catálogo'))
    expect(await screen.findByRole('option', { name: '1 - Triagem · Vendas' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Catálogo'), 'Renovado')
    expect(screen.queryByRole('option', { name: '1 - Triagem · Vendas' })).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Contrato Renovado · Contratos' })).toBeInTheDocument()
    await user.click(screen.getByLabelText('Solicitante'))
    await user.type(screen.getByLabelText('Solicitante'), 'Bru')
    expect(screen.queryByRole('option', { name: 'Ana' })).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Bruno' })).toBeInTheDocument()
  })

  it('asks for client when quote has no tiflux_client_id', async () => {
    renderDialog(makeQuote({ id: 14, tiflux_client_id: null }))
    expect(
      await screen.findByText(/Orçamento sem cliente TiFlux/i),
    ).toBeInTheDocument()
    expect(mocks.getQuoteTicketDefaults).not.toHaveBeenCalled()
  })
})
