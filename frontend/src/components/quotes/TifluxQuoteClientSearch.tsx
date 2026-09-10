import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { Loader2, Search } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api, type TifluxQuoteClient } from '@/api/client'
import { Input } from '@/components/ui/input'
import { formatCnpj } from '@/lib/format'
import { cn } from '@/lib/cn'

export type { TifluxQuoteClient }

type Props = {
  value: string
  disabled?: boolean
  placeholder?: string
  onChange: (value: string) => void
  onSelect: (client: TifluxQuoteClient) => void
}

export function TifluxQuoteClientSearch({
  value,
  disabled,
  placeholder = 'Buscar no TiFlux (CNPJ ou nome)…',
  onChange,
  onSelect,
}: Props) {
  const listId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), 300)
    return () => window.clearTimeout(t)
  }, [value])

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      const inside = Boolean(rootRef.current?.contains(e.target as Node))
      if (!inside) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const enabled = !disabled && debounced.trim().length >= 2
  const query = useQuery({
    queryKey: ['tiflux-quote-clients', debounced],
    queryFn: () => api.searchTifluxQuoteClients(debounced, 20),
    enabled,
    staleTime: 30_000,
  })

  const clients = query.data?.clients ?? []
  const showList = Boolean(open && enabled)

  // #region agent log
  const listRef = useRef<HTMLUListElement>(null)
  useLayoutEffect(() => {
    const header = document.querySelector('header')
    const ul = listRef.current
    const headerRect = header?.getBoundingClientRect()
    const ulRect = ul?.getBoundingClientRect()
    const ulStyle = ul ? window.getComputedStyle(ul) : null
    const rootStyle = rootRef.current ? window.getComputedStyle(rootRef.current) : null
    const mainEl = document.querySelector('main')
    const mainStyle = mainEl ? window.getComputedStyle(mainEl) : null
    const overlapTopbar = Boolean(
      headerRect &&
        ulRect &&
        ulRect.top < headerRect.bottom &&
        ulRect.bottom > headerRect.top,
    )
    fetch('http://127.0.0.1:7624/ingest/4fbad495-1d4e-4120-8a74-d59ccbb75445', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '95d267' },
      body: JSON.stringify({
        sessionId: '95d267',
        runId: 'pre-fix',
        hypothesisId: 'A',
        location: 'TifluxQuoteClientSearch.tsx:layout',
        message: 'client-search layout',
        data: {
          showList,
          open,
          enabled,
          clientsLen: clients.length,
          valueLen: value.trim().length,
          rootZ: rootStyle?.zIndex ?? null,
          ulPosition: ulStyle?.position ?? null,
          ulZ: ulStyle?.zIndex ?? null,
          ulTransform: ulStyle?.transform ?? null,
          mainTransform: mainStyle?.transform ?? null,
          mainZ: mainStyle?.zIndex ?? null,
          overlapTopbar,
          ulTop: ulRect ? Math.round(ulRect.top) : null,
          ulHeight: ulRect ? Math.round(ulRect.height) : null,
          headerBottom: headerRect ? Math.round(headerRect.bottom) : null,
          headerZ: header ? window.getComputedStyle(header).zIndex : null,
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {})
  }, [showList, open, enabled, clients.length, value])
  // #endregion

  return (
    <div ref={rootRef} className={cn('relative', showList && 'z-50')}>
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          disabled={disabled}
          value={value}
          placeholder={placeholder}
          className="pl-8"
          onFocus={() => {
            setOpen(true)
          }}
          onChange={(e) => {
            onChange(e.target.value)
            setOpen(true)
          }}
        />
        {query.isFetching && (
          <Loader2 className="absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-muted-foreground" />
        )}
      </div>
      {showList && (
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          className={cn(
            'relative z-50 mt-1 max-h-64 w-full overflow-auto rounded-md border border-aurora-border',
            'bg-popover p-1 text-sm shadow-md',
          )}
        >
          {query.isError ? (
            <li className="px-2 py-2 text-xs text-aurora-danger">
              {query.error instanceof Error
                ? query.error.message
                : 'Falha ao buscar clientes TiFlux'}
            </li>
          ) : clients.length === 0 && !query.isFetching ? (
            <li className="px-2 py-2 text-xs text-muted-foreground">
              Nenhum cliente encontrado no TiFlux.
            </li>
          ) : (
            clients.map((client) => (
              <li key={client.id}>
                <button
                  type="button"
                  role="option"
                  className="flex w-full flex-col items-start gap-0.5 rounded-sm px-2 py-1.5 text-left hover:bg-accent"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onSelect(client)
                    setOpen(false)
                  }}
                >
                  <span className="font-medium">{client.name}</span>
                  <span className="text-xs text-muted-foreground">
                    TiFlux #{client.id}
                    {client.cnpj ? ` · ${formatCnpj(client.cnpj)}` : ' · sem CNPJ'}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  )
}
