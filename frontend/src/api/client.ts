import { getCsrfToken, isCsrfExempt, refreshCsrfToken, setCsrfToken } from './csrf'

export { refreshCsrfToken, setCsrfToken }

export type PermissionKey =
  | 'cadastrar'
  | 'inativar'
  | 'consultar'
  | 'empresas_inativas'
  | 'manage_users'
  | 'orcamentos'
  | 'aprovar_orcamento'
  | 'gerar_contrato'
  | 'faturar'
  | 'aprovar_fatura'

export type UserPermissions = Record<PermissionKey, boolean>

export type AuthUser = {
  email: string
  name: string
  id?: number
  dev_mode?: boolean
  permissions?: Partial<UserPermissions>
}

export type AdminUser = {
  id: number
  email: string
  name: string
  is_active: boolean
  permissions: UserPermissions
  created_at: string
  updated_at: string
  temporary_password?: string
}

export type AuditEntry = {
  id: number
  user_id: number | null
  user_email: string
  action: string
  resource: string
  detail: Record<string, unknown>
  ip_address: string
  created_at: string
}

export type QuoteStatus =
  | 'draft'
  | 'submitted'
  | 'sent'
  | 'approved'
  | 'rejected'
  | 'contracted'

/** section = module.id (seed implantacao|mensalidade + custom). */
export type QuoteSection = string
export type LegacyModuleKind = 'implantacao' | 'mensalidade'
export type LeadTemperature = 'quente' | 'morno' | 'frio'
export type BilledByType = 'distribuidor' | 'fornecedor'

export type QuoteModule = {
  id: string
  title: string
  legacy_kind: LegacyModuleKind | null
  show_labor: boolean
  payment_plan: string | null
  discount_pct: number | null
  discount_value: number | null
  labor_hours: number | null
  labor_hourly_rate: number | null
  notes: string | null
  billed_by_name: string | null
  sort_order: number
}

export type QuoteItemRead = {
  id: number
  quote_id: number
  section: QuoteSection
  name: string
  qty: number
  unit_value: number
  total_value: number
  template_key: string | null
  sort_order: number
}

export type QuoteItemWrite = {
  section: QuoteSection
  name: string
  qty: number
  unit_value: number
  template_key?: string | null
  sort_order?: number
}

export type QuoteRead = {
  id: number
  cnpj: string
  client_name: string | null
  tiflux_client_id: number | null
  vhsys_client_id: number | null
  status: QuoteStatus
  lead_temperature: LeadTemperature | null
  billed_by_type: BilledByType | null
  billed_by_name: string | null
  implant_payment_plan: string | null
  implant_discount_pct: number | null
  implant_discount_value: number | null
  implant_labor_hours: number | null
  implant_labor_hourly_rate: number | null
  monthly_payment_plan: string | null
  monthly_discount_pct: number | null
  monthly_discount_value: number | null
  monthly_labor_hours: number | null
  monthly_labor_hourly_rate: number | null
  modules: QuoteModule[]
  client_email: string | null
  extra_recipients: string[]
  notes: string | null
  tiflux_ticket_number: string | null
  vhsys_os_id: string | null
  pdf_path: string | null
  created_by: number
  created_at: string
  updated_at: string
  submitted_at: string | null
  sent_at: string | null
  approved_at: string | null
  items: QuoteItemRead[]
}

export type QuoteWrite = {
  cnpj: string
  client_name?: string | null
  tiflux_client_id?: number | null
  vhsys_client_id?: number | null
  lead_temperature?: LeadTemperature | null
  billed_by_type?: BilledByType | null
  billed_by_name?: string | null
  implant_payment_plan?: string | null
  implant_discount_pct?: number | null
  implant_discount_value?: number | null
  implant_labor_hours?: number | null
  implant_labor_hourly_rate?: number | null
  monthly_payment_plan?: string | null
  monthly_discount_pct?: number | null
  monthly_discount_value?: number | null
  monthly_labor_hours?: number | null
  monthly_labor_hourly_rate?: number | null
  modules?: QuoteModule[]
  client_email?: string | null
  extra_recipients?: string[]
  notes?: string | null
  items?: QuoteItemWrite[]
}

export type QuoteUpdate = Partial<Omit<QuoteWrite, 'items' | 'modules'>> & {
  items?: QuoteItemWrite[] | null
  modules?: QuoteModule[] | null
}

export type QuoteTemplateLine = {
  name: string
  qty: number
  unit_value: number
  sort_order: number
}

export type QuoteTemplateRead = {
  id: number
  key: string
  name: string
  section: QuoteSection
  lines: QuoteTemplateLine[]
  created_at: string
}

export type QuoteTemplateWrite = {
  key?: string | null
  name: string
  section: QuoteSection
  lines: QuoteTemplateLine[]
}

export type QuoteTemplateUpdate = {
  name?: string | null
  section?: QuoteSection | null
  lines?: QuoteTemplateLine[] | null
}

export type QuoteModuleTemplateRead = {
  id: number
  key: string
  name: string
  title: string
  show_labor: boolean
  lines: QuoteTemplateLine[]
  created_at: string
}

export type QuoteModuleTemplateWrite = {
  key?: string | null
  name: string
  title: string
  show_labor?: boolean
  lines?: QuoteTemplateLine[]
}

export type QuoteModuleTemplateUpdate = {
  name?: string | null
  title?: string | null
  show_labor?: boolean | null
  lines?: QuoteTemplateLine[] | null
}

export type VhsysCatalogItem = {
  id: number
  kind: 'produto' | 'servico'
  name: string
  code: string | null
  unit_value: number
  category_id?: number | null
}

export type VhsysCatalogCategory = {
  id: number
  name: string
}

export type TifluxQuoteClient = {
  id: number
  name: string
  cnpj: string | null
}

export type VhsysParty = {
  id: number
  name: string
  fantasy_name: string | null
  cnpj: string | null
}

export type QuotesListParams = {
  status?: QuoteStatus
  lead_temperature?: LeadTemperature
  limit?: number
  offset?: number
}

/** Resposta 202 de POST submit / mark-sent (QuoteRead + meta outbox). */
export type QuoteOutboxActionResult = QuoteRead & {
  outbox_id: number
  outbox_status: string
  dry_run: boolean
}

export type DocumentDocType = 'orcamento' | 'faturamento' | 'pdf'

export type DocumentQuoteHit = {
  id: number
  display_id: string
  doc_type: DocumentDocType
  cnpj: string
  client_name: string | null
  status: string
  lead_temperature: string | null
  billed_by_type: string | null
  billed_by_name: string | null
  vhsys_os_id: string | null
  tiflux_ticket_number: string | null
  tiflux_client_id: number | null
  has_pdf: boolean
  implant_net: number | null
  monthly_net: number | null
  value_total: number | null
  created_at: string
  updated_at: string
}

export type DocumentPdfHit = {
  quote_id: number
  display_id: string
  doc_type: DocumentDocType
  client_name: string | null
  cnpj: string
  status: string | null
  lead_temperature: string | null
  billed_by_type: string | null
  billed_by_name: string | null
  vhsys_os_id: string | null
  tiflux_ticket_number: string | null
  has_pdf: boolean
  value_total: number | null
  pdf_path: string
  created_at: string | null
  updated_at: string | null
}

export type DocumentBillingHit = {
  id: number
  doc_type: DocumentDocType
  cnpj: string
  client_name: string | null
  competence: string
  status: string
  net_total: number | null
  gross_total: number | null
  due_date: string | null
  payment_method: string | null
  vhsys_nf_id: string | null
  vhsys_cr_id: string | null
  tiflux_ticket_number: string | null
  tiflux_client_id: number | null
  created_at: string
  updated_at: string
}

export type DocumentsEnrichment = {
  tiflux: 'ok' | 'skipped' | 'error'
  vhsys: 'ok' | 'skipped' | 'error'
  detail: string | null
}

export type DocumentsSearchResponse = {
  query: string
  quotes: DocumentQuoteHit[]
  pdfs: DocumentPdfHit[]
  billing_runs: DocumentBillingHit[]
  enrichment: DocumentsEnrichment
}

/** Status elegíveis para POST /orcamentos/{id}/submit (API `_SUBMITTABLE_STATUSES`). */
export const QUOTE_SUBMITTABLE_STATUSES: ReadonlySet<QuoteStatus> = new Set(['draft'])

/** Status elegíveis para POST /orcamentos/{id}/mark-sent. */
export const QUOTE_MARK_SENT_STATUSES: ReadonlySet<QuoteStatus> = new Set(['submitted'])

export function isQuoteSubmittable(status: QuoteStatus): boolean {
  return QUOTE_SUBMITTABLE_STATUSES.has(status)
}

export function isQuoteMarkSentEligible(status: QuoteStatus): boolean {
  return QUOTE_MARK_SENT_STATUSES.has(status)
}

/** Extrai QuoteRead da resposta de submit/mark-sent. */
export function quoteFromOutboxResult(result: QuoteOutboxActionResult): QuoteRead {
  const { outbox_id: _oid, outbox_status: _ost, dry_run: _dr, ...quote } = result
  return quote
}

export type BillingStatus =
  | 'draft'
  | 'approved'
  | 'awaiting_prefeitura'
  | 'emitting'
  | 'sent'
  | 'error'

export type BillingItemSource = 'contract' | 'ticket'
export type BillingPaymentMethod = 'boleto' | 'pix'
export type BillingArtifactKind = 'report' | 'nf' | 'boleto'

export type BillingItemWrite = {
  source: BillingItemSource
  external_ref?: string | null
  description: string
  amount: number
  sort_order?: number
}

export type BillingItemRead = {
  id: number
  run_id: number
  source: BillingItemSource
  external_ref: string | null
  description: string
  amount: number
  sort_order: number
}

export type BillingArtifactWrite = {
  kind: BillingArtifactKind
  path_or_url: string
}

export type BillingArtifactRead = {
  id: number
  run_id: number
  kind: BillingArtifactKind
  path_or_url: string
  created_at: string
}

export type BillingRunWrite = {
  cnpj: string
  client_name?: string | null
  tiflux_client_id?: number | null
  vhsys_client_id?: number | null
  competence: string
  due_date?: string | null
  has_retencao?: boolean
  payment_method?: BillingPaymentMethod | null
  gross_total?: number | null
  discount_pct?: number | null
  discount_value?: number | null
  items?: BillingItemWrite[]
}

export type BillingRunUpdate = Partial<Omit<BillingRunWrite, 'items'>> & {
  items?: BillingItemWrite[] | null
}

export type BillingRunRead = {
  id: number
  cnpj: string
  client_name: string | null
  tiflux_client_id: number | null
  vhsys_client_id: number | null
  competence: string
  due_date: string | null
  status: BillingStatus
  has_retencao: boolean
  payment_method: string | null
  gross_total: number | null
  discount_pct: number | null
  discount_value: number | null
  net_total: number | null
  nf_prefeitura_number: string | null
  tiflux_ticket_number: string | null
  vhsys_nf_id: string | null
  vhsys_cr_id: string | null
  error_message: string | null
  approved_by: number | null
  created_by: number | null
  created_at: string
  updated_at: string
  approved_at: string | null
  sent_at: string | null
  items: BillingItemRead[]
  artifacts: BillingArtifactRead[]
}

export type BillingRunsListParams = {
  status?: BillingStatus
  competence?: string
  limit?: number
  offset?: number
}

export type TifluxBillingHistoryType = 'billed' | 'reversed' | 'paid'

export type TifluxBillingHistoryItem = {
  billing_id: number
  billing_date: string | null
  due_date: string | null
  client_id: number | null
  client_name: string | null
  real_value: number
  nfe_number: number | string | null
  paid: boolean
  reversal: boolean
  local_run_id: number | null
}

export type TifluxBillingHistoryParams = {
  billing_day?: string
  competence?: string
  client_id?: number
  billing_type?: TifluxBillingHistoryType
  due_start_date?: string
  due_end_date?: string
  limit?: number
  offset?: number
}

export type TifluxBillingContractRow = {
  id: number
  name: string
  amount: number
  status: string
  external_ref: string
  client_id: number | null
  client_name: string | null
  modality: string | null
  expiration_date: string | null
  readjustment_date: string | null
  local_run_id: number | null
}

export type BillingPrefeituraInput = {
  nf_prefeitura_number: string
  net_total: number
}

/** Resposta 202 de POST approve / prefeitura (BillingRunRead + meta outbox). */
export type BillingOutboxActionResult = BillingRunRead & {
  outbox_id: number | null
  outbox_status?: string | null
  dry_run: boolean
}

export function billingFromOutboxResult(result: BillingOutboxActionResult): BillingRunRead {
  const { outbox_id: _oid, outbox_status: _ost, dry_run: _dr, ...run } = result
  return run
}

export class ApiError extends Error {
  readonly status: number
  readonly body: Record<string, unknown>

  constructor(message: string, status: number, body: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

function errorMessageFromBody(data: Record<string, unknown>, status: number): string {
  const detail = data.detail ?? data.error
  if (typeof detail === 'string' && detail.trim()) return detail
  return `Erro ${status}`
}

async function withCsrfHeaders(
  url: string,
  init?: RequestInit,
): Promise<{ headers: Record<string, string>; method: string }> {
  const method = (init?.method || 'GET').toUpperCase()
  const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && !isCsrfExempt(url)
  if (needsCsrf && !getCsrfToken()) {
    await refreshCsrfToken()
  }

  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  }
  const csrf = getCsrfToken()
  if (needsCsrf && csrf) {
    headers['X-CSRF-Token'] = csrf
  }
  return { headers, method }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const { headers, method } = await withCsrfHeaders(url, init)
  if (!headers['Content-Type'] && method !== 'GET' && method !== 'HEAD') {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(url, {
    credentials: 'include',
    ...init,
    headers,
  })
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>
  if (!res.ok) {
    throw new ApiError(errorMessageFromBody(data, res.status), res.status, data)
  }
  return data as T
}

function parseContentDispositionFilename(header: string | null, fallback: string): string {
  if (!header) return fallback
  const utf = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf?.[1]) {
    try {
      return decodeURIComponent(utf[1].trim())
    } catch {
      /* fall through */
    }
  }
  const plain = header.match(/filename="?([^";]+)"?/i)
  return plain?.[1]?.trim() || fallback
}

async function requestBlob(
  url: string,
  init: RequestInit | undefined,
  fallbackFilename: string,
): Promise<{ blob: Blob; filename: string }> {
  const { headers } = await withCsrfHeaders(url, init)
  const res = await fetch(url, {
    credentials: 'include',
    ...init,
    headers,
  })
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as Record<string, unknown>
    throw new ApiError(errorMessageFromBody(data, res.status), res.status, data)
  }
  const blob = await res.blob()
  const filename = parseContentDispositionFilename(
    res.headers.get('Content-Disposition'),
    fallbackFilename,
  )
  return { blob, filename }
}

/** Integra cliente; em 409 (já cadastrado) devolve o body com IDs existentes. */
async function integrarAllowDuplicate(
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const url = '/integrar'
  const init: RequestInit = { method: 'POST', body: JSON.stringify(body) }
  const { headers } = await withCsrfHeaders(url, init)
  headers['Content-Type'] = 'application/json'

  const res = await fetch(url, {
    credentials: 'include',
    ...init,
    headers,
  })
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>
  if (res.ok || res.status === 207 || (res.status === 409 && data.all_duplicates)) {
    return data
  }
  throw new ApiError(errorMessageFromBody(data, res.status), res.status, data)
}

export function downloadBinaryBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const api = {
  me: () => request<{ authenticated: boolean; user: AuthUser }>('/auth/me'),
  login: (body: { email: string; password: string; remember_me?: boolean }) =>
    request<{ ok: boolean; redirect: string; csrf_token?: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  forgotPassword: (body: { email: string }) =>
    request<{ message: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  resetPassword: (body: { token: string; password: string }) =>
    request<{ ok: boolean; message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getProfile: () =>
    request<{ email: string; name: string; backup_email: string; phone: string }>('/auth/profile'),
  updateProfile: (body: { name: string; backup_email: string; phone: string }) =>
    request<{ email: string; name: string; backup_email: string; phone: string }>('/auth/profile', {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  changePassword: (body: { current_password: string; new_password: string; confirm_password: string }) =>
    request<{ ok: boolean; message: string }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  previewCnpj: (cnpj: string) => request<Record<string, unknown>>('/preview', { method: 'POST', body: JSON.stringify({ cnpj }) }),
  integrar: (body: Record<string, unknown>) => request<Record<string, unknown>>('/integrar', { method: 'POST', body: JSON.stringify(body) }),
  /** Preview+integrar no wizard: aceita 409 all_duplicates para linkar IDs existentes. */
  integrarForQuote: (body: Record<string, unknown>) => integrarAllowDuplicate(body),
  inativarPreview: (query: string) => request<Record<string, unknown>>('/inativar/preview', { method: 'POST', body: JSON.stringify({ query }) }),
  inativar: (query: string, tiflux_client_id: number) =>
    request<Record<string, unknown>>('/inativar', { method: 'POST', body: JSON.stringify({ query, tiflux_client_id }) }),
  consultaPreview: (query: string) => request<Record<string, unknown>>('/consulta/preview', { method: 'POST', body: JSON.stringify({ query }) }),
  consultaDetalhe: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/consulta/detalhe', { method: 'POST', body: JSON.stringify(body) }),
  consultaTifluxOpcoes: () =>
    request<{ success: boolean; desks: Array<Record<string, unknown>>; technical_groups: Array<Record<string, unknown>> }>(
      '/consulta/tiflux/opcoes',
    ),
  consultaTifluxVinculos: (body: {
    tiflux_client_id: number
    desk_ids: number[]
    technical_group_ids: number[]
  }) =>
    request<{
      success: boolean
      tiflux?: { success: boolean; data: Record<string, unknown> }
    }>('/consulta/tiflux/vinculos', { method: 'POST', body: JSON.stringify(body) }),
  dormantReport: (months = 24, limit = 0) =>
    request<Record<string, unknown>>(`/relatorio/empresas-inativas?months=${months}&limit=${limit}`),

  stats: () =>
    request<{
      success: boolean
      tiflux_total: number
      vhsys_total: number
      registered_30d: number
      inactivated_30d: number
      tiflux_dormant: number | null
      dormant_status: 'ready' | 'pending' | 'stale'
      computed_at: string
      stale_after_seconds: number
    }>('/stats'),

  dormantReportStream: (
    onProgress: (data: DormantProgress) => void,
    months = 24,
    limit = 0,
  ): { promise: Promise<Record<string, unknown>>; cancel: () => void } => {
    const url = `/relatorio/empresas-inativas/stream?months=${months}&limit=${limit}`
    const es = new EventSource(url, { withCredentials: true })
    let settled = false

    let rejectRef: (reason?: unknown) => void = () => {}

    const promise = new Promise<Record<string, unknown>>((resolve, reject) => {
      rejectRef = reject
      const finish = <T,>(fn: (value: T) => void, value: T) => {
        if (settled) return
        settled = true
        es.close()
        fn(value)
      }

      es.addEventListener('progress', (ev) => {
        try {
          onProgress(JSON.parse((ev as MessageEvent).data) as DormantProgress)
        } catch {
          /* ignore malformed */
        }
      })

      es.addEventListener('done', (ev) => {
        try {
          finish(resolve, JSON.parse((ev as MessageEvent).data) as Record<string, unknown>)
        } catch {
          finish(reject, new Error('Resposta inválida do servidor'))
        }
      })

      es.addEventListener('error', (ev) => {
        if ((ev as MessageEvent).data) {
          try {
            const data = JSON.parse((ev as MessageEvent).data) as { error?: string }
            finish(reject, new Error(data.error || 'Erro ao gerar relatório'))
          } catch {
            finish(reject, new Error('Erro ao gerar relatório'))
          }
        }
      })

      es.onerror = () => {
        if (settled || es.readyState === EventSource.CLOSED) return
        finish(reject, new Error('Conexão com o servidor interrompida'))
      }
    })

    return {
      promise,
      cancel: () => {
        if (!settled) {
          settled = true
          es.close()
          rejectRef(new Error('CANCELLED'))
        }
      },
    }
  },

  adminListUsers: () =>
    request<{ users: AdminUser[]; permission_labels: Partial<Record<PermissionKey, string>> }>(
      '/auth/admin/users',
    ),

  adminCreateUser: (body: { email: string; name: string; password?: string }) =>
    request<AdminUser>('/auth/admin/users', { method: 'POST', body: JSON.stringify(body) }),

  adminDeactivateUser: (userId: number) =>
    request<{ ok: boolean }>(`/auth/admin/users/${userId}`, { method: 'DELETE' }),

  adminUpdatePermissions: (userId: number, permissions: Partial<UserPermissions>) =>
    request<{ permissions: UserPermissions }>(`/auth/admin/users/${userId}/permissions`, {
      method: 'PATCH',
      body: JSON.stringify({ permissions }),
    }),

  adminSetPassword: (userId: number, password: string) =>
    request<{ ok: boolean; message: string }>(`/auth/admin/users/${userId}/password`, {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),

  adminSendResetEmail: (userId: number) =>
    request<{ ok: boolean; message: string }>(`/auth/admin/users/${userId}/reset-email`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  adminAuditLog: (params?: { limit?: number; offset?: number }) => {
    const qs = new URLSearchParams()
    if (params?.limit != null) qs.set('limit', String(params.limit))
    if (params?.offset != null) qs.set('offset', String(params.offset))
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<{ entries: AuditEntry[] }>(`/auth/admin/audit${suffix}`)
  },

  adminUserAuditLog: (userId: number, params?: { limit?: number; offset?: number }) => {
    const qs = new URLSearchParams()
    if (params?.limit != null) qs.set('limit', String(params.limit))
    if (params?.offset != null) qs.set('offset', String(params.offset))
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<{ entries: AuditEntry[] }>(`/auth/admin/audit/users/${userId}${suffix}`)
  },

  searchDocuments: (q: string, limit = 50) => {
    const qs = new URLSearchParams({ q, limit: String(limit) })
    return request<DocumentsSearchResponse>(`/documentos?${qs}`)
  },

  listRecentDocuments: (limit = 50) => {
    const qs = new URLSearchParams({ limit: String(limit) })
    return request<DocumentsSearchResponse>(`/documentos/recent?${qs}`)
  },

  listQuotes: (params?: QuotesListParams) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.lead_temperature) qs.set('lead_temperature', params.lead_temperature)
    if (params?.limit != null) qs.set('limit', String(params.limit))
    if (params?.offset != null) qs.set('offset', String(params.offset))
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<{ quotes: QuoteRead[] }>(`/orcamentos${suffix}`)
  },

  getQuote: (id: number) => request<QuoteRead>(`/orcamentos/${id}`),

  createQuote: (body: QuoteWrite) =>
    request<QuoteRead>('/orcamentos', { method: 'POST', body: JSON.stringify(body) }),

  updateQuote: (id: number, body: QuoteUpdate) =>
    request<QuoteRead>(`/orcamentos/${id}`, { method: 'PUT', body: JSON.stringify(body) }),

  deleteQuote: async (id: number): Promise<void> => {
    await request<Record<string, never>>(`/orcamentos/${id}`, { method: 'DELETE' })
  },

  listQuoteTemplates: () => request<{ templates: QuoteTemplateRead[] }>('/orcamentos/templates'),

  createQuoteTemplate: (body: QuoteTemplateWrite) =>
    request<QuoteTemplateRead>('/orcamentos/templates', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateQuoteTemplate: (id: number, body: QuoteTemplateUpdate) =>
    request<QuoteTemplateRead>(`/orcamentos/templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deleteQuoteTemplate: async (id: number): Promise<void> => {
    await request<Record<string, never>>(`/orcamentos/templates/${id}`, { method: 'DELETE' })
  },

  listQuoteModuleTemplates: () =>
    request<{ templates: QuoteModuleTemplateRead[] }>('/orcamentos/module-templates'),

  createQuoteModuleTemplate: (body: QuoteModuleTemplateWrite) =>
    request<QuoteModuleTemplateRead>('/orcamentos/module-templates', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateQuoteModuleTemplate: (id: number, body: QuoteModuleTemplateUpdate) =>
    request<QuoteModuleTemplateRead>(`/orcamentos/module-templates/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteQuoteModuleTemplate: async (id: number): Promise<void> => {
    await request<Record<string, never>>(`/orcamentos/module-templates/${id}`, {
      method: 'DELETE',
    })
  },

  /** `limit=0` (default) = catálogo VHSYS completo (paginação server-side). */
  searchVhsysCatalog: (q = '', limit = 0, categoryId?: number | null) => {
    const qs = new URLSearchParams()
    if (q.trim()) qs.set('q', q.trim())
    qs.set('limit', String(limit))
    if (categoryId != null && categoryId > 0) qs.set('category_id', String(categoryId))
    return request<{
      items: VhsysCatalogItem[]
      query: string
      count?: number
      category_id?: number | null
    }>(`/orcamentos/vhsys/catalog?${qs}`)
  },

  listVhsysCategories: () =>
    request<{ categories: VhsysCatalogCategory[]; count?: number }>(
      '/orcamentos/vhsys/categories',
    ),

  /** Via dupla: reutiliza se nome existir; senão POST /produtos no VHSYS. */
  createVhsysCatalogItem: (body: {
    name: string
    unit_value?: number
    tipo_produto?: 'Servico' | 'Produto'
    unidade_produto?: string
    id_categoria?: number | null
  }) =>
    request<{ item: VhsysCatalogItem; created: boolean }>('/orcamentos/vhsys/catalog', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  searchTifluxQuoteClients: (q: string, limit = 20) => {
    const qs = new URLSearchParams()
    qs.set('q', q.trim())
    qs.set('limit', String(limit))
    return request<{ clients: TifluxQuoteClient[]; query: string }>(
      `/orcamentos/tiflux/clients?${qs}`,
    )
  },

  getTifluxClientContact: (clientId: number) =>
    request<{ id: number; name: string | null; email: string | null }>(
      `/orcamentos/tiflux/clients/${clientId}`,
    ),

  getVhsysClientContact: (clientId: number) =>
    request<{ id: number; name: string | null; email: string | null }>(
      `/orcamentos/vhsys/clients/${clientId}`,
    ),

  searchVhsysParties: (q: string, limit = 20) => {
    const qs = new URLSearchParams()
    qs.set('q', q.trim())
    qs.set('limit', String(limit))
    return request<{ parties: VhsysParty[]; query: string }>(
      `/orcamentos/vhsys/parties?${qs}`,
    )
  },

  approveQuote: (id: number) =>
    request<QuoteRead>(`/orcamentos/${id}/approve`, { method: 'POST', body: JSON.stringify({}) }),

  /** draft→submitted + outbox `quote.submit` (202; dry-run sem HTTP externo). */
  submitQuote: (id: number) =>
    request<QuoteOutboxActionResult>(`/orcamentos/${id}/submit`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  /** submitted→sent + outbox `quote.sent` (202; opcional). */
  markSentQuote: (id: number) =>
    request<QuoteOutboxActionResult>(`/orcamentos/${id}/mark-sent`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  /** POST gera PDF e devolve blob para download. */
  generateQuotePdf: (id: number) =>
    requestBlob(`/orcamentos/${id}/pdf`, { method: 'POST', body: '{}' }, `orcamento-${id}.pdf`),

  /** GET baixa PDF já gerado. */
  downloadQuotePdf: (id: number) =>
    requestBlob(`/orcamentos/${id}/pdf`, { method: 'GET' }, `orcamento-${id}.pdf`),

  listBillingRuns: (params?: BillingRunsListParams) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.competence) qs.set('competence', params.competence)
    if (params?.limit != null) qs.set('limit', String(params.limit))
    if (params?.offset != null) qs.set('offset', String(params.offset))
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<{ runs: BillingRunRead[] }>(`/faturamento/runs${suffix}`)
  },

  searchTifluxBillingClients: (q: string, limit = 20) => {
    const qs = new URLSearchParams()
    qs.set('q', q.trim())
    qs.set('limit', String(limit))
    return request<{
      clients: Array<{ id: number; name: string; cnpj: string | null }>
      query: string
    }>(`/faturamento/tiflux/clients?${qs}`)
  },

  listTifluxBillingHistory: (params?: TifluxBillingHistoryParams) => {
    const qs = new URLSearchParams()
    if (params?.billing_day) qs.set('billing_day', params.billing_day)
    if (params?.competence) qs.set('competence', params.competence)
    if (params?.client_id != null) qs.set('client_id', String(params.client_id))
    if (params?.billing_type) qs.set('billing_type', params.billing_type)
    if (params?.due_start_date) qs.set('due_start_date', params.due_start_date)
    if (params?.due_end_date) qs.set('due_end_date', params.due_end_date)
    if (params?.limit != null) qs.set('limit', String(params.limit))
    if (params?.offset != null) qs.set('offset', String(params.offset))
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<{
      items: TifluxBillingHistoryItem[]
      count: number
      filters: Record<string, string | number | null>
      source: string
      note: string
    }>(`/faturamento/tiflux/history${suffix}`)
  },

  listTifluxContracts: (params?: {
    client_id?: number
    status?: string
    competence?: string
    limit?: number
    offset?: number
  }) => {
    const qs = new URLSearchParams()
    if (params?.client_id != null) qs.set('client_id', String(params.client_id))
    if (params?.status) qs.set('status', params.status)
    if (params?.competence) qs.set('competence', params.competence)
    if (params?.limit != null) qs.set('limit', String(params.limit))
    if (params?.offset != null) qs.set('offset', String(params.offset))
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<{
      contracts: TifluxBillingContractRow[]
      count: number
      client_id: number | null
      status: string
      competence: string | null
    }>(`/faturamento/tiflux/contracts${suffix}`)
  },

  listTifluxBillingContracts: (clientId: number) =>
    request<{
      contracts: Array<{
        id: number
        name: string
        amount: number
        status: string
        external_ref: string
        client_id?: number | null
        client_name?: string | null
      }>
      client_id: number
      count: number
    }>(`/faturamento/tiflux/clients/${clientId}/contracts`),

  getBillingRun: (id: number) => request<BillingRunRead>(`/faturamento/runs/${id}`),

  createBillingRun: (body: BillingRunWrite) =>
    request<BillingRunRead>('/faturamento/runs', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateBillingRun: (id: number, body: BillingRunUpdate) =>
    request<BillingRunRead>(`/faturamento/runs/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deleteBillingRun: async (id: number): Promise<void> => {
    await request<Record<string, never>>(`/faturamento/runs/${id}`, { method: 'DELETE' })
  },

  createBillingArtifact: (runId: number, body: BillingArtifactWrite) =>
    request<BillingArtifactRead>(`/faturamento/runs/${runId}/artifacts`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  deleteBillingArtifact: async (runId: number, artifactId: number): Promise<void> => {
    await request<Record<string, never>>(
      `/faturamento/runs/${runId}/artifacts/${artifactId}`,
      { method: 'DELETE' },
    )
  },

  /** draft→approved|awaiting_prefeitura + outbox (202; dry-run sem HTTP externo). */
  approveBillingRun: (id: number) =>
    request<BillingOutboxActionResult>(`/faturamento/runs/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  /** awaiting_prefeitura→approved + outbox billing.nf_prefeitura (202). */
  submitBillingPrefeitura: (id: number, body: BillingPrefeituraInput) =>
    request<BillingOutboxActionResult>(`/faturamento/runs/${id}/prefeitura`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

export type DormantProgress = {
  phase: 'start' | 'tickets' | 'billing' | 'scanning'
  scanned: number
  found: number
  limit: number
  scan_cap: number
  percent: number
  current_client?: string
}
