import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { ApiError, api, type QuoteRead } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { btnGreenClass, btnSecondaryClass, inputClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

const NONE = '__none__'

function parseOptionalId(raw: string): number | null {
  if (!raw || raw === NONE) return null
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed >= 1 ? parsed : null
}

type SearchOption = { id: number; label: string }

function TicketFieldSearch({
  id,
  label,
  value,
  noneLabel,
  options,
  onChange,
  placeholder,
}: {
  id: string
  label: string
  value: string
  noneLabel: string
  options: SearchOption[]
  onChange: (next: string) => void
  placeholder: string
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const selected = options.find((row) => String(row.id) === value)
  const selectedLabel = value === NONE || selected == null ? noneLabel : selected.label
  const rows = useMemo(
    () => [{ id: NONE, label: noneLabel }, ...options.map((row) => ({ id: String(row.id), label: row.label }))],
    [noneLabel, options],
  )
  const needle = query.trim().toLowerCase()
  const filtered = needle
    ? rows.filter((row) => row.label.toLowerCase().includes(needle))
    : rows

  useEffect(() => {
    if (!open) return
    const onDoc = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const pick = (next: string) => {
    onChange(next)
    setQuery('')
    setOpen(false)
  }

  return (
    <div ref={rootRef} className={cn('relative space-y-1', open && 'z-20')}>
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Input
          id={id}
          role="combobox"
          aria-expanded={open}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          value={open ? query : selectedLabel}
          placeholder={placeholder}
          autoComplete="off"
          className="pr-9"
          onFocus={() => setOpen(true)}
          onClick={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') event.preventDefault()
            if (event.key === 'ArrowDown') setOpen(true)
          }}
        />
        <ChevronDown
          className={cn(
            'pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-transform',
            open && 'rotate-180',
          )}
        />
        {open ? (
        <ul
          id={`${id}-list`}
          role="listbox"
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-72 overflow-y-auto rounded-lg border border-aurora-border bg-aurora-surface shadow-lg"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">Nenhum resultado.</li>
          ) : (
            filtered.map((item) => (
              <li key={item.id} role="presentation">
                <button
                  type="button"
                  role="option"
                  aria-selected={item.id === value}
                  className={cn(
                    'flex w-full min-w-0 truncate px-3 py-2 text-left text-sm',
                    item.id === value
                      ? 'bg-aurora-accent-muted text-aurora-fg'
                      : 'text-aurora-fg hover:bg-aurora-accent-muted/50',
                  )}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => pick(item.id)}
                >
                  {item.label}
                </button>
              </li>
            ))
          )}
        </ul>
        ) : null}
      </div>
    </div>
  )
}

type Props = {
  quote: QuoteRead | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function QuoteTicketCreateDialog({ quote, open, onOpenChange }: Props) {
  const resetKey = [open ? 'open' : 'closed', quote?.id ?? 0].join(':')
  return (
    <QuoteTicketCreateDialogBody
      key={resetKey}
      quote={quote}
      open={open}
      onOpenChange={onOpenChange}
    />
  )
}

function QuoteTicketCreateDialogBody({ quote, open, onOpenChange }: Props) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [catalogId, setCatalogId] = useState<string>(NONE)
  const [priorityId, setPriorityId] = useState<string>(NONE)
  const [requestorId, setRequestorId] = useState<string>(NONE)

  const defaultsQuery = useQuery({
    queryKey: ['quote-ticket-defaults', quote?.id],
    queryFn: () => api.getQuoteTicketDefaults(quote!.id),
    enabled: open && quote != null && quote.tiflux_client_id != null,
  })
  const defaults = defaultsQuery.data

  useEffect(() => {
    if (!defaults) return
    setTitle(defaults.title)
    setDescription(defaults.description)
    setCatalogId(
      defaults.default_catalog_item_id != null
        ? String(defaults.default_catalog_item_id)
        : NONE,
    )
    setPriorityId(
      defaults.default_priority_id != null ? String(defaults.default_priority_id) : NONE,
    )
    setRequestorId(
      defaults.default_requestor_id != null ? String(defaults.default_requestor_id) : NONE,
    )
  }, [defaults])

  const createMutation = useMutation({
    mutationFn: () => {
      if (!quote) throw new Error('Orçamento inválido.')
      const requestorIdResolved =
        parseOptionalId(requestorId) ?? defaults?.default_requestor_id ?? null
      const requestor =
        defaults?.requestors.find((row) => row.id === requestorIdResolved) ?? null
      const body = {
        title: title.trim(),
        description: description.trim(),
        services_catalogs_item_id:
          parseOptionalId(catalogId) ?? defaults?.default_catalog_item_id ?? null,
        priority_id: parseOptionalId(priorityId) ?? defaults?.default_priority_id ?? null,
        requestor_id: requestorIdResolved,
        requestor_name: requestor?.name ?? null,
        requestor_email: requestor?.email ?? null,
      }
      return api.createQuoteTicket(quote.id, body)
    },
    onSuccess: (updated) => {
      toast.success(`Ticket #${updated.tiflux_ticket_number} criado e vinculado`)
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      void queryClient.invalidateQueries({ queryKey: ['quote', updated.id] })
      onOpenChange(false)
    },
    onError: (err: Error) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(err.message || 'Orçamento já possui ticket.')
        return
      }
      toast.error(err.message || 'Falha ao criar ticket TiFlux')
    },
  })

  const missingClient = quote != null && quote.tiflux_client_id == null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex w-[calc(100vw-2rem)] min-w-0 max-w-2xl flex-col gap-4 overflow-visible overflow-y-visible p-6">
        <DialogHeader className="shrink-0 pr-6">
          <DialogTitle>Criar ticket</DialogTitle>
          <DialogDescription>
            Mesa Comercial
            {defaults?.desk_name ? ` · ${defaults.desk_name}` : ''}
            {quote ? ` · orçamento #${quote.id}` : ''}
          </DialogDescription>
        </DialogHeader>

        {missingClient ? (
          <p className="text-sm text-muted-foreground">
            Orçamento sem cliente TiFlux. Vincule o cliente no passo 1 para criar o ticket.
          </p>
        ) : defaultsQuery.isPending ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Carregando mesa, catálogo e prioridade…
          </div>
        ) : defaultsQuery.isError ? (
          <p className="text-sm text-aurora-danger">
            {defaultsQuery.error instanceof Error
              ? defaultsQuery.error.message
              : 'Não foi possível carregar os dados da mesa Comercial.'}
          </p>
        ) : (
          <form
            id="ticket-create-form"
            className="min-w-0 space-y-3 overflow-visible"
            onSubmit={(e) => {
              e.preventDefault()
              createMutation.mutate()
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="ticket-create-desk">Mesa</Label>
              <Input
                id="ticket-create-desk"
                value={
                  defaults?.desk_name
                    ? `${defaults.desk_name} (#${defaults.desk_id})`
                    : `Comercial (#${defaults?.desk_id ?? ''})`
                }
                disabled
                readOnly
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ticket-create-title">Título</Label>
              <Input
                id="ticket-create-title"
                value={title}
                maxLength={200}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ticket-create-description">Descrição</Label>
              <textarea
                id="ticket-create-description"
                rows={4}
                maxLength={8000}
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className={cn(inputClass, 'h-auto min-h-[88px] min-w-0 resize-y py-2.5')}
              />
            </div>
            <TicketFieldSearch
              id="ticket-create-catalog"
              label="Catálogo"
              value={catalogId}
              noneLabel="Sem catálogo"
              placeholder="Buscar catálogo"
              onChange={setCatalogId}
              options={(defaults?.catalog_items ?? []).map((item) => ({
                id: item.id,
                label: item.area_name ? `${item.name} · ${item.area_name}` : item.name,
              }))}
            />
            <div className="space-y-1">
              <Label>Prioridade</Label>
              <Select value={priorityId} onValueChange={setPriorityId}>
                <SelectTrigger className="w-full min-w-0" aria-label="Prioridade">
                  <SelectValue placeholder="Prioridade" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Padrão da mesa</SelectItem>
                  {(defaults?.priorities ?? []).map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      {item.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <TicketFieldSearch
              id="ticket-create-requestor"
              label="Solicitante"
              value={requestorId}
              noneLabel="Sem solicitante"
              placeholder="Buscar solicitante"
              onChange={setRequestorId}
              options={(defaults?.requestors ?? []).map((item) => ({
                id: item.id,
                label: item.name || item.email || `#${item.id}`,
              }))}
            />
          </form>
        )}
        {!missingClient && defaultsQuery.isSuccess ? (
          <DialogFooter className="shrink-0 gap-2 sm:gap-2">
            <Button
              type="button"
              className={btnSecondaryClass}
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              form="ticket-create-form"
              className={btnGreenClass}
              disabled={createMutation.isPending || !title.trim() || !description.trim()}
            >
              {createMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              Criar e vincular
            </Button>
          </DialogFooter>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
