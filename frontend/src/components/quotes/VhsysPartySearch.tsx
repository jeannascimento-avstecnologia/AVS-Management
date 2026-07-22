import { useEffect, useId, useRef, useState } from 'react'
import { Loader2, Search } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api, type VhsysParty } from '@/api/client'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/cn'

type Props = {
  value: string
  disabled?: boolean
  placeholder?: string
  onChange: (value: string) => void
  onSelect: (party: VhsysParty) => void
}

export function VhsysPartySearch({
  value,
  disabled,
  placeholder = 'Buscar no VHSYS…',
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
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const canSearch = debounced.trim().length >= 2

  const query = useQuery({
    queryKey: ['vhsys-parties', debounced],
    queryFn: () => api.searchVhsysParties(debounced, 20),
    enabled: open && !disabled && canSearch,
    staleTime: 30_000,
  })

  const parties = query.data?.parties ?? []

  return (
    <div ref={rootRef} className="relative">
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
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            onChange(e.target.value)
            setOpen(true)
          }}
        />
        {query.isFetching && (
          <Loader2 className="absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-muted-foreground" />
        )}
      </div>
      {open && !disabled && (
        <ul
          id={listId}
          role="listbox"
          className={cn(
            'absolute z-40 mt-1 max-h-56 w-full overflow-auto rounded-md border border-aurora-border',
            'bg-popover p-1 text-sm shadow-md',
          )}
        >
          {!canSearch ? (
            <li className="px-2 py-2 text-xs text-muted-foreground">
              Digite ao menos 2 caracteres para buscar no VHSYS.
            </li>
          ) : query.isError ? (
            <li className="px-2 py-2 text-xs text-aurora-danger">
              {query.error instanceof Error
                ? query.error.message
                : 'Falha ao buscar clientes VHSYS'}
            </li>
          ) : parties.length === 0 && !query.isFetching ? (
            <li className="px-2 py-2 text-xs text-muted-foreground">Nenhum resultado.</li>
          ) : (
            parties.map((party) => (
              <li key={party.id}>
                <button
                  type="button"
                  role="option"
                  className="flex w-full flex-col rounded-sm px-2 py-1.5 text-left hover:bg-accent"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onSelect(party)
                    setOpen(false)
                  }}
                >
                  <span className="truncate font-medium">{party.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {[party.fantasy_name, party.cnpj].filter(Boolean).join(' · ') ||
                      `VHSYS #${party.id}`}
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
