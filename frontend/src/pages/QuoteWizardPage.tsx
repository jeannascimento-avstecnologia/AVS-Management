import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  ArrowLeft,
  Building2,
  Check,
  CloudOff,
  FileDown,
  Loader2,
  Mail,
  MoreHorizontal,
  Plus,
  Search,
  Repeat,
  Send,
  StickyNote,
  Thermometer,
  Trash2,
  ChevronUp,
  ChevronDown,
  Boxes,
  FileText,
  Pencil,
  UserPlus,
  UserRound,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  ApiError,
  api,
  downloadBinaryBlob,
  isQuoteMarkSentEligible,
  isQuoteSubmittable,
  quoteFromOutboxResult,
  type BilledByType,
  type LeadTemperature,
  type QuoteItemWrite,
  type QuoteModule,
  type QuoteModuleTemplateRead,
  type QuoteProposalTemplateRead,
  type QuoteMonthlyDraftWrite,
  type QuoteRead,
  type QuoteSection,
  type QuoteTemplateLine,
  type QuoteUpdate,
  type LegacyModuleKind,
} from '@/api/client'
import {
  QuoteClientRegisterDialog,
  type QuoteClientLink,
} from '@/components/quotes/QuoteClientRegisterDialog'
import { QuoteModuleTemplatesPanel } from '@/components/quotes/QuoteModuleTemplatesPanel'
import { QuoteMonthlyChargesDialog } from '@/components/quotes/QuoteMonthlyChargesDialog'
import { QuoteProposalTemplatesPanel } from '@/components/quotes/QuoteProposalTemplatesPanel'
import { localId } from '@/lib/localId'
import { TifluxQuoteClientSearch } from '@/components/quotes/TifluxQuoteClientSearch'
import { VhsysItemSearch } from '@/components/quotes/VhsysItemSearch'
import { moduleTitleFromTemplate } from '@/lib/quoteModuleTemplates'
import { VhsysPartySearch } from '@/components/quotes/VhsysPartySearch'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
import { WizardStepper } from '@/components/ui/wizard-stepper'
import { usePermission } from '@/hooks/useAuth'
import { digitsOnly, formatCnpj, formatDate } from '@/lib/format'
import { btnAccentClass, btnSecondaryClass, btnDangerClass, inputClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

const STEPS = ['Cliente', 'Itens', 'Revisão'] as const

const TEMP_LABELS: Record<LeadTemperature, string> = {
  quente: 'Quente',
  morno: 'Morno',
  frio: 'Frio',
}

const TEMP_CHIP: Record<LeadTemperature, string> = {
  quente:
    'border-aurora-danger/50 bg-aurora-danger/15 text-aurora-danger ring-2 ring-aurora-danger/25',
  morno:
    'border-aurora-warning/50 bg-aurora-warning/15 text-aurora-warning ring-2 ring-aurora-warning/25',
  frio: 'border-aurora-info/50 bg-aurora-info/15 text-aurora-info ring-2 ring-aurora-info/25',
}

const NONE = '__none__'
const AUTOSAVE_MS = 800
const INSTALLMENT_OPTIONS = Array.from({ length: 12 }, (_, i) => i + 1)

type DraftItem = {
  localKey: string
  itemId: number | null
  section: QuoteSection
  name: string
  qty: string
  unit_value: string
  template_key: string | null
  vhsys_product_id: number | null
}

type DraftModule = {
  id: string
  title: string
  legacy_kind: LegacyModuleKind | null
  show_labor: boolean
  payment_plan: string
  discount_pct: string
  discount_value: string
  labor_hours: string
  labor_hourly_rate: string
  notes: string
  billed_by_name: string
  billed_by_cnpj: string
  simplified: boolean
  display_name: string
  sort_order: number
}

type PaymentMode = 'a_vista' | 'parcelado' | 'recorrente_anual' | ''

type DraftForm = {
  cnpj: string
  client_name: string
  title: string
  tiflux_client_id: number | null
  vhsys_client_id: number | null
  lead_temperature: LeadTemperature | null
  billed_by_type: BilledByType | null
  billed_by_name: string
  modules: DraftModule[]
  client_email: string
  extra_recipients: string[]
  notes: string
  items: DraftItem[]
}

type SaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error'

const PRESET_IMPLANT: DraftModule = {
  id: 'implantacao',
  title: 'Implantação',
  legacy_kind: 'implantacao',
  show_labor: false,
  payment_plan: '',
  discount_pct: '',
  discount_value: '',
  labor_hours: '',
  labor_hourly_rate: '',
  notes: '',
  billed_by_name: '',
  billed_by_cnpj: '',
  simplified: false,
  display_name: '',
  sort_order: 0,
}

const PRESET_MONTHLY: DraftModule = {
  id: 'mensalidade',
  title: 'Mensalidade',
  legacy_kind: 'mensalidade',
  show_labor: true,
  payment_plan: '',
  discount_pct: '',
  discount_value: '',
  labor_hours: '',
  labor_hourly_rate: '',
  notes: '',
  billed_by_name: '',
  billed_by_cnpj: '',
  simplified: false,
  display_name: '',
  sort_order: 1,
}

function moduleFromApi(mod: QuoteModule): DraftModule {
  return {
    id: mod.id,
    title: mod.title,
    legacy_kind: mod.legacy_kind,
    show_labor: mod.show_labor,
    payment_plan: mod.payment_plan ?? '',
    discount_pct: mod.discount_pct != null ? String(mod.discount_pct) : '',
    discount_value: mod.discount_value != null ? String(mod.discount_value) : '',
    labor_hours: mod.labor_hours != null ? String(mod.labor_hours) : '',
    labor_hourly_rate: mod.labor_hourly_rate != null ? String(mod.labor_hourly_rate) : '',
    notes: mod.notes ?? '',
    billed_by_name: mod.billed_by_name ?? '',
    billed_by_cnpj: mod.billed_by_cnpj ?? '',
    simplified: Boolean(mod.simplified),
    display_name: mod.display_name ?? '',
    sort_order: mod.sort_order,
  }
}

function modulesFromQuote(quote: QuoteRead): DraftModule[] {
  return [...(quote.modules ?? [])]
    .sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id))
    .map(moduleFromApi)
}

function slugifyModuleId(title: string): string {
  const base = title
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 48)
  return base || `modulo_${Date.now().toString(36)}`
}

function draftModuleToApi(mod: DraftModule, index: number): QuoteModule {
  return {
    id: mod.id,
    title: mod.title.trim() || mod.id,
    legacy_kind: mod.legacy_kind,
    show_labor: mod.show_labor,
    payment_plan: mod.payment_plan || null,
    discount_pct: parseOptionalNumber(mod.discount_pct),
    discount_value: parseOptionalNumber(mod.discount_value),
    labor_hours: mod.show_labor ? parseOptionalNumber(mod.labor_hours) : null,
    labor_hourly_rate: mod.show_labor ? parseOptionalNumber(mod.labor_hourly_rate) : null,
    notes: mod.notes.trim() || null,
    billed_by_name: mod.billed_by_name.trim() || null,
    billed_by_cnpj: digitsOnly(mod.billed_by_cnpj) || null,
    simplified: mod.simplified,
    display_name: mod.display_name.trim() || null,
    sort_order: index,
  }
}

function newLocalKey(): string {
  return localId()
}

function parseOptionalNumber(raw: string | number | null | undefined): number | null {
  if (raw == null) return null
  if (typeof raw === 'number') return Number.isFinite(raw) ? raw : null
  const trimmed = String(raw).trim()
  if (!trimmed) return null
  const n = Number(trimmed.replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

function parsePositiveNumber(raw: string | number | null | undefined, fallback: number): number {
  const n = parseOptionalNumber(raw)
  if (n == null || n <= 0) return fallback
  return n
}

function parseNonNegativeNumber(raw: string | number | null | undefined): number {
  const n = parseOptionalNumber(raw)
  if (n == null || n < 0) return 0
  return n
}

function money(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function roundMoney(value: number): number {
  return Math.round(value * 100) / 100
}

function formatMoneyInput(value: number): string {
  return String(roundMoney(value))
}

function formatPctInput(value: number): string {
  const rounded = Math.round(value * 100) / 100
  return String(rounded)
}

/** líquido = subtotal − desconto ( % e R$ vinculados, não somados ). */
function applySectionDiscount(
  subtotal: number,
  discountPct: string,
  discountValue: string,
): { discount: number; net: number } {
  const pct = Math.min(Math.max(parseOptionalNumber(discountPct) ?? 0, 0), 100)
  const fixed = Math.max(parseOptionalNumber(discountValue) ?? 0, 0)
  let discount = 0
  if (fixed > 0) {
    discount = roundMoney(Math.min(fixed, Math.max(0, subtotal)))
  } else if (pct > 0) {
    discount = roundMoney(Math.max(0, subtotal) * (pct / 100))
  }
  return { discount, net: roundMoney(Math.max(0, subtotal - discount)) }
}

/** Ao editar % → espelha R$; ao limpar % → limpa R$. */
function mirrorDiscountFromPct(
  subtotal: number,
  pctRaw: string,
): { pct: string; value: string } {
  if (!pctRaw.trim()) return { pct: '', value: '' }
  const pct = parseOptionalNumber(pctRaw)
  if (pct == null) return { pct: pctRaw, value: '' }
  const clamped = Math.min(Math.max(pct, 0), 100)
  if (subtotal <= 0) return { pct: pctRaw, value: clamped === 0 ? '0' : '' }
  return { pct: pctRaw, value: formatMoneyInput(subtotal * (clamped / 100)) }
}

/** Ao editar R$ → espelha %; ao limpar R$ → limpa %. */
function mirrorDiscountFromValue(
  subtotal: number,
  valueRaw: string,
): { pct: string; value: string } {
  if (!valueRaw.trim()) return { pct: '', value: '' }
  const fixed = parseOptionalNumber(valueRaw)
  if (fixed == null) return { pct: '', value: valueRaw }
  const amount = Math.max(fixed, 0)
  if (subtotal <= 0) return { pct: amount === 0 ? '0' : '', value: valueRaw }
  const pct = Math.min((amount / subtotal) * 100, 100)
  return { pct: formatPctInput(pct), value: valueRaw }
}

const RECORRENTE_LABEL = 'Anual - Recorrente Mensal'

function parsePaymentPlan(value: string): { mode: PaymentMode; installments: number | null } {
  const raw = value.trim()
  if (!raw || raw === 'a_vista') return { mode: raw ? 'a_vista' : '', installments: null }
  if (raw === 'recorrente_anual' || raw === 'recorrente-anual' || raw === 'anual') {
    return { mode: 'recorrente_anual', installments: 12 }
  }
  const recorrenteNx = raw.match(/^recorrente_(\d+)x?$/i)
  if (recorrenteNx) {
    const n = Number(recorrenteNx[1])
    if (n >= 1) return { mode: 'recorrente_anual', installments: Math.min(n, 12) }
  }
  const parcelado = raw.match(/^parcelado_(\d+)x?$/i)
  if (parcelado) {
    const n = Number(parcelado[1])
    if (n >= 1) return { mode: 'parcelado', installments: Math.min(n, 12) }
  }
  const legacy = raw.match(/^(\d+)x(?:_sem_juros)?$/i)
  if (legacy) {
    const n = Number(legacy[1])
    if (n >= 1) return { mode: 'parcelado', installments: Math.min(n, 12) }
  }
  if (raw === 'personalizado') return { mode: 'parcelado', installments: 2 }
  return { mode: 'parcelado', installments: 2 }
}

function buildPaymentPlan(mode: PaymentMode, installments: number | null): string {
  if (mode === 'a_vista') return 'a_vista'
  if (mode === 'recorrente_anual') {
    const n = installments && installments >= 1 && installments <= 12 ? installments : 12
    return `recorrente_${n}x`
  }
  if (mode === 'parcelado') {
    const n = installments && installments >= 1 && installments <= 12 ? installments : 2
    return `${n}x`
  }
  return ''
}

function defaultQuoteNotes(ticket: string | null): string {
  const number = (ticket ?? '').trim()
  return number
    ? `Os valores podem sofrer alteracao sem previo aviso.\nTicket no.: ${number}`
    : 'Os valores podem sofrer alteracao sem previo aviso.\nTicket no.:'
}

function parseMonthlyDraft(raw: string | null | undefined): QuoteMonthlyDraftWrite | null {
  if (!raw?.trim()) return null
  try {
    const data = JSON.parse(raw) as QuoteMonthlyDraftWrite
    if (!Array.isArray(data.allocations)) return null
    return { allocations: data.allocations }
  } catch {
    return null
  }
}

function syncDraftItemIds(form: DraftForm, quote: QuoteRead): DraftForm {
  const remaining = [...quote.items]
  const items = form.items.map((draft) => {
    if (draft.itemId != null) {
      const hitIdx = remaining.findIndex((i) => i.id === draft.itemId)
      if (hitIdx >= 0) {
        remaining.splice(hitIdx, 1)
        return draft
      }
    }
    const name = draft.name.trim() || 'Novo item'
    const qty = parsePositiveNumber(draft.qty, 1)
    const unit = parseNonNegativeNumber(draft.unit_value)
    const hitIdx = remaining.findIndex(
      (i) =>
        i.section === draft.section &&
        i.name === name &&
        i.qty === qty &&
        i.unit_value === unit,
    )
    if (hitIdx >= 0) {
      const hit = remaining.splice(hitIdx, 1)[0]
      return { ...draft, itemId: hit.id }
    }
    return draft
  })
  return { ...form, items }
}

function quoteToForm(quote: QuoteRead): DraftForm {
  return {
    cnpj: quote.cnpj,
    client_name: quote.client_name ?? '',
    title: quote.title ?? '',
    tiflux_client_id: quote.tiflux_client_id,
    vhsys_client_id: quote.vhsys_client_id,
    lead_temperature: quote.lead_temperature,
    billed_by_type: quote.billed_by_type,
    billed_by_name: quote.billed_by_name ?? '',
    modules: modulesFromQuote(quote),
    client_email: quote.client_email ?? '',
    extra_recipients: [...(quote.extra_recipients ?? [])],
    notes: quote.notes?.trim() ? quote.notes : defaultQuoteNotes(quote.tiflux_ticket_number),
    items: quote.items.map((item) => ({
      localKey: newLocalKey(),
      itemId: item.id,
      section: item.section,
      name: item.name,
      qty: String(item.qty),
      unit_value: String(item.unit_value),
      template_key: item.template_key,
      vhsys_product_id: item.vhsys_product_id ?? null,
    })),
  }
}

function formToUpdate(form: DraftForm): QuoteUpdate {
  const modules = form.modules.map((m, i) => draftModuleToApi(m, i))
  const items: QuoteItemWrite[] = form.items.map((item, index) => ({
    id: item.itemId ?? undefined,
    section: item.section,
    name: item.name.trim() || 'Novo item',
    qty: parsePositiveNumber(item.qty, 1),
    unit_value: parseNonNegativeNumber(item.unit_value),
    template_key: item.template_key,
    vhsys_product_id: item.vhsys_product_id,
    sort_order: index,
  }))

  const implant = modules.find((m) => m.legacy_kind === 'implantacao')
  const monthly = modules.find((m) => m.legacy_kind === 'mensalidade')

  return {
    cnpj: digitsOnly(form.cnpj),
    client_name: form.client_name.trim() || null,
    tiflux_client_id: form.tiflux_client_id,
    vhsys_client_id: form.vhsys_client_id,
    lead_temperature: form.lead_temperature,
    billed_by_type: form.billed_by_type,
    billed_by_name: form.billed_by_name.trim() || null,
    implant_payment_plan: implant?.payment_plan ?? null,
    implant_discount_pct: implant?.discount_pct ?? null,
    implant_discount_value: implant?.discount_value ?? null,
    implant_labor_hours: null,
    implant_labor_hourly_rate: null,
    monthly_payment_plan: monthly?.payment_plan ?? null,
    monthly_discount_pct: monthly?.discount_pct ?? null,
    monthly_discount_value: monthly?.discount_value ?? null,
    monthly_labor_hours: monthly?.labor_hours ?? null,
    monthly_labor_hourly_rate: monthly?.labor_hourly_rate ?? null,
    modules,
    client_email: form.client_email.trim() || null,
    extra_recipients: form.extra_recipients
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean),
    notes: form.notes.trim() || null,
    title: form.title.trim() || null,
    items,
  }
}

function laborTotal(hoursRaw: string, rateRaw: string): number {
  const hours = Math.max(0, parseNonNegativeNumber(hoursRaw))
  const rate = Math.max(0, parseNonNegativeNumber(rateRaw))
  return hours * rate
}

function sectionTotal(items: DraftItem[], section: QuoteSection): number {
  return items
    .filter((i) => i.section === section)
    .reduce((sum, i) => {
      const qty = parsePositiveNumber(i.qty, 0)
      const unit = parseNonNegativeNumber(i.unit_value)
      return sum + qty * unit
    }, 0)
}

function paymentLabel(value: string): string {
  if (!value) return '—'
  const { mode, installments } = parsePaymentPlan(value)
  if (mode === 'a_vista') return 'À vista'
  if (mode === 'recorrente_anual') {
    return installments ? `${RECORRENTE_LABEL} ${installments}x` : RECORRENTE_LABEL
  }
  if (mode === 'parcelado' && installments) return `Parcelado ${installments}x`
  return value
}

function lineTotal(item: DraftItem): number {
  return parsePositiveNumber(item.qty, 0) * parseNonNegativeNumber(item.unit_value)
}

export function QuoteWizardPage() {
  const { id: idParam } = useParams<{ id: string }>()
  const quoteId = Number(idParam)
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const canCadastrar = usePermission('cadastrar')

  const locationStep = (location.state as { initialStep?: number } | null)?.initialStep
  const [step, setStep] = useState(() =>
    locationStep === 2 || locationStep === 3 ? locationStep : 1,
  )
  const [form, setForm] = useState<DraftForm | null>(null)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [clientDialogOpen, setClientDialogOpen] = useState(false)
  const [pdfPending, setPdfPending] = useState(false)
  const [extraEmailDraft, setExtraEmailDraft] = useState('')
  const [tifluxSearch, setTifluxSearch] = useState('')
  const [addModuleOpen, setAddModuleOpen] = useState(false)
  const [insertBlockSearch, setInsertBlockSearch] = useState('')
  const [customModuleTitle, setCustomModuleTitle] = useState('')
  const [manageModuleTemplatesOpen, setManageModuleTemplatesOpen] = useState(false)
  const [proposalLibraryOpen, setProposalLibraryOpen] = useState(false)
  const [saveProposalOpen, setSaveProposalOpen] = useState(false)
  const [saveProposalName, setSaveProposalName] = useState('')
  const [monthlyOpen, setMonthlyOpen] = useState(false)
  const [monthlySaving, setMonthlySaving] = useState(false)
  const [versionSaving, setVersionSaving] = useState(false)
  const [versionPdfPending, setVersionPdfPending] = useState<number | null>(null)
  const emailPrefillDone = useRef(false)
  const discountSourceByModule = useRef<Record<string, 'pct' | 'value' | null>>({})

  const hydratedId = useRef<number | null>(null)
  const dirtyRef = useRef(false)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const quoteQuery = useQuery({
    queryKey: ['quote', quoteId],
    queryFn: () => api.getQuote(quoteId),
    enabled: Number.isFinite(quoteId) && quoteId > 0,
  })

  const versionsQuery = useQuery({
    queryKey: ['quote-versions', quoteId],
    queryFn: () => api.listQuoteVersions(quoteId),
    enabled: Number.isFinite(quoteId) && quoteId > 0,
  })

  const moduleTemplatesQuery = useQuery({
    queryKey: ['quote-module-templates'],
    queryFn: () => api.listQuoteModuleTemplates(),
  })

  const quote = quoteQuery.data
  const canEdit = quote?.status === 'draft'
  const moduleTemplates = moduleTemplatesQuery.data?.templates ?? []
  const filteredInsertTemplates = useMemo(() => {
    const q = insertBlockSearch.trim().toLocaleLowerCase('pt-BR')
    if (!q) return moduleTemplates
    return moduleTemplates.filter((tpl) => {
      const title = moduleTitleFromTemplate(tpl).toLocaleLowerCase('pt-BR')
      return title.includes(q) || tpl.name.toLocaleLowerCase('pt-BR').includes(q)
    })
  }, [moduleTemplates, insertBlockSearch])

  useEffect(() => {
    if (!quote) return
    if (hydratedId.current === quote.id) return
    hydratedId.current = quote.id
    emailPrefillDone.current = false
    discountSourceByModule.current = {}
    setForm(quoteToForm(quote))
    setTifluxSearch(quote.client_name?.trim() || '')
    setSaveStatus('idle')
    setLastSavedAt(quote.updated_at)
    dirtyRef.current = false
  }, [quote])

  const patchForm = useCallback((updater: (prev: DraftForm) => DraftForm) => {
    setForm((prev) => {
      if (!prev) return prev
      return updater(prev)
    })
    dirtyRef.current = true
    setSaveStatus('dirty')
  }, [])

  function moduleSubtotal(mod: DraftModule, items: DraftItem[]): number {
    const itemsSum = sectionTotal(items, mod.id)
    const labor = mod.show_labor
      ? laborTotal(mod.labor_hours, mod.labor_hourly_rate)
      : 0
    return itemsSum + labor
  }

  function patchModule(moduleId: string, patch: Partial<DraftModule>) {
    patchForm((prev) => ({
      ...prev,
      modules: prev.modules.map((m) => (m.id === moduleId ? { ...m, ...patch } : m)),
    }))
  }

  // Reespelha desconto quando o subtotal muda (itens / mão de obra).
  useEffect(() => {
    if (!form || !canEdit) return
    let changed = false
    const nextModules = form.modules.map((mod) => {
      const source = discountSourceByModule.current[mod.id]
      if (!source) return mod
      const sub = moduleSubtotal(mod, form.items)
      if (source === 'pct' && mod.discount_pct.trim()) {
        const mirrored = mirrorDiscountFromPct(sub, mod.discount_pct)
        if (mirrored.value !== mod.discount_value) {
          changed = true
          return { ...mod, discount_value: mirrored.value }
        }
      } else if (source === 'value' && mod.discount_value.trim()) {
        const mirrored = mirrorDiscountFromValue(sub, mod.discount_value)
        if (mirrored.pct !== mod.discount_pct) {
          changed = true
          return { ...mod, discount_pct: mirrored.pct }
        }
      }
      return mod
    })
    if (changed) {
      patchForm((p) => ({ ...p, modules: nextModules }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- evita loop em modules[]
  }, [canEdit, patchForm, form?.items])

  // Prefill e-mail: TiFlux (contato) → fallback VHSYS, se ainda vazio.
  useEffect(() => {
    if (step !== 3 || !form || !canEdit) return
    if (emailPrefillDone.current) return
    if (form.client_email.trim()) {
      emailPrefillDone.current = true
      return
    }
    const tifluxId = form.tiflux_client_id
    const vhsysId = form.vhsys_client_id
    if (tifluxId == null && vhsysId == null) {
      emailPrefillDone.current = true
      return
    }
    let cancelled = false
    void (async () => {
      try {
        if (tifluxId != null) {
          const contact = await api.getTifluxClientContact(tifluxId)
          if (cancelled) return
          if (contact.email) {
            patchForm((prev) => {
              if (prev.client_email.trim()) return prev
              return { ...prev, client_email: contact.email ?? '' }
            })
            return
          }
        }
        if (vhsysId != null) {
          const contact = await api.getVhsysClientContact(vhsysId)
          if (cancelled || !contact.email) return
          patchForm((prev) => {
            if (prev.client_email.trim()) return prev
            return { ...prev, client_email: contact.email ?? '' }
          })
        }
      } catch {
        /* silencioso — usuário digita manualmente */
      } finally {
        if (!cancelled) emailPrefillDone.current = true
      }
    })()
    return () => {
      cancelled = true
    }
  }, [step, form, canEdit, patchForm])

  const formRef = useRef(form)
  formRef.current = form

  const saveMutation = useMutation({
    mutationFn: (body: QuoteUpdate) => api.updateQuote(quoteId, body),
    onSuccess: (updated) => {
      setLastSavedAt(updated.updated_at)
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      queryClient.setQueryData(['quote', quoteId], updated)
      setForm((prev) => (prev ? syncDraftItemIds(prev, updated) : prev))
      if (dirtyRef.current) {
        setSaveStatus('dirty')
      } else {
        setSaveStatus('saved')
      }
    },
    onError: (err: Error) => {
      dirtyRef.current = true
      setSaveStatus('error')
      toast.error(err.message || 'Falha ao salvar rascunho')
    },
  })

  const saveProposalMutation = useMutation({
    mutationFn: (payload: { name: string; modules: QuoteModule[]; items: QuoteItemWrite[] }) =>
      api.createQuoteProposalTemplate(payload),
    onSuccess: (created) => {
      toast.success(`Modelo “${created.name}” salvo`)
      setSaveProposalOpen(false)
      setSaveProposalName('')
      void queryClient.invalidateQueries({ queryKey: ['quote-proposal-templates'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao salvar modelo')
    },
  })

  const persist = useCallback(() => {
    const current = formRef.current
    if (!current || !canEdit) return
    if (digitsOnly(current.cnpj).length !== 14) {
      setSaveStatus('error')
      return
    }
    dirtyRef.current = false
    setSaveStatus('saving')
    saveMutation.mutate(formToUpdate(current))
  }, [canEdit, saveMutation])

  useEffect(() => {
    if (!form || !canEdit || saveStatus !== 'dirty') return
    if (digitsOnly(form.cnpj).length !== 14) return

    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      persist()
    }, AUTOSAVE_MS)

    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current)
    }
  }, [form, canEdit, saveStatus, persist])

  function addItem(section: QuoteSection) {
    patchForm((prev) => ({
      ...prev,
      items: [
        ...prev.items,
        {
          localKey: newLocalKey(),
          itemId: null,
          section,
          name: '',
          qty: '1',
          unit_value: '',
          template_key: null,
          vhsys_product_id: null,
        },
      ],
    }))
  }

  function removeItem(localKey: string) {
    patchForm((prev) => ({
      ...prev,
      items: prev.items.filter((i) => i.localKey !== localKey),
    }))
  }

  function updateItem(localKey: string, patch: Partial<DraftItem>) {
    patchForm((prev) => ({
      ...prev,
      items: prev.items.map((i) => (i.localKey === localKey ? { ...i, ...patch } : i)),
    }))
  }

  function removeModule(moduleId: string) {
    const mod = form?.modules.find((m) => m.id === moduleId)
    if (!mod) return
    if (
      !window.confirm(
        `Remover o bloco “${mod.title}”? Os itens deste bloco serão apagados.`,
      )
    ) {
      return
    }
    patchForm((prev) => ({
      ...prev,
      modules: prev.modules
        .filter((m) => m.id !== moduleId)
        .map((m, i) => ({ ...m, sort_order: i })),
      items: prev.items.filter((i) => i.section !== moduleId),
    }))
  }

  function moveModule(moduleId: string, direction: -1 | 1) {
    patchForm((prev) => {
      const ordered = [...prev.modules].sort((a, b) => a.sort_order - b.sort_order)
      const idx = ordered.findIndex((m) => m.id === moduleId)
      const swap = idx + direction
      if (idx < 0 || swap < 0 || swap >= ordered.length) return prev
      const next = [...ordered]
      ;[next[idx], next[swap]] = [next[swap], next[idx]]
      return {
        ...prev,
        modules: next.map((m, i) => ({ ...m, sort_order: i })),
      }
    })
  }

  function restorePreset(kind: LegacyModuleKind) {
    const preset = kind === 'implantacao' ? { ...PRESET_IMPLANT } : { ...PRESET_MONTHLY }
    patchForm((prev) => {
      if (prev.modules.some((m) => m.id === preset.id)) return prev
      const modules = [...prev.modules, { ...preset, sort_order: prev.modules.length }]
      return { ...prev, modules: modules.map((m, i) => ({ ...m, sort_order: i })) }
    })
    setAddModuleOpen(false)
  }

  function addCustomModule() {
    const title = customModuleTitle.trim()
    if (!title) {
      toast.error('Informe o título do bloco.')
      return
    }
    let id = slugifyModuleId(title)
    patchForm((prev) => {
      const existing = new Set(prev.modules.map((m) => m.id))
      let n = 2
      let candidate = id
      while (existing.has(candidate)) {
        candidate = `${id}_${n}`
        n += 1
      }
      id = candidate
      const modules = [
        ...prev.modules,
        {
          id,
          title,
          legacy_kind: null as LegacyModuleKind | null,
          show_labor: false,
          payment_plan: '',
          discount_pct: '',
          discount_value: '',
          labor_hours: '',
          labor_hourly_rate: '',
          notes: '',
          billed_by_name: '',
          billed_by_cnpj: '',
          simplified: false,
          display_name: '',
          sort_order: prev.modules.length,
        },
      ]
      return { ...prev, modules: modules.map((m, i) => ({ ...m, sort_order: i })) }
    })
    setCustomModuleTitle('')
    setAddModuleOpen(false)
    toast.success(`Bloco “${title}” adicionado`)
  }

  function addModuleFromTemplate(template: QuoteModuleTemplateRead) {
    const moduleId = `custom_${localId()}`
    const title = moduleTitleFromTemplate(template)
    if (!title) {
      toast.error('Bloco sem título — edite na Biblioteca.')
      return
    }
    patchForm((prev) => {
      const modules = [
        ...prev.modules,
        {
          id: moduleId,
          title,
          legacy_kind: null as LegacyModuleKind | null,
          show_labor: template.show_labor,
          payment_plan: '',
          discount_pct: '',
          discount_value: '',
          labor_hours: '',
          labor_hourly_rate: '',
          notes: template.notes ?? '',
          billed_by_name: template.billed_by_name ?? '',
          billed_by_cnpj: template.billed_by_cnpj ?? '',
          simplified: Boolean(template.simplified),
          display_name: template.display_name ?? '',
          sort_order: prev.modules.length,
        },
      ]
      const fromTemplate: DraftItem[] = template.lines.map((line) => ({
        localKey: newLocalKey(),
        itemId: null,
        section: moduleId,
        name: line.name,
        qty: String(line.qty),
        unit_value: String(line.unit_value),
        template_key: template.key,
        vhsys_product_id: null,
      }))
      return {
        ...prev,
        modules: modules.map((m, i) => ({ ...m, sort_order: i })),
        items: [...prev.items, ...fromTemplate],
      }
    })
    setAddModuleOpen(false)
    toast.success(`Bloco “${title}” inserido`)
  }

  function applyProposalTemplate(template: QuoteProposalTemplateRead) {
    if (!canEdit) return
    if (form && form.modules.length > 0) {
      if (
        !window.confirm(
          'Substituir os blocos atuais por este modelo? Itens e condições do canvas serão trocados.',
        )
      ) {
        return
      }
    }
    const idMap = new Map<string, string>()
    const modules: DraftModule[] = [...template.modules]
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((mod, idx) => {
        const nextId =
          mod.legacy_kind === 'implantacao' || mod.legacy_kind === 'mensalidade'
            ? mod.id
            : `custom_${localId()}`
        idMap.set(mod.id, nextId)
        return {
          ...moduleFromApi(mod),
          id: nextId,
          sort_order: idx,
        }
      })
    const items: DraftItem[] = template.items.map((item) => ({
      localKey: newLocalKey(),
      itemId: null,
      section: idMap.get(item.section) ?? item.section,
      name: item.name,
      qty: String(item.qty),
      unit_value: String(item.unit_value),
      template_key: item.template_key ?? null,
      vhsys_product_id: item.vhsys_product_id ?? null,
    }))
    patchForm((prev) => ({ ...prev, modules, items }))
    setProposalLibraryOpen(false)
    toast.success(`Modelo “${template.name}” aplicado`)
  }

  async function handleManualSave() {
    if (!canEdit) return
    if (digitsOnly(form?.cnpj ?? '').length !== 14) {
      toast.error('CNPJ inválido — corrija no passo Cliente.')
      setStep(1)
      return
    }
    const current = formRef.current
    if (!current) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    setVersionSaving(true)
    dirtyRef.current = false
    setSaveStatus('saving')
    try {
      const updated = await api.updateQuote(quoteId, formToUpdate(current))
      const synced = syncDraftItemIds(current, updated)
      formRef.current = synced
      setForm(synced)
      queryClient.setQueryData(['quote', quoteId], updated)
      setLastSavedAt(updated.updated_at)
      const version = await api.createQuoteVersion(quoteId)
      void queryClient.invalidateQueries({ queryKey: ['quote', quoteId] })
      void queryClient.invalidateQueries({ queryKey: ['quote-versions', quoteId] })
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      setSaveStatus('saved')
      toast.success(`Versão v${version.version_number} salva`)
    } catch (err) {
      dirtyRef.current = true
      setSaveStatus('error')
      toast.error(err instanceof Error ? err.message : 'Falha ao salvar versão')
    } finally {
      setVersionSaving(false)
    }
  }

  async function handleMonthlySave(draft: QuoteMonthlyDraftWrite, selectedLocalKeys: string[]) {
    const current = formRef.current
    if (!current || !canEdit) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    setMonthlySaving(true)
    try {
      const updated = await api.updateQuote(quoteId, formToUpdate(current))
      const synced = syncDraftItemIds(current, updated)
      formRef.current = synced
      setForm(synced)
      queryClient.setQueryData(['quote', quoteId], updated)
      const idByKey = new Map(synced.items.map((i) => [i.localKey, i.itemId]))
      const allocations = draft.allocations.map((a, index) => {
        const fromKey = idByKey.get(selectedLocalKeys[index] ?? '')
        return { ...a, item_id: fromKey ?? a.item_id }
      })
      if (selectedLocalKeys.length > 0 && allocations.some((a) => !a.item_id || a.item_id < 1)) {
        toast.error('Salve os itens antes de aplicar mensalidades.')
        return
      }
      const next = await api.updateQuoteMonthlyDraft(quoteId, { allocations })
      queryClient.setQueryData(['quote', quoteId], next)
      setLastSavedAt(next.updated_at)
      dirtyRef.current = false
      setSaveStatus('saved')
      setMonthlyOpen(false)
      toast.success(allocations.length ? 'Mensalidades aplicadas' : 'Mensalidades limpas')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Falha ao salvar mensalidades')
    } finally {
      setMonthlySaving(false)
    }
  }

  async function handleDownloadVersionPdf(versionId: number, versionNumber: number) {
    setVersionPdfPending(versionId)
    try {
      const { blob, filename } = await api.downloadQuoteVersionPdf(
        quoteId,
        versionId,
        versionNumber,
      )
      downloadBinaryBlob(blob, filename)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Falha ao baixar PDF da versão')
    } finally {
      setVersionPdfPending(null)
    }
  }

  function addExtraRecipient() {
    const email = extraEmailDraft.trim().toLowerCase()
    if (!email) return
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      toast.error('E-mail extra inválido.')
      return
    }
    patchForm((prev) => {
      if (prev.extra_recipients.includes(email) || prev.client_email.trim().toLowerCase() === email) {
        return prev
      }
      return { ...prev, extra_recipients: [...prev.extra_recipients, email] }
    })
    setExtraEmailDraft('')
  }

  /** Aplica refs do cliente sem tocar em `items`. */
  function applyClientLink(link: QuoteClientLink) {
    emailPrefillDone.current = false
    const name = link.client_name || ''
    if (name) setTifluxSearch(name)
    patchForm((prev) => ({
      ...prev,
      cnpj: link.cnpj,
      client_name: link.client_name || prev.client_name,
      tiflux_client_id: link.tiflux_client_id,
      vhsys_client_id: link.vhsys_client_id,
      client_email: '',
    }))
  }

  async function handleGeneratePdf() {
    setPdfPending(true)
    try {
      const { blob, filename } = await api.generateQuotePdf(quoteId)
      downloadBinaryBlob(blob, filename)
      void queryClient.invalidateQueries({ queryKey: ['quote', quoteId] })
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      toast.success('PDF gerado')
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          toast.error('Sem permissão para gerar PDF.')
          return
        }
        if (err.status === 404) {
          toast.error('Orçamento não encontrado.')
          return
        }
      }
      toast.error(err instanceof Error ? err.message : 'Falha ao gerar PDF')
    } finally {
      setPdfPending(false)
    }
  }

  const submitMutation = useMutation({
    mutationFn: async () => {
      const current = formRef.current
      if (current && canEdit && dirtyRef.current) {
        if (digitsOnly(current.cnpj).length !== 14) {
          throw new Error('CNPJ inválido — corrija no passo Cliente.')
        }
        if (saveTimer.current) clearTimeout(saveTimer.current)
        dirtyRef.current = false
        await api.updateQuote(quoteId, formToUpdate(current))
      }
      return api.submitQuote(quoteId)
    },
    onSuccess: (result) => {
      const updated = quoteFromOutboxResult(result)
      queryClient.setQueryData(['quote', quoteId], updated)
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      setSaveStatus('idle')
      dirtyRef.current = false
      const dryNote = result.dry_run ? ' (dry-run — sem POST externo)' : ''
      toast.success(`Orçamento enviado${dryNote}`)
    },
    onError: (err: Error) => {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          toast.error('Sem permissão para enviar orçamento.')
          return
        }
        if (err.status === 409) {
          toast.error(err.message || 'Orçamento não está elegível para envio.')
          return
        }
      }
      toast.error(err.message || 'Falha ao enviar orçamento')
    },
  })

  const markSentMutation = useMutation({
    mutationFn: () => api.markSentQuote(quoteId),
    onSuccess: (result) => {
      const updated = quoteFromOutboxResult(result)
      queryClient.setQueryData(['quote', quoteId], updated)
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      const dryNote = result.dry_run ? ' (dry-run)' : ''
      toast.success(`Marcado como enviado ao cliente${dryNote}`)
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Falha ao marcar como enviado')
    },
  })

  function handleSubmit() {
    if (digitsOnly(form?.cnpj ?? '').length !== 14) {
      toast.error('CNPJ inválido — corrija no passo Cliente.')
      setStep(1)
      return
    }
    if ((form?.items.length ?? 0) === 0) {
      toast.error('Adicione ao menos um item antes de enviar.')
      setStep(2)
      return
    }
    const primary = form?.client_email.trim() ?? ''
    if (!primary) {
      toast.error('Informe o e-mail do destinatário principal antes de enviar.')
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(primary)) {
      toast.error('E-mail principal inválido.')
      return
    }
    submitMutation.mutate()
  }

  if (!Number.isFinite(quoteId) || quoteId <= 0) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>ID de orçamento inválido.</AlertDescription>
      </Alert>
    )
  }

  if (quoteQuery.isPending || !form) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  if (quoteQuery.isError || !quote) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Não encontrado</AlertTitle>
          <AlertDescription>
            {quoteQuery.error instanceof Error
              ? quoteQuery.error.message
              : 'Orçamento não encontrado.'}
          </AlertDescription>
        </Alert>
        <Button type="button" className={btnSecondaryClass} asChild>
          <Link to="/orcamentos">Voltar à lista</Link>
        </Button>
      </div>
    )
  }

  const orderedModules = [...form.modules].sort(
    (a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id),
  )
  const hasImplant = orderedModules.some((m) => m.id === 'implantacao')
  const hasMonthly = orderedModules.some((m) => m.id === 'mensalidade')
  const moduleNets = orderedModules.map((mod) => {
    const sub = moduleSubtotal(mod, form.items)
    return {
      mod,
      sub,
      net: applySectionDiscount(sub, mod.discount_pct, mod.discount_value),
    }
  })
  const grandTotal = moduleNets.reduce((sum, row) => sum + row.net.net, 0)
  const monthlyLines = form.items.map((item) => ({
    localKey: item.localKey,
    itemId: item.itemId,
    section: item.section,
    sectionTitle: form.modules.find((m) => m.id === item.section)?.title ?? item.section,
    name: item.name.trim() || 'Novo item',
    total: lineTotal(item),
  }))
  const monthlyDraft = parseMonthlyDraft(quote.monthly_draft_json)
  const versions = versionsQuery.data?.versions ?? []

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="-ml-2 h-8 gap-1 text-muted-foreground"
            onClick={() => navigate('/orcamentos')}
          >
            <ArrowLeft className="h-4 w-4" />
            Lista
          </Button>
          <h1 className="flex flex-wrap items-center gap-2 text-2xl font-semibold tracking-tight">
            <span>
              Orçamento M{quote.id}
              {quote.current_version_number != null ? (
                <span className="ml-2 text-base font-normal text-muted-foreground">
                  v{quote.current_version_number}
                </span>
              ) : null}
            </span>
            <Input
              className="h-8 max-w-xs text-sm font-normal"
              placeholder="Nome do orçamento (não vai no PDF)"
              disabled={!canEdit}
              value={form.title}
              maxLength={120}
              onChange={(e) => patchForm((prev) => ({ ...prev, title: e.target.value }))}
              aria-label="Nome do orçamento"
            />
          </h1>
          <p className="text-sm text-muted-foreground">
            {formatCnpj(form.cnpj)}
            {form.client_name ? ` · ${form.client_name}` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={canEdit ? 'secondary' : 'outline'}>
            {canEdit ? 'Rascunho' : quote.status}
          </Badge>
          {quote.current_version_number != null ? (
            <Badge variant="outline">v{quote.current_version_number}</Badge>
          ) : null}
          <SaveIndicator status={saveStatus} lastSavedAt={lastSavedAt} />
        </div>
      </div>

      {!canEdit && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Somente leitura</AlertTitle>
          <AlertDescription>
            Status <strong>{quote.status}</strong> — edição e autosave só em draft.
          </AlertDescription>
        </Alert>
      )}

      <WizardStepper steps={[...STEPS]} current={step} accent="blue" />

      {step === 1 && (
        <Card className="hub-panel-enter border-aurora-border border-l-4 border-l-aurora-accent bg-aurora-surface shadow-sm">
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center gap-2">
              <UserRound className="h-4 w-4 text-aurora-accent" aria-hidden />
              <CardTitle className="text-base">Cliente</CardTitle>
              <Badge
                variant="outline"
                className="border-aurora-accent/40 bg-aurora-accent-muted text-aurora-accent"
              >
                Passo 1
              </Badge>
              {form.tiflux_client_id != null ? (
                <Badge variant="success">Vinculado</Badge>
              ) : (
                <Badge variant="outline" className="text-muted-foreground">
                  Pendente
                </Badge>
              )}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Busca TiFlux (CNPJ ou nome). Lead e vínculo no mesmo painel — padrão visual do passo
              Itens.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className={cn(
                'space-y-3 rounded-xl border border-aurora-accent/30 p-3 sm:p-4',
                'bg-gradient-to-br from-aurora-accent-muted/40 to-aurora-surface',
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Building2 className="h-4 w-4 text-aurora-accent" aria-hidden />
                <span className="text-sm font-semibold text-aurora-accent">Cliente TiFlux</span>
              </div>
              <TifluxQuoteClientSearch
                value={tifluxSearch}
                disabled={!canEdit}
                onChange={(v) => {
                  setTifluxSearch(v)
                  if (
                    canEdit &&
                    form.tiflux_client_id != null &&
                    v !== form.client_name
                  ) {
                    patchForm((prev) => ({
                      ...prev,
                      tiflux_client_id: null,
                      client_name: '',
                      cnpj: '',
                    }))
                  }
                }}
                onSelect={(client) => {
                  const clientCnpj = client.cnpj ? digitsOnly(client.cnpj) : ''
                  if (clientCnpj.length !== 14) {
                    toast.error('Cliente sem CNPJ válido no TiFlux.')
                    return
                  }
                  setTifluxSearch(client.name)
                  emailPrefillDone.current = false
                  patchForm((prev) => ({
                    ...prev,
                    cnpj: clientCnpj,
                    client_name: client.name || prev.client_name,
                    tiflux_client_id: client.id,
                    client_email: '',
                  }))
                  void api
                    .getTifluxClientContact(client.id)
                    .then((contact) => {
                      if (!contact.email) return
                      patchForm((prev) => {
                        if (prev.tiflux_client_id !== client.id) return prev
                        if (prev.client_email.trim()) return prev
                        return { ...prev, client_email: contact.email ?? '' }
                      })
                      emailPrefillDone.current = true
                    })
                    .catch(() => {
                      /* prefill na revisão tenta de novo */
                    })
                  toast.success(`Cliente TiFlux #${client.id} vinculado`)
                }}
              />
              {(form.client_name || form.cnpj || form.tiflux_client_id != null) && (
                <div
                  className={cn(
                    'aurora-motion rounded-xl border border-aurora-border bg-aurora-surface p-3 shadow-sm',
                    'hover:border-aurora-accent/45 hover:shadow-md',
                  )}
                >
                  <p className="text-sm font-semibold text-aurora-fg">
                    {form.client_name || '—'}
                  </p>
                  <p className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    {form.cnpj ? (
                      <span className="font-mono">{formatCnpj(form.cnpj)}</span>
                    ) : null}
                    {form.tiflux_client_id != null ? (
                      <Badge
                        variant="outline"
                        className="border-aurora-accent/40 bg-aurora-accent-muted text-aurora-accent"
                      >
                        TiFlux #{form.tiflux_client_id}
                      </Badge>
                    ) : null}
                    {form.vhsys_client_id != null ? (
                      <Badge
                        variant="outline"
                        className="border-aurora-brand-red/40 bg-aurora-brand-red/10 text-aurora-brand-red"
                      >
                        VHSYS #{form.vhsys_client_id}
                      </Badge>
                    ) : null}
                  </p>
                </div>
              )}
            </div>

            <div
              className={cn(
                'space-y-3 rounded-xl border border-aurora-border p-3 sm:p-4',
                'bg-gradient-to-br from-aurora-surface-2/80 to-aurora-surface',
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Thermometer className="h-4 w-4 text-aurora-muted" aria-hidden />
                <span className="text-sm font-semibold text-aurora-fg">Temperatura do lead</span>
                {form.lead_temperature ? (
                  <Badge variant="outline" className={cn('border', TEMP_CHIP[form.lead_temperature])}>
                    {TEMP_LABELS[form.lead_temperature]}
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-muted-foreground">
                    Não informado
                  </Badge>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Temperatura do lead">
                <Button
                  type="button"
                  size="sm"
                  className={cn(
                    btnSecondaryClass,
                    'aurora-motion',
                    form.lead_temperature === null &&
                      'border-aurora-accent bg-aurora-accent-muted text-aurora-accent ring-2 ring-aurora-accent/25',
                  )}
                  disabled={!canEdit}
                  onClick={() => patchForm((p) => ({ ...p, lead_temperature: null }))}
                >
                  —
                </Button>
                {(Object.keys(TEMP_LABELS) as LeadTemperature[]).map((t) => (
                  <Button
                    key={t}
                    type="button"
                    size="sm"
                    className={cn(
                      btnSecondaryClass,
                      'aurora-motion',
                      form.lead_temperature === t && TEMP_CHIP[t],
                    )}
                    disabled={!canEdit}
                    onClick={() => patchForm((p) => ({ ...p, lead_temperature: t }))}
                  >
                    {TEMP_LABELS[t]}
                  </Button>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {canCadastrar ? (
                <Button
                  type="button"
                  className={cn(btnSecondaryClass)}
                  disabled={!canEdit}
                  onClick={() => setClientDialogOpen(true)}
                >
                  <UserPlus className="h-4 w-4" />
                  Cadastrar cliente
                </Button>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Cadastro overlay exige permissão <strong>cadastrar</strong>.
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {step === 2 && (
        <div className="space-y-4 hub-panel-enter">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-xl text-sm text-muted-foreground">
              Blocos viram seções do PDF. Bibliotecas reutilizam blocos e modelos de orçamento.
            </p>
            {canEdit && (
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  className={btnAccentClass}
                  onClick={() => setAddModuleOpen(true)}
                >
                  <Plus className="h-4 w-4" />
                  Inserir bloco
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className={btnSecondaryClass}
                  onClick={() => setManageModuleTemplatesOpen(true)}
                >
                  <Boxes className="h-4 w-4" />
                  Biblioteca de Blocos
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className={btnSecondaryClass}
                  onClick={() => setProposalLibraryOpen(true)}
                >
                  <FileText className="h-4 w-4" />
                  Biblioteca de Orçamentos
                </Button>
              </div>
            )}
          </div>

          {orderedModules.length === 0 ? (
            <Card className="border-aurora-border bg-aurora-surface shadow-sm">
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                Nenhum bloco. Use <strong>Inserir bloco</strong> ou a Biblioteca de Orçamentos.
              </CardContent>
            </Card>
          ) : (
            orderedModules.map((mod, idx) => {
              const items = form.items.filter((i) => i.section === mod.id)
              const sub = moduleSubtotal(mod, form.items)
              return (
                <ItemsSection
                  key={mod.id}
                  title={mod.title}
                  section={mod.id}
                  items={items}
                  canEdit={canEdit}
                  paymentPlan={mod.payment_plan}
                  discountPct={mod.discount_pct}
                  discountValue={mod.discount_value}
                  showLabor={mod.show_labor}
                  laborHours={mod.labor_hours}
                  laborRate={mod.labor_hourly_rate}
                  subtotal={sub}
                  canMoveUp={idx > 0}
                  canMoveDown={idx < orderedModules.length - 1}
                  onMoveUp={() => moveModule(mod.id, -1)}
                  onMoveDown={() => moveModule(mod.id, 1)}
                  onRename={(title) => patchModule(mod.id, { title })}
                  onRemoveModule={() => removeModule(mod.id)}
                  onPaymentPlan={(v) => patchModule(mod.id, { payment_plan: v })}
                  onDiscountPct={(v) => {
                    discountSourceByModule.current[mod.id] = 'pct'
                    const mirrored = mirrorDiscountFromPct(sub, v)
                    patchModule(mod.id, {
                      discount_pct: mirrored.pct,
                      discount_value: mirrored.value,
                    })
                  }}
                  onDiscountValue={(v) => {
                    discountSourceByModule.current[mod.id] = 'value'
                    const mirrored = mirrorDiscountFromValue(sub, v)
                    patchModule(mod.id, {
                      discount_pct: mirrored.pct,
                      discount_value: mirrored.value,
                    })
                  }}
                  onLaborHours={(v) => patchModule(mod.id, { labor_hours: v })}
                  onLaborRate={(v) => patchModule(mod.id, { labor_hourly_rate: v })}
                  notes={mod.notes}
                  billedByName={mod.billed_by_name}
                  billedByCnpj={mod.billed_by_cnpj}
                  simplified={mod.simplified}
                  displayName={mod.display_name}
                  onNotes={(v) => patchModule(mod.id, { notes: v })}
                  onBilledByName={(v) => patchModule(mod.id, { billed_by_name: v })}
                  onBilledByCnpj={(v) => patchModule(mod.id, { billed_by_cnpj: v })}
                  onSimplified={(v) => patchModule(mod.id, { simplified: v })}
                  onDisplayName={(v) => patchModule(mod.id, { display_name: v })}
                  onAdd={() => addItem(mod.id)}
                  onRemove={removeItem}
                  onUpdate={updateItem}
                />
              )
            })
          )}

          {canEdit && (
            <div className="flex justify-end">
              <Button
                type="button"
                size="sm"
                className={btnSecondaryClass}
                onClick={() => {
                  setSaveProposalName('')
                  setSaveProposalOpen(true)
                }}
              >
                <FileText className="h-4 w-4" />
                Salvar modelo de orçamento
              </Button>
            </div>
          )}

          <Dialog open={addModuleOpen} onOpenChange={setAddModuleOpen}>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Inserir bloco</DialogTitle>
                <DialogDescription>
                  Escolha um bloco da biblioteca, restaure um preset ou comece em branco.
                </DialogDescription>
              </DialogHeader>
              <div className="max-h-[min(70vh,36rem)] space-y-4 overflow-y-auto pr-1">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={insertBlockSearch}
                    onChange={(e) => setInsertBlockSearch(e.target.value)}
                    placeholder="Pesquisar blocos…"
                    className="pl-8"
                    aria-label="Pesquisar blocos da biblioteca"
                  />
                </div>
                {moduleTemplatesQuery.isPending && (
                  <p className="text-xs text-muted-foreground">Carregando biblioteca…</p>
                )}
                {!moduleTemplatesQuery.isPending && moduleTemplates.length === 0 && (
                  <div className="rounded-lg border border-dashed border-aurora-border bg-aurora-surface-2/40 px-4 py-6 text-center">
                    <p className="text-sm text-muted-foreground">
                      Nenhum bloco na biblioteca ainda.
                    </p>
                    <Button
                      type="button"
                      size="sm"
                      className={cn(btnAccentClass, 'mt-3')}
                      onClick={() => {
                        setAddModuleOpen(false)
                        setManageModuleTemplatesOpen(true)
                      }}
                    >
                      <Boxes className="h-4 w-4" />
                      Abrir Biblioteca
                    </Button>
                  </div>
                )}
                {filteredInsertTemplates.length > 0 && (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {filteredInsertTemplates.map((tpl) => {
                      const importTitle = moduleTitleFromTemplate(tpl)
                      const itemCount = tpl.lines.length
                      return (
                        <button
                          key={tpl.id}
                          type="button"
                          className={cn(
                            'flex flex-col items-start gap-1 rounded-lg border border-aurora-border bg-aurora-surface-2/30 p-3 text-left transition-colors',
                            'hover:border-aurora-info/50 hover:bg-aurora-info/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-aurora-info/40',
                          )}
                          onClick={() => addModuleFromTemplate(tpl)}
                        >
                          <span className="line-clamp-2 text-sm font-semibold text-foreground">
                            {importTitle}
                          </span>
                          <span className="text-[11px] text-muted-foreground">
                            {itemCount === 1 ? '1 item' : `${itemCount} itens`}
                            {tpl.show_labor ? ' · MO' : ''}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                )}
                {(!hasImplant || !hasMonthly) && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Restaurar
                    </p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {!hasImplant && (
                        <button
                          type="button"
                          className={cn(
                            'rounded-lg border border-aurora-border bg-aurora-surface-2/30 p-3 text-left text-sm font-medium',
                            'hover:border-aurora-accent/50 hover:bg-aurora-accent/5',
                          )}
                          onClick={() => restorePreset('implantacao')}
                        >
                          Restaurar Implantação
                        </button>
                      )}
                      {!hasMonthly && (
                        <button
                          type="button"
                          className={cn(
                            'rounded-lg border border-aurora-border bg-aurora-surface-2/30 p-3 text-left text-sm font-medium',
                            'hover:border-aurora-brand-red/50 hover:bg-aurora-brand-red/5',
                          )}
                          onClick={() => restorePreset('mensalidade')}
                        >
                          Restaurar Mensalidade
                        </button>
                      )}
                    </div>
                  </div>
                )}
                <div className="space-y-2 border-t border-aurora-border/70 pt-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Em branco
                  </p>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <Label htmlFor="custom-mod-title">Título do bloco</Label>
                      <Input
                        id="custom-mod-title"
                        value={customModuleTitle}
                        onChange={(e) => setCustomModuleTitle(e.target.value)}
                        placeholder="Ex.: Licenças"
                        maxLength={200}
                      />
                    </div>
                    <Button
                      type="button"
                      className={btnSecondaryClass}
                      onClick={addCustomModule}
                    >
                      Criar em branco
                    </Button>
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  className={btnSecondaryClass}
                  onClick={() => setAddModuleOpen(false)}
                >
                  Cancelar
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog
            open={manageModuleTemplatesOpen}
            onOpenChange={setManageModuleTemplatesOpen}
          >
            <DialogContent className="max-w-3xl">
              <DialogHeader>
                <DialogTitle>Biblioteca de Blocos</DialogTitle>
                <DialogDescription>
                  CRUD de blocos reutilizáveis. Implantação e Mensalidade não entram aqui.
                </DialogDescription>
              </DialogHeader>
              <QuoteModuleTemplatesPanel embedded />
            </DialogContent>
          </Dialog>

          <Dialog open={proposalLibraryOpen} onOpenChange={setProposalLibraryOpen}>
            <DialogContent className="max-w-3xl">
              <DialogHeader>
                <DialogTitle>Biblioteca de Orçamentos</DialogTitle>
                <DialogDescription>
                  Selecione um modelo para substituir os blocos deste rascunho.
                </DialogDescription>
              </DialogHeader>
              <QuoteProposalTemplatesPanel embedded onSelect={applyProposalTemplate} />
            </DialogContent>
          </Dialog>

          <Dialog open={saveProposalOpen} onOpenChange={setSaveProposalOpen}>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>Salvar modelo de orçamento</DialogTitle>
                <DialogDescription>
                  Grava os blocos, itens e condições atuais (sem dados do cliente).
                </DialogDescription>
              </DialogHeader>
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault()
                  const name = saveProposalName.trim()
                  if (!name) {
                    toast.error('Informe o nome do modelo.')
                    return
                  }
                  if (!form) return
                  const payload = formToUpdate(form)
                  saveProposalMutation.mutate({
                    name,
                    modules: payload.modules ?? [],
                    items: payload.items ?? [],
                  })
                }}
              >
                <div className="space-y-1.5">
                  <Label htmlFor="proposal-template-name">Nome</Label>
                  <Input
                    id="proposal-template-name"
                    value={saveProposalName}
                    onChange={(e) => setSaveProposalName(e.target.value)}
                    maxLength={200}
                    placeholder="Ex.: Pacote M365 padrão"
                  />
                </div>
                <DialogFooter>
                  <Button
                    type="button"
                    className={btnSecondaryClass}
                    onClick={() => setSaveProposalOpen(false)}
                  >
                    Cancelar
                  </Button>
                  <Button
                    type="submit"
                    className={btnAccentClass}
                    disabled={saveProposalMutation.isPending}
                  >
                    {saveProposalMutation.isPending ? 'Salvando…' : 'Salvar'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4 hub-panel-enter">
          <Card className="border-aurora-border border-l-4 border-l-aurora-accent bg-aurora-surface shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <UserRound className="h-4 w-4 text-aurora-accent" aria-hidden />
                <CardTitle className="text-base">Resumo do cliente</CardTitle>
                <Badge
                  variant="outline"
                  className="border-aurora-accent/40 bg-aurora-accent-muted text-aurora-accent"
                >
                  Passo 3
                </Badge>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Confira vínculo e lead antes de enviar.
              </p>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-3 sm:grid-cols-2">
                <div
                  className={cn(
                    'aurora-motion rounded-xl border border-aurora-border bg-aurora-surface-2/50 p-3',
                    'hover:border-aurora-accent/40 hover:shadow-sm',
                  )}
                >
                  <dt className="text-xs text-muted-foreground">CNPJ</dt>
                  <dd className="mt-1 font-mono text-sm font-semibold">{formatCnpj(form.cnpj)}</dd>
                </div>
                <div
                  className={cn(
                    'aurora-motion rounded-xl border border-aurora-border bg-aurora-surface-2/50 p-3',
                    'hover:border-aurora-accent/40 hover:shadow-sm',
                  )}
                >
                  <dt className="text-xs text-muted-foreground">Cliente</dt>
                  <dd className="mt-1 text-sm font-semibold">{form.client_name || '—'}</dd>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {form.tiflux_client_id != null ? (
                      <Badge
                        variant="outline"
                        className="border-aurora-accent/40 bg-aurora-accent-muted text-aurora-accent"
                      >
                        TiFlux #{form.tiflux_client_id}
                      </Badge>
                    ) : null}
                    {form.vhsys_client_id != null ? (
                      <Badge
                        variant="outline"
                        className="border-aurora-brand-red/40 bg-aurora-brand-red/10 text-aurora-brand-red"
                      >
                        VHSYS #{form.vhsys_client_id}
                      </Badge>
                    ) : null}
                  </div>
                </div>
                <div
                  className={cn(
                    'aurora-motion rounded-xl border border-aurora-border bg-aurora-surface-2/50 p-3',
                    'hover:border-aurora-accent/40 hover:shadow-sm',
                  )}
                >
                  <dt className="text-xs text-muted-foreground">Temperatura</dt>
                  <dd className="mt-2">
                    {form.lead_temperature ? (
                      <Badge
                        variant="outline"
                        className={cn('border', TEMP_CHIP[form.lead_temperature])}
                      >
                        {TEMP_LABELS[form.lead_temperature]}
                      </Badge>
                    ) : (
                      <span className="text-sm text-muted-foreground">—</span>
                    )}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          {moduleNets.map(({ mod, sub }) => (
            <ReviewBlock
              key={mod.id}
              title={mod.title}
              section={mod.id}
              items={form.items.filter((i) => i.section === mod.id)}
              paymentPlan={mod.payment_plan}
              discountPct={mod.discount_pct}
              discountValue={mod.discount_value}
              showLabor={mod.show_labor}
              laborHours={mod.labor_hours}
              laborRate={mod.labor_hourly_rate}
              notes={mod.notes}
              billedByName={mod.billed_by_name}
              subtotal={sub}
            />
          ))}

          <div
            className={cn(
              'grid gap-3 rounded-xl border border-aurora-border p-4',
              'bg-gradient-to-br from-aurora-accent-muted/35 to-aurora-brand-red/10',
              moduleNets.length > 1 ? 'sm:grid-cols-2' : 'sm:grid-cols-1',
            )}
          >
            {moduleNets.map(({ mod, net }) => (
              <div
                key={mod.id}
                className="flex items-center justify-between gap-2 rounded-lg border border-aurora-accent/30 bg-aurora-surface/80 px-3 py-2.5"
              >
                <span className="text-sm font-medium text-aurora-accent">
                  Total {mod.title}
                </span>
                <span className="text-sm font-semibold tabular-nums">{money(net.net)}</span>
              </div>
            ))}
            <div className="flex items-center justify-between gap-2 rounded-lg border border-aurora-brand-red/30 bg-aurora-surface/80 px-3 py-2.5 sm:col-span-full">
              <span className="text-sm font-medium text-aurora-brand-red">Total geral</span>
              <span className="text-sm font-semibold tabular-nums">{money(grandTotal)}</span>
            </div>
          </div>

          <Card className="border-aurora-border border-l-4 border-l-aurora-accent bg-aurora-surface shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <StickyNote className="h-4 w-4 text-aurora-accent" aria-hidden />
                <CardTitle className="text-base">Observações</CardTitle>
                <Badge
                  variant="outline"
                  className="border-aurora-accent/40 bg-aurora-accent-muted text-aurora-accent"
                >
                  PDF
                </Badge>
                {canEdit ? (
                  <Button
                    type="button"
                    size="sm"
                    className={cn(btnSecondaryClass, 'ml-auto')}
                    onClick={() => setMonthlyOpen(true)}
                  >
                    <Repeat className="h-4 w-4" />
                    Mensalidades
                  </Button>
                ) : monthlyDraft ? (
                  <Badge variant="outline">Mensalidades</Badge>
                ) : null}
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Pré-preenchido com aviso e Ticket no. — editável. Impresso no bloco OBSERVAÇÕES do PDF.
              </p>
            </CardHeader>
            <CardContent>
              <Label htmlFor="review-notes" className="sr-only">
                Observações do orçamento
              </Label>
              <textarea
                id="review-notes"
                rows={4}
                maxLength={4000}
                disabled={!canEdit}
                value={form.notes}
                placeholder="Ex.: Forma de pagamento Serviços: Boleto… / Produtos: Boleto mensal…"
                className={cn(inputClass, 'min-h-[96px] resize-y py-2.5')}
                onChange={(e) => patchForm((p) => ({ ...p, notes: e.target.value }))}
              />
              <p className="mt-1.5 text-right text-[11px] text-muted-foreground tabular-nums">
                {form.notes.length}/4000
              </p>
            </CardContent>
          </Card>

          <Card className="border-aurora-border border-l-4 border-l-aurora-info bg-aurora-surface shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <Mail className="h-4 w-4 text-aurora-info" aria-hidden />
                <CardTitle className="text-base">Envio por e-mail</CardTitle>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Destinatário principal (VHSYS) e cópias adicionais antes de enviar.
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="review-client-email">E-mail a ser enviado (Para)</Label>
                <Input
                  id="review-client-email"
                  type="email"
                  value={form.client_email}
                  disabled={!canEdit}
                  placeholder="Puxado do contato TiFlux…"
                  onChange={(e) =>
                    patchForm((p) => ({ ...p, client_email: e.target.value }))
                  }
                />
                <p className="text-[11px] text-muted-foreground">
                  Prefill automático do e-mail cadastrado no TiFlux (editável).
                </p>
              </div>
              <div className="space-y-2">
                <Label>Destinatários extras (CC)</Label>
                {form.extra_recipients.length > 0 ? (
                  <ul className="flex flex-wrap gap-2">
                    {form.extra_recipients.map((email) => (
                      <li
                        key={email}
                        className={cn(
                          'aurora-motion inline-flex items-center gap-1 rounded-lg border border-aurora-border',
                          'bg-aurora-surface-2/60 px-2.5 py-1 text-xs hover:border-aurora-accent/40',
                        )}
                      >
                        <span className="font-mono">{email}</span>
                        {canEdit ? (
                          <button
                            type="button"
                            className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                            aria-label={`Remover ${email}`}
                            onClick={() =>
                              patchForm((p) => ({
                                ...p,
                                extra_recipients: p.extra_recipients.filter((e) => e !== email),
                              }))
                            }
                          >
                            <X className="h-3 w-3" />
                          </button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground">Nenhum destinatário extra.</p>
                )}
                {canEdit ? (
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Input
                      type="email"
                      value={extraEmailDraft}
                      placeholder="adicionar@email.com"
                      onChange={(e) => setExtraEmailDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          addExtraRecipient()
                        }
                      }}
                    />
                    <Button
                      type="button"
                      size="sm"
                      className={btnSecondaryClass}
                      onClick={addExtraRecipient}
                    >
                      <Plus className="h-4 w-4" />
                      Adicionar
                    </Button>
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Card className="border-aurora-border bg-aurora-surface shadow-sm">
            <CardContent className="space-y-3 p-4">
              <Alert>
                <AlertDescription>
                  {isQuoteSubmittable(quote.status)
                    ? 'Enviar registra o orçamento e dispara o envio aos destinatários acima.'
                    : isQuoteMarkSentEligible(quote.status)
                      ? 'Orçamento submetido. Opcional: marcar como enviado ao cliente (quote.sent).'
                      : 'PDF local disponível abaixo. Envio só a partir de rascunho.'}
                </AlertDescription>
              </Alert>

              <div className="flex flex-wrap gap-2">
                {canEdit && (
                  <Button
                    type="button"
                    className={btnSecondaryClass}
                    onClick={handleManualSave}
                    disabled={
                      saveMutation.isPending ||
                      submitMutation.isPending ||
                      versionSaving
                    }
                  >
                    {versionSaving || saveMutation.isPending ? 'Salvando…' : 'Salvar orçamento'}
                  </Button>
                )}
                {isQuoteSubmittable(quote.status) && (
                  <Button
                    type="button"
                    className={btnAccentClass}
                    onClick={handleSubmit}
                    disabled={submitMutation.isPending || saveMutation.isPending}
                    aria-label="Enviar orçamento"
                  >
                    {submitMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                    {submitMutation.isPending ? 'Enviando…' : 'Enviar'}
                  </Button>
                )}
                {isQuoteMarkSentEligible(quote.status) && (
                  <Button
                    type="button"
                    className={btnAccentClass}
                    onClick={() => markSentMutation.mutate()}
                    disabled={markSentMutation.isPending}
                    aria-label="Marcar como enviado ao cliente"
                  >
                    {markSentMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                    {markSentMutation.isPending ? 'Marcando…' : 'Marcar enviado'}
                  </Button>
                )}
                <Button
                  type="button"
                  className={btnSecondaryClass}
                  onClick={() => void handleGeneratePdf()}
                  disabled={pdfPending}
                >
                  {pdfPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <FileDown className="h-4 w-4" />
                  )}
                  PDF
                </Button>
              </div>
              {versions.length > 0 ? (
                <div className="space-y-1.5 pt-1">
                  <p className="text-xs text-muted-foreground">Histórico de versões</p>
                  <div className="flex flex-wrap gap-1.5">
                    {versions.map((v) => (
                      <Button
                        key={v.id}
                        type="button"
                        size="sm"
                        className={btnSecondaryClass}
                        disabled={versionPdfPending === v.id}
                        onClick={() => void handleDownloadVersionPdf(v.id, v.version_number)}
                      >
                        {versionPdfPending === v.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <FileDown className="h-3.5 w-3.5" />
                        )}
                        v{v.version_number}
                      </Button>
                    ))}
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-aurora-border pt-4">
        <Button
          type="button"
          className={btnSecondaryClass}
          disabled={step <= 1}
          onClick={() => setStep((s) => Math.max(1, s - 1))}
        >
          Voltar
        </Button>
        <div className="flex gap-2">
          {step < 3 ? (
            <Button
              type="button"
              className={btnAccentClass}
              onClick={() => setStep((s) => Math.min(3, s + 1))}
            >
              Próximo
            </Button>
          ) : (
            <Button
              type="button"
              className={btnSecondaryClass}
              onClick={() => navigate('/orcamentos')}
            >
              Voltar à lista
            </Button>
          )}
        </div>
      </div>

      {canCadastrar && (
        <QuoteClientRegisterDialog
          open={clientDialogOpen}
          onOpenChange={setClientDialogOpen}
          initialCnpj={form.cnpj}
          onLinked={applyClientLink}
        />
      )}

      <QuoteMonthlyChargesDialog
        open={monthlyOpen}
        onOpenChange={setMonthlyOpen}
        quoteId={quoteId}
        lines={monthlyLines}
        canEdit={canEdit}
        initialDraft={monthlyDraft}
        saving={monthlySaving}
        onSave={handleMonthlySave}
      />
    </div>
  )
}

function SaveIndicator({
  status,
  lastSavedAt,
}: {
  status: SaveStatus
  lastSavedAt: string | null
}) {
  if (status === 'saving') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Salvando…
      </span>
    )
  }
  if (status === 'dirty') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        Alterações pendentes
      </span>
    )
  }
  if (status === 'error') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-aurora-danger">
        <CloudOff className="h-3.5 w-3.5" />
        Erro ao salvar
      </span>
    )
  }
  if (status === 'saved' || lastSavedAt) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <Check className="h-3.5 w-3.5 text-emerald-600" />
        Salvo{lastSavedAt ? ` · ${formatDate(lastSavedAt)}` : ''}
      </span>
    )
  }
  return null
}

function templateLinesFromDraftItems(
  items: DraftItem[],
  opts?: { silent?: boolean },
): QuoteTemplateLine[] | null {
  const silent = opts?.silent === true
  const lines: QuoteTemplateLine[] = []
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    const name = item.name.trim()
    if (!name) {
      if (!silent) toast.error(`Linha ${i + 1}: informe a descrição.`)
      return null
    }
    const qty = Number(item.qty.replace(',', '.'))
    const unitValue = Number(item.unit_value.replace(',', '.'))
    if (!Number.isFinite(qty) || qty <= 0) {
      if (!silent) toast.error(`Linha ${i + 1}: quantidade inválida.`)
      return null
    }
    if (!Number.isFinite(unitValue) || unitValue < 0) {
      if (!silent) toast.error(`Linha ${i + 1}: valor unitário inválido.`)
      return null
    }
    lines.push({ name, qty, unit_value: unitValue, sort_order: i })
  }
  if (lines.length === 0) {
    if (!silent) toast.error('Adicione ao menos um item antes de salvar na biblioteca.')
    return null
  }
  return lines
}

function ItemsSection({
  title,
  section,
  items,
  canEdit,
  paymentPlan,
  discountPct,
  discountValue,
  showLabor = true,
  laborHours,
  laborRate,
  subtotal,
  canMoveUp = false,
  canMoveDown = false,
  onMoveUp,
  onMoveDown,
  onRename,
  onRemoveModule,
  onPaymentPlan,
  onDiscountPct,
  onDiscountValue,
  onLaborHours,
  onLaborRate,
  notes,
  billedByName,
  billedByCnpj,
  simplified,
  displayName,
  onNotes,
  onBilledByName,
  onBilledByCnpj,
  onSimplified,
  onDisplayName,
  onAdd,
  onRemove,
  onUpdate,
}: {
  title: string
  section: QuoteSection
  items: DraftItem[]
  canEdit: boolean
  paymentPlan: string
  discountPct: string
  discountValue: string
  showLabor?: boolean
  laborHours: string
  laborRate: string
  subtotal: number
  canMoveUp?: boolean
  canMoveDown?: boolean
  onMoveUp?: () => void
  onMoveDown?: () => void
  onRename?: (title: string) => void
  onRemoveModule?: () => void
  onPaymentPlan: (v: string) => void
  onDiscountPct: (v: string) => void
  onDiscountValue: (v: string) => void
  onLaborHours: (v: string) => void
  onLaborRate: (v: string) => void
  notes: string
  billedByName: string
  billedByCnpj: string
  simplified: boolean
  displayName: string
  onNotes: (v: string) => void
  onBilledByName: (v: string) => void
  onBilledByCnpj: (v: string) => void
  onSimplified: (v: boolean) => void
  onDisplayName: (v: string) => void
  onAdd: () => void
  onRemove: (localKey: string) => void
  onUpdate: (localKey: string, patch: Partial<DraftItem>) => void
}) {
  const queryClient = useQueryClient()
  const [saveAsModuleOpen, setSaveAsModuleOpen] = useState(false)
  const [saveAsModuleName, setSaveAsModuleName] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState(title)

  useEffect(() => {
    setTitleDraft(title)
  }, [title])

  const labor = showLabor ? laborTotal(laborHours, laborRate) : 0
  const isImplant = section === 'implantacao'
  const accentBorder = isImplant
    ? 'border-l-4 border-l-aurora-accent'
    : section === 'mensalidade'
      ? 'border-l-4 border-l-aurora-brand-red'
      : 'border-l-4 border-l-aurora-info'
  const usedItemNames = items.map((i) => i.name)

  const saveAsModuleMutation = useMutation({
    mutationFn: (payload: {
      name: string
      title: string
      show_labor: boolean
      notes: string | null
      billed_by_name: string | null
      billed_by_cnpj: string | null
      simplified: boolean
      display_name: string | null
      lines: QuoteTemplateLine[]
    }) => api.createQuoteModuleTemplate(payload),
    onSuccess: (created) => {
      toast.success(`Bloco “${created.name}” salvo na biblioteca`)
      setSaveAsModuleOpen(false)
      setSaveAsModuleName('')
      void queryClient.invalidateQueries({ queryKey: ['quote-module-templates'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao salvar na biblioteca')
    },
  })

  function openSaveAsModule() {
    const lines = templateLinesFromDraftItems(items, { silent: true }) ?? []
    if (lines.length === 0 && !title.trim()) {
      toast.error('Preencha o bloco antes de salvar na biblioteca.')
      return
    }
    setSaveAsModuleName(title.trim())
    setSaveAsModuleOpen(true)
  }

  function submitSaveAsModule(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = saveAsModuleName.trim()
    if (!trimmed) {
      toast.error('Informe o nome do bloco.')
      return
    }
    const lines = templateLinesFromDraftItems(items, { silent: true }) ?? []
    // Dialog tem um campo: nome no catálogo = título ao importar (ADR title).
    // Antes usava o título atual do bloco (ex. Mensalidade) e gerava mismatch.
    saveAsModuleMutation.mutate({
      name: trimmed,
      title: trimmed,
      show_labor: showLabor,
      notes: notes.trim() || null,
      billed_by_name: billedByName.trim() || null,
      billed_by_cnpj: digitsOnly(billedByCnpj) || null,
      simplified,
      display_name: displayName.trim() || null,
      lines,
    })
  }

  return (
    <Card className={cn('border-aurora-border bg-aurora-surface shadow-sm', accentBorder)}>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              {editingTitle && canEdit && onRename ? (
                <Input
                  value={titleDraft}
                  autoFocus
                  className="h-8 max-w-xs text-base font-semibold"
                  onChange={(e) => setTitleDraft(e.target.value)}
                  onBlur={() => {
                    const next = titleDraft.trim()
                    if (next && next !== title) onRename(next)
                    else setTitleDraft(title)
                    setEditingTitle(false)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
                    if (e.key === 'Escape') {
                      setTitleDraft(title)
                      setEditingTitle(false)
                    }
                  }}
                />
              ) : (
                <CardTitle className="text-base">{title}</CardTitle>
              )}
              {canEdit && onRename ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  aria-label="Renomear bloco"
                  onClick={() => setEditingTitle(true)}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
              ) : null}
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Checkbox
                  checked={simplified}
                  disabled={!canEdit}
                  onCheckedChange={(v) => onSimplified(v === true)}
                  aria-label="Simplificar bloco"
                />
                Simplificar
              </label>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {canEdit && (
              <>
                <Button
                  type="button"
                  size="sm"
                  className={cn(btnSecondaryClass, 'h-8 px-2')}
                  disabled={!canMoveUp}
                  onClick={onMoveUp}
                  aria-label="Mover bloco para cima"
                >
                  <ChevronUp className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className={cn(btnSecondaryClass, 'h-8 px-2')}
                  disabled={!canMoveDown}
                  onClick={onMoveDown}
                  aria-label="Mover bloco para baixo"
                >
                  <ChevronDown className="h-4 w-4" />
                </Button>
                {!simplified && (
                  <Button type="button" size="sm" className={btnSecondaryClass} onClick={onAdd}>
                    <Plus className="h-4 w-4" />
                    Item
                  </Button>
                )}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      size="sm"
                      className={cn(btnSecondaryClass, 'h-8 px-2')}
                      aria-label={`Mais ações do bloco ${title}`}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={openSaveAsModule}>
                      Salvar na biblioteca
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                {onRemoveModule ? (
                  <Button
                    type="button"
                    size="sm"
                    className={cn(btnDangerClass, 'h-8 px-2')}
                    onClick={onRemoveModule}
                    aria-label={`Remover bloco ${title}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                ) : null}
              </>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {simplified ? (
          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <div className="space-y-1">
              <Label>Nome de Exibição</Label>
              <Input
                value={displayName}
                disabled={!canEdit}
                placeholder={title}
                onChange={(e) => onDisplayName(e.target.value)}
              />
            </div>
            <div className="flex flex-col justify-end">
              <span className="text-xs text-muted-foreground">Valor somado</span>
              <span className="text-sm font-semibold tabular-nums">{money(subtotal)}</span>
            </div>
          </div>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum item neste bloco.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((item) => (
              <li
                key={item.localKey}
                className="grid gap-2 rounded-lg border border-aurora-border/80 p-3 sm:grid-cols-[1fr_5rem_7rem_auto]"
              >
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Descrição</Label>
                  <VhsysItemSearch
                    value={item.name}
                    disabled={!canEdit}
                    excludeNames={usedItemNames}
                    unitValue={parseNonNegativeNumber(item.unit_value)}
                    onChange={(name) => onUpdate(item.localKey, { name, vhsys_product_id: null })}
                    onSelect={(catalog) =>
                      onUpdate(item.localKey, {
                        name: catalog.name,
                        unit_value:
                          catalog.unit_value > 0 ? String(catalog.unit_value) : item.unit_value,
                        vhsys_product_id: catalog.id,
                      })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Qtd</Label>
                  <Input
                    inputMode="decimal"
                    value={item.qty}
                    disabled={!canEdit}
                    onChange={(e) => onUpdate(item.localKey, { qty: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Valor unitário</Label>
                  <Input
                    inputMode="decimal"
                    value={item.unit_value}
                    disabled={!canEdit}
                    placeholder="0"
                    onChange={(e) => onUpdate(item.localKey, { unit_value: e.target.value })}
                  />
                </div>
                <div className="flex items-end justify-between gap-2 sm:flex-col sm:items-end">
                  <span className="text-sm font-medium tabular-nums">
                    {money(lineTotal(item))}
                  </span>
                  {canEdit && (
                    <Button
                      type="button"
                      size="sm"
                      className={cn(btnDangerClass, 'h-8 px-2')}
                      onClick={() => onRemove(item.localKey)}
                      aria-label="Remover item"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}

        <Accordion type="single" collapsible className="rounded-lg border border-aurora-border/80 px-3">
          <AccordionItem value="conditions" className="border-0">
            <AccordionTrigger className="py-3 text-sm hover:no-underline">
              Condições (desconto, pagamento{showLabor ? ', mão de obra' : ''})
            </AccordionTrigger>
            <AccordionContent className="space-y-4 pb-3">
              {showLabor ? (
                <div className="rounded-lg border border-aurora-border/60 p-3">
                  <p className="mb-2 text-sm font-medium">Mão de obra</p>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Horas</Label>
                      <Input
                        inputMode="decimal"
                        value={laborHours}
                        disabled={!canEdit}
                        placeholder="0"
                        onChange={(e) => onLaborHours(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Valor hora</Label>
                      <Input
                        inputMode="decimal"
                        value={laborRate}
                        disabled={!canEdit}
                        placeholder="0"
                        onChange={(e) => onLaborRate(e.target.value)}
                      />
                    </div>
                    <div className="flex flex-col justify-end">
                      <span className="text-xs text-muted-foreground">Total mão de obra</span>
                      <span className="text-sm font-semibold tabular-nums">{money(labor)}</span>
                    </div>
                  </div>
                </div>
              ) : null}

              <PaymentPlanFields
                paymentPlan={paymentPlan}
                canEdit={canEdit}
                onPaymentPlan={onPaymentPlan}
              />

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Desconto %</Label>
                  <Input
                    inputMode="decimal"
                    value={discountPct}
                    disabled={!canEdit}
                    onChange={(e) => onDiscountPct(e.target.value)}
                    placeholder="0"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Desconto R$</Label>
                  <Input
                    inputMode="decimal"
                    value={discountValue}
                    disabled={!canEdit}
                    onChange={(e) => onDiscountValue(e.target.value)}
                    placeholder="0"
                  />
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        <div className="grid gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Label htmlFor={`mod-notes-${section}`}>Observações</Label>
              <Badge
                variant="outline"
                className="border-aurora-accent/40 bg-aurora-accent-muted text-aurora-accent"
              >
                Opcional
              </Badge>
            </div>
            <textarea
              id={`mod-notes-${section}`}
              rows={3}
              maxLength={4000}
              disabled={!canEdit}
              value={notes}
              placeholder="Condições deste bloco…"
              className={cn(inputClass, 'min-h-[72px] resize-y py-2.5')}
              onChange={(e) => onNotes(e.target.value)}
            />
            <p className="text-right text-[11px] text-muted-foreground tabular-nums">
              {notes.length}/4000
            </p>
          </div>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Label htmlFor={`mod-billed-${section}`}>Faturado por</Label>
              <Badge
                variant="outline"
                className="border-aurora-info/40 bg-aurora-info/15 text-aurora-info"
              >
                Opcional
              </Badge>
            </div>
            <VhsysPartySearch
              value={billedByName}
              disabled={!canEdit}
              placeholder="Buscar distribuidor/fornecedor no VHSYS…"
              onChange={(v) => {
                onBilledByName(v)
                if (!v.trim()) onBilledByCnpj('')
              }}
              onSelect={(party) => {
                onBilledByName(party.fantasy_name || party.name)
                onBilledByCnpj(party.cnpj ? digitsOnly(party.cnpj) : '')
              }}
            />
            {billedByCnpj ? (
              <p className="text-xs text-muted-foreground">CNPJ: {formatCnpj(billedByCnpj)}</p>
            ) : null}
          </div>
        </div>

        {(() => {
          const { discount, net } = applySectionDiscount(subtotal, discountPct, discountValue)
          return (
            <div className="space-y-1 text-right text-sm">
              <p className="tabular-nums text-muted-foreground">
                {showLabor
                  ? `Subtotal (itens + mão de obra): ${money(subtotal)}`
                  : `Subtotal (itens): ${money(subtotal)}`}
              </p>
              {discount > 0 ? (
                <p className="tabular-nums text-muted-foreground">Desconto: −{money(discount)}</p>
              ) : null}
              <p className="font-semibold tabular-nums">Total: {money(net)}</p>
            </div>
          )
        })()}
      </CardContent>

      <Dialog open={saveAsModuleOpen} onOpenChange={setSaveAsModuleOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Salvar na biblioteca</DialogTitle>
            <DialogDescription>
              Salva {items.length} item(ns)
              {showLabor ? ' + mão de obra' : ''} na biblioteca. O nome vira o título do bloco ao
              inserir (ex. Licenças).
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitSaveAsModule} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor={`save-as-mod-name-${section}`}>Nome do bloco</Label>
              <Input
                id={`save-as-mod-name-${section}`}
                value={saveAsModuleName}
                onChange={(e) => setSaveAsModuleName(e.target.value)}
                placeholder={`Ex.: ${title || 'Licenças'}`}
                maxLength={200}
                autoFocus
                required
              />
            </div>
            <DialogFooter>
              <Button
                type="button"
                className={btnSecondaryClass}
                disabled={saveAsModuleMutation.isPending}
                onClick={() => setSaveAsModuleOpen(false)}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                className={btnAccentClass}
                disabled={saveAsModuleMutation.isPending}
              >
                {saveAsModuleMutation.isPending ? 'Salvando…' : 'Salvar na biblioteca'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

function PaymentPlanFields({
  paymentPlan,
  canEdit,
  onPaymentPlan,
}: {
  paymentPlan: string
  canEdit: boolean
  onPaymentPlan: (v: string) => void
}) {
  const { mode, installments } = parsePaymentPlan(paymentPlan)
  const modeValue = mode || NONE
  const showValueField = mode === 'parcelado' || mode === 'recorrente_anual'
  const monthsValue = String(installments ?? (mode === 'recorrente_anual' ? 12 : 2))

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="space-y-2">
        <Label>Forma de pagamento</Label>
        <Select
          value={modeValue}
          disabled={!canEdit}
          onValueChange={(v) => {
            if (v === NONE) {
              onPaymentPlan('')
              return
            }
            if (v === 'a_vista') {
              onPaymentPlan('a_vista')
              return
            }
            if (v === 'recorrente_anual') {
              onPaymentPlan(buildPaymentPlan('recorrente_anual', installments ?? 12))
              return
            }
            onPaymentPlan(buildPaymentPlan('parcelado', installments ?? 2))
          }}
        >
          <SelectTrigger aria-label="Forma de pagamento">
            <SelectValue placeholder="Opcional" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>Não informado</SelectItem>
            <SelectItem value="a_vista">À vista</SelectItem>
            <SelectItem value="parcelado">Parcelado</SelectItem>
            <SelectItem value="recorrente_anual">{RECORRENTE_LABEL}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {showValueField ? (
        <div className="space-y-2">
          <Label>{mode === 'recorrente_anual' ? 'Meses (recorrência)' : 'Parcelas'}</Label>
          <Select
            value={monthsValue}
            disabled={!canEdit}
            onValueChange={(v) =>
              onPaymentPlan(
                buildPaymentPlan(
                  mode === 'recorrente_anual' ? 'recorrente_anual' : 'parcelado',
                  Number(v),
                ),
              )
            }
          >
            <SelectTrigger aria-label={mode === 'recorrente_anual' ? 'Meses' : 'Parcelas'}>
              <SelectValue placeholder={mode === 'recorrente_anual' ? 'Meses' : 'Parcelas'} />
            </SelectTrigger>
            <SelectContent>
              {INSTALLMENT_OPTIONS.map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n}x
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
    </div>
  )
}

function ReviewBlock({
  title,
  section,
  items,
  paymentPlan,
  discountPct,
  discountValue,
  showLabor,
  laborHours,
  laborRate,
  notes,
  billedByName,
  subtotal,
}: {
  title: string
  section: QuoteSection
  items: DraftItem[]
  paymentPlan: string
  discountPct: string
  discountValue: string
  showLabor: boolean
  laborHours: string
  laborRate: string
  notes: string
  billedByName: string
  subtotal: number
}) {
  const { discount, net } = applySectionDiscount(subtotal, discountPct, discountValue)
  const labor = showLabor ? laborTotal(laborHours, laborRate) : 0
  const isImplant = section === 'implantacao'
  const isMonthly = section === 'mensalidade'

  return (
    <Card
      className={cn(
        'border-aurora-border bg-aurora-surface shadow-sm',
        isImplant
          ? 'border-l-4 border-l-aurora-accent'
          : isMonthly
            ? 'border-l-4 border-l-aurora-brand-red'
            : 'border-l-4 border-l-aurora-info',
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">{title}</CardTitle>
          <Badge
            variant="outline"
            className={cn(
              isImplant
                ? 'border-aurora-accent/40 bg-aurora-accent-muted text-aurora-accent'
                : isMonthly
                  ? 'border-aurora-brand-red/40 bg-aurora-brand-red/10 text-aurora-brand-red'
                  : 'border-aurora-info/40 bg-aurora-info/15 text-aurora-info',
            )}
          >
            {title}
          </Badge>
          <Badge variant="secondary">{items.length} item(ns)</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-aurora-border px-3 py-4 text-sm text-muted-foreground">
            Sem itens nesta seção.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {items.map((item) => (
              <li
                key={item.localKey}
                className={cn(
                  'aurora-motion flex justify-between gap-2 rounded-lg border border-aurora-border/80',
                  'bg-aurora-surface-2/40 px-3 py-2 text-sm',
                  'hover:border-aurora-accent/35 hover:shadow-sm',
                )}
              >
                <span className="truncate">
                  {item.name || 'Novo item'} × {item.qty || '0'}
                </span>
                <span className="shrink-0 tabular-nums font-medium">{money(lineTotal(item))}</span>
              </li>
            ))}
          </ul>
        )}
        {showLabor ? (
          <p className="text-xs text-muted-foreground">
            Mão de obra: {laborHours || '0'} h × {money(parseNonNegativeNumber(laborRate))} ={' '}
            {money(labor)}
          </p>
        ) : null}
        <div className="space-y-1 border-t border-aurora-border/70 pt-2 text-sm">
          <p className="text-xs text-muted-foreground">
            Pagamento: {paymentLabel(paymentPlan)}
            {discountPct ? ` · Desc. ${discountPct}%` : ''}
            {discountValue ? ` · Desc. ${money(Number(discountValue) || 0)}` : ''}
          </p>
          {billedByName.trim() ? (
            <p className="text-xs text-muted-foreground">Faturado por: {billedByName.trim()}</p>
          ) : null}
          {notes.trim() ? (
            <p className="whitespace-pre-wrap text-xs text-muted-foreground">
              Observações: {notes.trim()}
            </p>
          ) : null}
          <p className="tabular-nums text-muted-foreground">Subtotal {money(subtotal)}</p>
          {discount > 0 ? (
            <p className="tabular-nums text-muted-foreground">Desconto −{money(discount)}</p>
          ) : null}
          <p
            className={cn(
              'font-semibold tabular-nums',
              isImplant
                ? 'text-aurora-accent'
                : isMonthly
                  ? 'text-aurora-brand-red'
                  : 'text-aurora-info',
            )}
          >
            Total {money(net)}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
