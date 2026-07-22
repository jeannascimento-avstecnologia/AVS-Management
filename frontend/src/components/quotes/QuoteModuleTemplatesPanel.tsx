import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  Boxes,
  Loader2,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  api,
  type QuoteModuleTemplateRead,
  type QuoteTemplateLine,
} from '@/api/client'
import { VhsysItemSearch } from '@/components/quotes/VhsysItemSearch'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { btnAccentClass, btnDangerClass, btnSecondaryClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

const NONE = '__none__'

type DraftLine = {
  localKey: string
  name: string
  qty: string
  unit_value: string
}

export type QuoteModuleTemplatesPanelProps = {
  /** Prefill lines when opening “Novo bloco”. */
  seedLines?: QuoteTemplateLine[]
  seedTitle?: string
  seedShowLabor?: boolean
  /** Compact chrome for dialog embed (dialog title already says Biblioteca). */
  embedded?: boolean
}

function newLocalKey(): string {
  return `mtl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function emptyLine(): DraftLine {
  return { localKey: newLocalKey(), name: '', qty: '1', unit_value: '0' }
}

function linesFromTemplate(template: QuoteModuleTemplateRead): DraftLine[] {
  if (template.lines.length === 0) return [emptyLine()]
  return template.lines.map((line) => ({
    localKey: newLocalKey(),
    name: line.name,
    qty: String(line.qty),
    unit_value: String(line.unit_value),
  }))
}

function draftFromSeed(seed: QuoteTemplateLine[] | undefined): DraftLine[] {
  if (!seed || seed.length === 0) return [emptyLine()]
  return seed.map((line) => ({
    localKey: newLocalKey(),
    name: line.name,
    qty: String(line.qty),
    unit_value: String(line.unit_value),
  }))
}

function parseNonNegativeNumber(raw: string): number {
  const n = Number(raw.replace(',', '.'))
  return Number.isFinite(n) && n >= 0 ? n : 0
}

function lineHasPartialInput(row: DraftLine): boolean {
  const qty = row.qty.trim()
  const unit = row.unit_value.trim()
  return (qty !== '' && qty !== '1') || (unit !== '' && unit !== '0')
}

function parseLines(draft: DraftLine[]): QuoteTemplateLine[] | null {
  const lines: QuoteTemplateLine[] = []
  for (let i = 0; i < draft.length; i++) {
    const row = draft[i]
    const name = row.name.trim()
    if (!name) {
      if (lineHasPartialInput(row)) {
        toast.error(`Linha ${i + 1}: informe o item`)
        return null
      }
      // allow trailing empty rows when other lines exist
      continue
    }
    const qty = Number(row.qty.replace(',', '.'))
    const unitValue = Number(row.unit_value.replace(',', '.'))
    if (!Number.isFinite(qty) || qty <= 0) {
      toast.error(`Linha ${i + 1}: quantidade inválida.`)
      return null
    }
    if (!Number.isFinite(unitValue) || unitValue < 0) {
      toast.error(`Linha ${i + 1}: valor unitário inválido.`)
      return null
    }
    lines.push({ name, qty, unit_value: unitValue, sort_order: lines.length })
  }
  return lines
}

function updateLine(
  prev: DraftLine[],
  localKey: string,
  patch: Partial<Omit<DraftLine, 'localKey'>>,
): DraftLine[] {
  return prev.map((row) => (row.localKey === localKey ? { ...row, ...patch } : row))
}

function formatBrl(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function displayBlockName(template: QuoteModuleTemplateRead): string {
  const title = template.title.trim()
  if (title) return title
  const name = template.name.trim()
  if (name) return name
  return 'Bloco sem nome'
}

export function QuoteModuleTemplatesPanel({
  seedLines,
  seedTitle,
  seedShowLabor = false,
  embedded = false,
}: QuoteModuleTemplatesPanelProps) {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [blockName, setBlockName] = useState('')
  const [showLabor, setShowLabor] = useState(false)
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()])
  const [categoryId, setCategoryId] = useState<number | null>(null)

  const listQuery = useQuery({
    queryKey: ['quote-module-templates'],
    queryFn: () => api.listQuoteModuleTemplates(),
  })

  const categoriesQuery = useQuery({
    queryKey: ['vhsys-categories'],
    queryFn: () => api.listVhsysCategories(),
    staleTime: 10 * 60_000,
    enabled: showForm,
  })
  const categories = categoriesQuery.data?.categories ?? []
  const categorySelectValue = categoryId != null ? String(categoryId) : NONE
  const templates = listQuery.data?.templates ?? []

  function resetForm() {
    setEditingId(null)
    setBlockName('')
    setShowLabor(false)
    setLines([emptyLine()])
    setCategoryId(null)
  }

  function openCreate() {
    setEditingId(null)
    setBlockName(seedTitle?.trim() || '')
    setShowLabor(seedShowLabor)
    setCategoryId(null)
    setLines(draftFromSeed(seedLines))
    setShowForm(true)
  }

  function openEdit(template: QuoteModuleTemplateRead) {
    setEditingId(template.id)
    setBlockName(displayBlockName(template))
    setShowLabor(template.show_labor)
    setLines(linesFromTemplate(template))
    setCategoryId(null)
    setShowForm(true)
  }

  const createMutation = useMutation({
    mutationFn: (payload: {
      name: string
      title: string
      show_labor: boolean
      lines: QuoteTemplateLine[]
    }) => api.createQuoteModuleTemplate(payload),
    onSuccess: (created) => {
      toast.success(`Bloco “${created.title || created.name}” criado`)
      resetForm()
      setShowForm(false)
      void queryClient.invalidateQueries({ queryKey: ['quote-module-templates'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao criar bloco')
    },
  })

  const updateMutation = useMutation({
    mutationFn: (payload: {
      id: number
      name: string
      title: string
      show_labor: boolean
      lines: QuoteTemplateLine[]
    }) =>
      api.updateQuoteModuleTemplate(payload.id, {
        name: payload.name,
        title: payload.title,
        show_labor: payload.show_labor,
        lines: payload.lines,
      }),
    onSuccess: (updated) => {
      toast.success(`Bloco “${updated.title || updated.name}” atualizado`)
      resetForm()
      setShowForm(false)
      void queryClient.invalidateQueries({ queryKey: ['quote-module-templates'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao atualizar bloco')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteQuoteModuleTemplate(id),
    onSuccess: () => {
      toast.success('Bloco removido')
      void queryClient.invalidateQueries({ queryKey: ['quote-module-templates'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao remover bloco')
    },
  })

  const isSaving = createMutation.isPending || updateMutation.isPending

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = blockName.trim()
    if (!trimmed) {
      toast.error('Informe o nome do bloco.')
      return
    }
    // Always persist name === title (human label only; no custom_<uuid> in UI).
    const name = trimmed
    const title = trimmed
    const parsed = parseLines(lines)
    if (parsed == null) return
    if (editingId != null) {
      updateMutation.mutate({
        id: editingId,
        name,
        title,
        show_labor: showLabor,
        lines: parsed,
      })
      return
    }
    createMutation.mutate({
      name,
      title,
      show_labor: showLabor,
      lines: parsed,
    })
  }

  return (
    <div className="space-y-4">
      {!embedded && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Boxes className="h-4 w-4 shrink-0 text-aurora-info" aria-hidden />
              <h2 className="text-lg font-semibold tracking-tight text-aurora-fg">
                Biblioteca de blocos
              </h2>
            </div>
            <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
              Crie blocos reutilizáveis e use Inserir bloco no orçamento.
            </p>
          </div>
          <Button type="button" className={cn(btnAccentClass, 'shrink-0')} onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Novo bloco
          </Button>
        </div>
      )}

      {embedded && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground sm:text-sm">
            Gerencie blocos e use Inserir bloco no orçamento.
          </p>
          <Button type="button" className={cn(btnAccentClass, 'shrink-0')} onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Novo bloco
          </Button>
        </div>
      )}

      <div className="hub-panel-enter space-y-4 rounded-xl border border-aurora-info/35 bg-gradient-to-br from-aurora-info/10 to-aurora-surface p-3 sm:p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Boxes className="h-4 w-4 text-aurora-info" aria-hidden />
          <span className="text-sm font-semibold text-aurora-info">Blocos</span>
          <Badge
            className="border border-aurora-info/40 bg-aurora-info/15 text-aurora-info"
            variant="outline"
          >
            {templates.length} bloco{templates.length === 1 ? '' : 's'}
          </Badge>
        </div>

        {showForm && (
          <form
            onSubmit={handleSubmit}
            className="aurora-motion space-y-4 rounded-xl border border-aurora-border bg-aurora-surface p-4 shadow-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-aurora-border/70 pb-3">
              <p className="text-sm font-semibold text-aurora-fg">
                {editingId != null ? 'Editar bloco' : 'Novo bloco'}
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="mod-template-name">Nome do bloco</Label>
              <Input
                id="mod-template-name"
                value={blockName}
                onChange={(e) => setBlockName(e.target.value)}
                placeholder="Ex.: Licenças"
                maxLength={200}
                required
                className="focus-visible:ring-aurora-accent"
              />
            </div>

            <label className="flex items-center gap-2 text-sm text-aurora-fg">
              <input
                type="checkbox"
                checked={showLabor}
                onChange={(e) => setShowLabor(e.target.checked)}
                className="h-4 w-4 rounded border-aurora-border"
              />
              Exibir mão de obra neste bloco
            </label>

            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Categoria VHSYS</Label>
              <Select
                value={categorySelectValue}
                disabled={categoriesQuery.isFetching}
                onValueChange={(v) => {
                  if (v === NONE) {
                    setCategoryId(null)
                    return
                  }
                  const id = Number(v)
                  setCategoryId(Number.isFinite(id) && id > 0 ? id : null)
                }}
              >
                <SelectTrigger aria-label="Categoria VHSYS do bloco">
                  <SelectValue placeholder="Todas as categorias" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Todas as categorias</SelectItem>
                  {categories.map((cat) => (
                    <SelectItem key={cat.id} value={String(cat.id)}>
                      {cat.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <fieldset className="space-y-3 overflow-visible">
              <legend className="mb-1 text-sm font-medium text-aurora-fg">
                Itens default (opcional)
              </legend>
              <ul className="space-y-3">
                {lines.map((line, idx) => (
                  <li
                    key={line.localKey}
                    className={cn(
                      'aurora-motion grid gap-2 overflow-visible rounded-xl border border-aurora-border bg-aurora-surface-2/40 p-3',
                      'sm:grid-cols-[1fr_5rem_7rem_auto]',
                    )}
                  >
                    <div className="space-y-1 overflow-visible">
                      <Label className="text-xs text-muted-foreground">Item (busca VHSYS)</Label>
                      <VhsysItemSearch
                        value={line.name}
                        categoryId={categoryId}
                        unitValue={parseNonNegativeNumber(line.unit_value)}
                        placeholder={`Item ${idx + 1} — buscar VHSYS…`}
                        onChange={(nextName) =>
                          setLines((prev) => updateLine(prev, line.localKey, { name: nextName }))
                        }
                        onSelect={(catalog) =>
                          setLines((prev) =>
                            updateLine(prev, line.localKey, {
                              name: catalog.name,
                              unit_value:
                                catalog.unit_value > 0
                                  ? String(catalog.unit_value)
                                  : line.unit_value,
                            }),
                          )
                        }
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Qtd</Label>
                      <Input
                        value={line.qty}
                        onChange={(e) =>
                          setLines((prev) =>
                            updateLine(prev, line.localKey, { qty: e.target.value }),
                          )
                        }
                        inputMode="decimal"
                        aria-label={`Qtd linha ${idx + 1}`}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Valor unit.</Label>
                      <Input
                        value={line.unit_value}
                        onChange={(e) =>
                          setLines((prev) =>
                            updateLine(prev, line.localKey, { unit_value: e.target.value }),
                          )
                        }
                        inputMode="decimal"
                        placeholder="0"
                        aria-label={`Valor unitário linha ${idx + 1}`}
                      />
                    </div>
                    <div className="flex items-end justify-end">
                      <Button
                        type="button"
                        size="sm"
                        className={cn(btnDangerClass, 'h-8 px-2')}
                        disabled={lines.length <= 1}
                        onClick={() =>
                          setLines((prev) => prev.filter((row) => row.localKey !== line.localKey))
                        }
                        aria-label={`Remover linha ${idx + 1}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
              <Button
                type="button"
                size="sm"
                className={btnSecondaryClass}
                onClick={() => setLines((prev) => [...prev, emptyLine()])}
              >
                <Plus className="h-4 w-4" />
                Item
              </Button>
            </fieldset>

            <div className="flex justify-end gap-2 border-t border-aurora-border/70 pt-3">
              <Button
                type="button"
                className={btnSecondaryClass}
                disabled={isSaving}
                onClick={() => {
                  resetForm()
                  setShowForm(false)
                }}
              >
                Cancelar
              </Button>
              <Button type="submit" className={btnAccentClass} disabled={isSaving}>
                {isSaving ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Salvando…
                  </>
                ) : editingId != null ? (
                  'Salvar alterações'
                ) : (
                  'Criar bloco'
                )}
              </Button>
            </div>
          </form>
        )}

        {listQuery.isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {listQuery.error instanceof Error
                ? listQuery.error.message
                : 'Não foi possível carregar a biblioteca de blocos.'}
            </AlertDescription>
          </Alert>
        )}

        {listQuery.isPending && (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full rounded-xl" />
            <Skeleton className="h-16 w-full rounded-xl" />
          </div>
        )}

        {!listQuery.isPending && !listQuery.isError && templates.length === 0 && !showForm && (
          <EmptyState
            icon={Boxes}
            title="Nenhum bloco na biblioteca"
            description="Crie o primeiro bloco aqui; depois use Inserir bloco no orçamento."
            action={{ label: 'Criar primeiro bloco', onClick: openCreate }}
          />
        )}

        {!listQuery.isPending && templates.length > 0 && (
          <ul
            className={cn(
              'space-y-2',
              embedded && !showForm && 'max-h-[36vh] overflow-y-auto pr-1',
            )}
          >
            {templates.map((template) => {
              const label = displayBlockName(template)
              const itemCount = template.lines.length
              const lineSum = template.lines.reduce((s, l) => s + l.qty * l.unit_value, 0)
              return (
                <li key={template.id}>
                  <div
                    className={cn(
                      'aurora-motion group flex flex-col gap-3 rounded-xl border border-aurora-border bg-aurora-surface p-3.5 shadow-sm',
                      'hover:-translate-y-0.5 hover:border-aurora-info/45 hover:shadow-md',
                      'sm:flex-row sm:items-center sm:justify-between',
                    )}
                  >
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate text-sm font-semibold text-aurora-fg">
                          {label}
                        </span>
                        {template.show_labor ? (
                          <Badge variant="outline" className="text-[10px]">
                            MO
                          </Badge>
                        ) : null}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {itemCount} {itemCount === 1 ? 'item' : 'itens'}
                        {lineSum > 0 ? ` · ${formatBrl(lineSum)}` : ''}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        className={btnSecondaryClass}
                        onClick={() => openEdit(template)}
                        aria-label={`Editar bloco ${label}`}
                      >
                        <Pencil className="h-4 w-4" />
                        Editar
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        className={btnDangerClass}
                        disabled={deleteMutation.isPending}
                        onClick={() => {
                          if (window.confirm(`Remover bloco “${label}”?`)) {
                            deleteMutation.mutate(template.id)
                          }
                        }}
                        aria-label={`Remover bloco ${label}`}
                      >
                        {deleteMutation.isPending && deleteMutation.variables === template.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                        Remover
                      </Button>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
