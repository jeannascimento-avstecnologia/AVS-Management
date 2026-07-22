import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  Layers,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  Wrench,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  api,
  type QuoteSection,
  type QuoteTemplateLine,
  type QuoteTemplateRead,
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

const PRESET_SECTIONS = ['implantacao', 'mensalidade'] as const

/** Human-readable section title — never expose raw module ids (`custom_<uuid>`). */
function resolveSectionLabel(section: string, overrideTitle?: string): string {
  const trimmed = overrideTitle?.trim()
  if (trimmed) return trimmed
  if (section === 'implantacao') return 'Implantação'
  if (section === 'mensalidade') return 'Mensalidade'
  return 'Módulo'
}

type SectionMeta = {
  label: string
  icon: typeof Wrench
  tabActive: string
  panel: string
  chip: string
  accentText: string
}

const SECTION_META_PRESET: Record<(typeof PRESET_SECTIONS)[number], SectionMeta> = {
  implantacao: {
    label: 'Implantação',
    icon: Wrench,
    tabActive:
      'border-aurora-accent bg-aurora-accent text-white shadow-sm ring-2 ring-aurora-accent/30',
    panel: 'border-aurora-accent/35 bg-gradient-to-br from-aurora-accent-muted/40 to-aurora-surface',
    chip: 'border-aurora-accent/40 bg-aurora-accent-muted text-aurora-accent',
    accentText: 'text-aurora-accent',
  },
  mensalidade: {
    label: 'Mensalidade',
    icon: RefreshCw,
    tabActive:
      'border-aurora-brand-red bg-aurora-brand-red text-white shadow-sm ring-2 ring-aurora-brand-red/30',
    panel:
      'border-aurora-brand-red/35 bg-gradient-to-br from-aurora-brand-red/10 to-aurora-surface',
    chip: 'border-aurora-brand-red/40 bg-aurora-brand-red/10 text-aurora-brand-red',
    accentText: 'text-aurora-brand-red',
  },
}

const CUSTOM_META: SectionMeta = {
  label: 'Módulo',
  icon: Layers,
  tabActive:
    'border-aurora-info bg-aurora-info text-white shadow-sm ring-2 ring-aurora-info/30',
  panel: 'border-aurora-info/35 bg-gradient-to-br from-aurora-info/10 to-aurora-surface',
  chip: 'border-aurora-info/40 bg-aurora-info/15 text-aurora-info',
  accentText: 'text-aurora-info',
}

function sectionMeta(section: string, overrideTitle?: string): SectionMeta {
  const label = resolveSectionLabel(section, overrideTitle)
  if (section === 'implantacao' || section === 'mensalidade') {
    return { ...SECTION_META_PRESET[section], label }
  }
  return { ...CUSTOM_META, label }
}

const NONE = '__none__'

type DraftLine = {
  localKey: string
  name: string
  qty: string
  unit_value: string
}

export type QuoteTemplatesPanelProps = {
  /** When set: opens on that section tab (still shows both). */
  section?: QuoteSection
  /** Human title for custom modules (UI only; `section` stays the API key). */
  sectionTitle?: string
  /** Prefill lines when opening “Novo modelo”. */
  seedLines?: QuoteTemplateLine[]
  /** Compact chrome for dialog embed. */
  embedded?: boolean
}

function newLocalKey(): string {
  return `tl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function emptyLine(): DraftLine {
  return { localKey: newLocalKey(), name: '', qty: '1', unit_value: '0' }
}

function linesFromTemplate(template: QuoteTemplateRead): DraftLine[] {
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

function parseLines(draft: DraftLine[]): QuoteTemplateLine[] | null {
  const lines: QuoteTemplateLine[] = []
  for (let i = 0; i < draft.length; i++) {
    const row = draft[i]
    const name = row.name.trim()
    if (!name) {
      toast.error(`Linha ${i + 1}: informe o nome.`)
      return null
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
    lines.push({ name, qty, unit_value: unitValue, sort_order: i })
  }
  if (lines.length === 0) {
    toast.error('Adicione ao menos uma linha.')
    return null
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

export function QuoteTemplatesPanel({
  section: initialSection,
  sectionTitle,
  seedLines,
  embedded = false,
}: QuoteTemplatesPanelProps) {
  const queryClient = useQueryClient()
  const [activeSection, setActiveSection] = useState<QuoteSection>(
    initialSection ?? 'implantacao',
  )
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()])
  const [categoryId, setCategoryId] = useState<number | null>(null)

  const listQuery = useQuery({
    queryKey: ['quote-templates'],
    queryFn: () => api.listQuoteTemplates(),
  })

  const categoriesQuery = useQuery({
    queryKey: ['vhsys-categories'],
    queryFn: () => api.listVhsysCategories(),
    staleTime: 10 * 60_000,
    enabled: showForm,
  })
  const categories = categoriesQuery.data?.categories ?? []
  const categorySelectValue = categoryId != null ? String(categoryId) : NONE

  const allTemplates = listQuery.data?.templates ?? []
  const implantCount = allTemplates.filter((t) => t.section === 'implantacao').length
  const monthlyCount = allTemplates.filter((t) => t.section === 'mensalidade').length
  const templates = allTemplates.filter((t) => t.section === activeSection)
  const titleForActive =
    activeSection !== 'implantacao' && activeSection !== 'mensalidade'
      ? sectionTitle
      : undefined
  const meta = sectionMeta(activeSection, titleForActive)
  const SectionIcon = meta.icon
  const lockedCustom =
    Boolean(initialSection) &&
    initialSection !== 'implantacao' &&
    initialSection !== 'mensalidade'

  function resetForm() {
    setEditingId(null)
    setName('')
    setLines([emptyLine()])
    setCategoryId(null)
  }

  function switchSection(next: QuoteSection) {
    if (next === activeSection) return
    setActiveSection(next)
    setShowForm(false)
    resetForm()
  }

  function openCreate() {
    setEditingId(null)
    setName('')
    setCategoryId(null)
    const useSeed =
      Boolean(seedLines?.length) &&
      activeSection === (initialSection ?? activeSection)
    setLines(useSeed ? draftFromSeed(seedLines) : [emptyLine()])
    setShowForm(true)
  }

  function openEdit(template: QuoteTemplateRead) {
    setActiveSection(template.section)
    setEditingId(template.id)
    setName(template.name)
    setLines(linesFromTemplate(template))
    setCategoryId(null)
    setShowForm(true)
  }

  const createMutation = useMutation({
    mutationFn: (payload: { name: string; section: QuoteSection; lines: QuoteTemplateLine[] }) =>
      api.createQuoteTemplate(payload),
    onSuccess: (created) => {
      toast.success(
        `Modelo “${created.name}” criado em ${resolveSectionLabel(created.section, sectionTitle)}`,
      )
      resetForm()
      setShowForm(false)
      void queryClient.invalidateQueries({ queryKey: ['quote-templates'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao criar modelo')
    },
  })

  const updateMutation = useMutation({
    mutationFn: (payload: {
      id: number
      name: string
      section: QuoteSection
      lines: QuoteTemplateLine[]
    }) =>
      api.updateQuoteTemplate(payload.id, {
        name: payload.name,
        section: payload.section,
        lines: payload.lines,
      }),
    onSuccess: (updated) => {
      toast.success(`Modelo “${updated.name}” atualizado`)
      resetForm()
      setShowForm(false)
      void queryClient.invalidateQueries({ queryKey: ['quote-templates'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao atualizar modelo')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteQuoteTemplate(id),
    onSuccess: () => {
      toast.success('Modelo removido')
      void queryClient.invalidateQueries({ queryKey: ['quote-templates'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao remover modelo')
    },
  })

  const isSaving = createMutation.isPending || updateMutation.isPending

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      toast.error('Informe o nome do modelo.')
      return
    }
    const parsed = parseLines(lines)
    if (!parsed) return
    if (editingId != null) {
      updateMutation.mutate({
        id: editingId,
        name: trimmed,
        section: activeSection,
        lines: parsed,
      })
      return
    }
    createMutation.mutate({ name: trimmed, section: activeSection, lines: parsed })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Layers className={cn('h-4 w-4 shrink-0', meta.accentText)} aria-hidden />
            <h2
              className={cn(
                'font-semibold tracking-tight text-aurora-fg',
                embedded ? 'text-base' : 'text-lg',
              )}
            >
              Modelos de itens
            </h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
            Modelos por módulo. Linhas usam catálogo VHSYS e continuam editáveis no wizard.
          </p>
        </div>
        <Button type="button" className={cn(btnAccentClass, 'shrink-0')} onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Novo · {meta.label}
        </Button>
      </div>

      {/* Section switcher — presets; custom locked when embedded from wizard */}
      {lockedCustom ? (
        <div className="rounded-xl border border-aurora-border bg-aurora-surface-2/60 px-3 py-2.5 text-sm font-semibold">
          Seção: <span className={meta.accentText}>{meta.label}</span>
        </div>
      ) : (
      <div
        className="grid grid-cols-2 gap-2 rounded-xl border border-aurora-border bg-aurora-surface-2/60 p-1.5"
        role="tablist"
        aria-label="Seção do modelo"
      >
        {PRESET_SECTIONS.map((sec) => {
          const m = sectionMeta(sec)
          const Icon = m.icon
          const count = sec === 'implantacao' ? implantCount : monthlyCount
          const active = activeSection === sec
          return (
            <button
              key={sec}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => switchSection(sec)}
              className={cn(
                'aurora-motion flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-semibold',
                active
                  ? m.tabActive
                  : 'border-transparent bg-transparent text-aurora-muted hover:border-aurora-border hover:bg-aurora-surface hover:text-aurora-fg',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              <span>{m.label}</span>
              <span
                className={cn(
                  'rounded-full px-1.5 py-0.5 text-[10px] font-bold tabular-nums',
                  active ? 'bg-white/20 text-white' : 'bg-aurora-surface text-aurora-muted',
                )}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>
      )}

      <div
        className={cn(
          'hub-panel-enter space-y-4 rounded-xl border p-3 sm:p-4',
          meta.panel,
        )}
        role="tabpanel"
        aria-label={`Modelos de ${meta.label}`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <SectionIcon className={cn('h-4 w-4', meta.accentText)} aria-hidden />
          <span className={cn('text-sm font-semibold', meta.accentText)}>{meta.label}</span>
          <Badge className={cn('border', meta.chip)} variant="outline">
            {templates.length} modelo{templates.length === 1 ? '' : 's'}
          </Badge>
        </div>

        {showForm && (
          <form
            onSubmit={handleSubmit}
            className="aurora-motion space-y-4 rounded-xl border border-aurora-border bg-aurora-surface p-4 shadow-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-aurora-border/70 pb-3">
              <div>
                <p className="text-sm font-semibold text-aurora-fg">
                  {editingId != null ? 'Editar modelo' : 'Novo modelo'}
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Seção fixa: <span className={meta.accentText}>{meta.label}</span>
                </p>
              </div>
              <Badge className={cn('border', meta.chip)} variant="outline">
                {meta.label}
              </Badge>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="template-name">Nome</Label>
              <Input
                id="template-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={`Ex.: ${meta.label} padrão`}
                maxLength={200}
                required
                className="focus-visible:ring-aurora-accent"
              />
            </div>

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
                <SelectTrigger aria-label="Categoria VHSYS do modelo">
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
              {categoriesQuery.isError ? (
                <p className="text-[11px] text-aurora-danger">
                  {categoriesQuery.error instanceof Error
                    ? categoriesQuery.error.message
                    : 'Falha ao carregar categorias VHSYS'}
                </p>
              ) : (
                <p className="text-[11px] text-muted-foreground">
                  Filtra a busca de itens
                  {categoryId != null ? ' pela categoria selecionada' : ''}.
                </p>
              )}
            </div>

            <fieldset className="space-y-3 overflow-visible">
              <legend className="mb-1 text-sm font-medium text-aurora-fg">Linhas</legend>
              <ul className="space-y-3">
                {lines.map((line, idx) => (
                  <li
                    key={line.localKey}
                    className={cn(
                      'aurora-motion grid gap-2 overflow-visible rounded-xl border border-aurora-border bg-aurora-surface-2/40 p-3',
                      'hover:border-aurora-accent/40 hover:shadow-sm',
                      'sm:grid-cols-[1fr_5rem_7rem_auto]',
                    )}
                  >
                    <div className="space-y-1 overflow-visible">
                      <Label className="text-xs text-muted-foreground">Descrição (VHSYS)</Label>
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
                Linha
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
                  `Criar em ${meta.label}`
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
                : 'Não foi possível carregar modelos.'}
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
            icon={SectionIcon}
            title={`Nenhum modelo de ${meta.label.toLowerCase()}`}
            description={`Cadastre linhas pré-preenchidas só para ${meta.label.toLowerCase()}.`}
            action={{ label: `Novo · ${meta.label}`, onClick: openCreate }}
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
              const lineSum = template.lines.reduce(
                (s, l) => s + l.qty * l.unit_value,
                0,
              )
              return (
                <li key={template.id}>
                  <div
                    className={cn(
                      'aurora-motion group flex flex-col gap-3 rounded-xl border border-aurora-border bg-aurora-surface p-3.5 shadow-sm',
                      'hover:-translate-y-0.5 hover:border-aurora-accent/45 hover:shadow-md',
                      'sm:flex-row sm:items-center sm:justify-between',
                    )}
                  >
                    <div className="min-w-0 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate text-sm font-semibold text-aurora-fg">
                          {template.name}
                        </span>
                        <Badge className={cn('border', meta.chip)} variant="outline">
                          {meta.label}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        <span className="font-mono text-[10px] opacity-70">{template.key}</span>
                        {' · '}
                        {template.lines.length} linha(s)
                        {template.lines[0] ? ` · ${template.lines[0].name}` : ''}
                        {lineSum > 0 ? ` · ${formatBrl(lineSum)}` : ''}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        className={cn(
                          btnSecondaryClass,
                          'opacity-90 group-hover:opacity-100',
                        )}
                        onClick={() => openEdit(template)}
                        aria-label={`Editar modelo ${template.name}`}
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
                          if (window.confirm(`Remover modelo “${template.name}”?`)) {
                            deleteMutation.mutate(template.id)
                          }
                        }}
                        aria-label={`Remover modelo ${template.name}`}
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
