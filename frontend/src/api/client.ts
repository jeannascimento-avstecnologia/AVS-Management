async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    // #region agent log
    if (url.includes('/relatorio/')) {
      fetch('http://127.0.0.1:7478/ingest/8cfaa81f-b56e-4ac1-8010-5fd779a0abab',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d84fb3'},body:JSON.stringify({sessionId:'d84fb3',location:'client.ts:request:error',message:'relatorio http error',data:{url,status:res.status,error:data.error||data.detail||null},timestamp:Date.now(),hypothesisId:'A'})}).catch(()=>{});
    }
    // #endregion
    throw new Error(data.error || data.detail || `Erro ${res.status}`)
  }
  return data as T
}

export const api = {
  me: () => request<{ authenticated: boolean; user: { email: string; name: string } }>('/auth/me'),
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
}
