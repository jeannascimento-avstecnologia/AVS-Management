async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.error || data.detail || `Erro ${res.status}`)
  }
  return data as T
}

export const api = {
  me: () => request<{ authenticated: boolean; user: { email: string; name: string } }>('/auth/me'),
  login: (body: { email: string; password: string; remember_me?: boolean }) =>
    request<{ ok: boolean; redirect: string }>('/auth/login', {
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
  previewCnpj: (cnpj: string) => request<Record<string, unknown>>('/preview', { method: 'POST', body: JSON.stringify({ cnpj }) }),
  integrar: (body: Record<string, unknown>) => request<Record<string, unknown>>('/integrar', { method: 'POST', body: JSON.stringify(body) }),
  inativarPreview: (query: string) => request<Record<string, unknown>>('/inativar/preview', { method: 'POST', body: JSON.stringify({ query }) }),
  inativar: (query: string, tiflux_client_id: number) =>
    request<Record<string, unknown>>('/inativar', { method: 'POST', body: JSON.stringify({ query, tiflux_client_id }) }),
  consultaPreview: (query: string) => request<Record<string, unknown>>('/consulta/preview', { method: 'POST', body: JSON.stringify({ query }) }),
  consultaDetalhe: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/consulta/detalhe', { method: 'POST', body: JSON.stringify(body) }),
  dormantReport: (months = 24, limit = 100) =>
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
    limit = 100,
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
