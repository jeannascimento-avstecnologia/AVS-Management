import { getCsrfToken, isCsrfExempt, refreshCsrfToken, setCsrfToken } from './csrf'

export { refreshCsrfToken, setCsrfToken }

export type PermissionKey =
  | 'cadastrar'
  | 'inativar'
  | 'consultar'
  | 'empresas_inativas'
  | 'manage_users'

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

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || 'GET').toUpperCase()
  const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && !isCsrfExempt(url)
  if (needsCsrf && !getCsrfToken()) {
    await refreshCsrfToken()
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
  }
  const csrf = getCsrfToken()
  if (needsCsrf && csrf) {
    headers['X-CSRF-Token'] = csrf
  }

  const res = await fetch(url, {
    credentials: 'include',
    ...init,
    headers,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.error || data.detail || `Erro ${res.status}`)
  }
  return data as T
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
    request<{ users: AdminUser[]; permission_labels: Record<string, string> }>('/auth/admin/users'),

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
