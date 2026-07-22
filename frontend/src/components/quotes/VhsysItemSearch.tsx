import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Loader2, Plus, Search } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, type VhsysCatalogItem } from '@/api/client'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/cn'

type Props = {
  value: string
  disabled?: boolean
  placeholder?: string
  /** Valor unitário da linha — enviado ao cadastrar no VHSYS. */
  unitValue?: number
  /** Filtra catálogo pela categoria VHSYS selecionada na seção. */
  categoryId?: number | null
  onChange: (value: string) => void
  onSelect: (item: VhsysCatalogItem) => void
}

function money(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function matchesCatalog(item: VhsysCatalogItem, term: string): boolean {
  const q = term.trim().toLocaleLowerCase('pt-BR')
  if (!q) return true
  const name = item.name.toLocaleLowerCase('pt-BR')
  const code = (item.code ?? '').toLocaleLowerCase('pt-BR')
  return name.includes(q) || code.includes(q)
}

function exactNameMatch(items: VhsysCatalogItem[], term: string): VhsysCatalogItem | null {
  const needle = term.trim().toLocaleLowerCase('pt-BR')
  if (!needle) return null
  return items.find((i) => i.name.toLocaleLowerCase('pt-BR') === needle) ?? null
}

export function VhsysItemSearch({
  value,
  disabled,
  placeholder = 'Buscar produto/serviço VHSYS…',
  unitValue = 0,
  categoryId = null,
  onChange,
  onSelect,
}: Props) {
  const listId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), 200)
    return () => window.clearTimeout(t)
  }, [value])

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const catalogKey = ['vhsys-catalog-all', categoryId ?? 'all'] as const

  const catalog = useQuery({
    queryKey: catalogKey,
    queryFn: () => api.searchVhsysCatalog('', 0, categoryId),
    enabled: open && !disabled,
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  })

  const createMutation = useMutation({
    mutationFn: (name: string) =>
      api.createVhsysCatalogItem({
        name,
        unit_value: Number.isFinite(unitValue) ? Math.max(0, unitValue) : 0,
        tipo_produto: 'Servico',
        id_categoria: categoryId != null && categoryId > 0 ? categoryId : null,
      }),
    onSuccess: (data) => {
      const prev = queryClient.getQueryData<{
        items: VhsysCatalogItem[]
        query: string
        count?: number
      }>(catalogKey)
      const withoutDup = (prev?.items ?? []).filter((i) => i.id !== data.item.id)
      const nextItems = [...withoutDup, data.item].sort((a, b) =>
        a.name.localeCompare(b.name, 'pt-BR', { sensitivity: 'base' }),
      )
      queryClient.setQueryData(catalogKey, {
        items: nextItems,
        query: '',
        count: nextItems.length,
        category_id: categoryId ?? null,
      })
      onSelect(data.item)
      setOpen(false)
      if (data.created) {
        toast.success('Produto cadastrado no VHSYS e aplicado à linha.')
      } else {
        toast.message('Produto já existia no VHSYS — vinculado à linha.')
      }
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Falha ao cadastrar no VHSYS.')
    },
  })

  const allItems = catalog.data?.items ?? []
  const items = useMemo(
    () => allItems.filter((item) => matchesCatalog(item, debounced)),
    [allItems, debounced],
  )
  const total = catalog.data?.count ?? allItems.length
  const exact = useMemo(() => exactNameMatch(allItems, debounced), [allItems, debounced])
  const canCreate =
    Boolean(debounced.trim()) &&
    exact === null &&
    !catalog.isFetching &&
    !createMutation.isPending

  return (
    <div ref={rootRef} className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          disabled={disabled || createMutation.isPending}
          value={value}
          placeholder={placeholder}
          className="pl-8"
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            onChange(e.target.value)
            setOpen(true)
          }}
        />
        {(catalog.isFetching || createMutation.isPending) && (
          <Loader2 className="absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-muted-foreground" />
        )}
      </div>
      {open && !disabled && (
        <ul
          id={listId}
          role="listbox"
          className={cn(
            'absolute z-40 mt-1 max-h-80 w-full overflow-auto rounded-md border border-aurora-border',
            'bg-popover p-1 text-sm shadow-md',
          )}
        >
          {catalog.isError ? (
            <li className="px-2 py-2 text-xs text-aurora-danger">
              {catalog.error instanceof Error
                ? catalog.error.message
                : 'Falha ao buscar catálogo VHSYS'}
            </li>
          ) : catalog.isFetching && allItems.length === 0 ? (
            <li className="flex items-center gap-2 px-2 py-3 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Carregando catálogo VHSYS…
            </li>
          ) : (
            <>
              <li className="sticky top-0 z-10 bg-popover px-2 py-1.5 text-[11px] text-muted-foreground">
                {debounced.trim()
                  ? `${items.length} de ${total} no VHSYS`
                  : categoryId
                    ? `${total} itens da categoria`
                    : `${total} itens do VHSYS (via dupla)`}
                {catalog.isFetching ? ' · atualizando…' : null}
              </li>
              {canCreate ? (
                <li>
                  <button
                    type="button"
                    role="option"
                    className="flex w-full items-start gap-2 rounded-sm px-2 py-2 text-left text-aurora-brand-red hover:bg-accent"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => createMutation.mutate(debounced.trim())}
                  >
                    <Plus className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span className="min-w-0">
                      <span className="block font-medium">
                        Cadastrar no VHSYS: “{debounced.trim()}”
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        Via dupla — cria serviço e usa nesta linha
                        {unitValue > 0 ? ` (${money(unitValue)})` : ''}
                      </span>
                    </span>
                  </button>
                </li>
              ) : null}
              {items.length === 0 && !canCreate ? (
                <li className="px-2 py-2 text-xs text-muted-foreground">
                  Nenhum item encontrado
                  {categoryId ? ' nesta categoria' : ` em ${total} do VHSYS`}.
                </li>
              ) : (
                items.map((item) => (
                  <li key={`${item.kind}-${item.id}`}>
                    <button
                      type="button"
                      role="option"
                      className="flex w-full items-start justify-between gap-2 rounded-sm px-2 py-1.5 text-left hover:bg-accent"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => {
                        onSelect(item)
                        setOpen(false)
                      }}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{item.name}</span>
                        {item.code ? (
                          <span className="text-xs text-muted-foreground">Cód. {item.code}</span>
                        ) : null}
                      </span>
                      <span className="shrink-0 tabular-nums text-xs text-muted-foreground">
                        {money(item.unit_value)}
                      </span>
                    </button>
                  </li>
                ))
              )}
            </>
          )}
        </ul>
      )}
    </div>
  )
}
