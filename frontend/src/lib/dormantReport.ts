import { formatCnpj, formatDate } from './format'
import { downloadBlob } from './consultReport'

export const REASON_LABELS: Record<string, string> = {
  sem_ticket_24m: 'Sem ticket em 24 meses',
  sem_cobranca_24m: 'Sem cobrança em 24 meses',
}

export type DormantClientRow = {
  id: number
  name: string
  social: string
  social_revenue: string
  last_ticket_at: string | null
  last_billing_at: string | null
  reasonCodes: string[]
  reasonLabels: string[]
  /** @deprecated use reasonLabels */
  reasons: string[]
}

export type ParsedDormantReport = {
  months: number
  scanned: number
  total: number
  truncated: boolean
  clients: DormantClientRow[]
}

export function parseDormantReport(data: Record<string, unknown>): ParsedDormantReport {
  const clients = ((data.clients as Array<Record<string, unknown>>) || []).map((c) => {
    const reasonCodes = ((c.reasons as string[]) || [])
    const reasonLabels = reasonCodes.map((r) => REASON_LABELS[r] || r.replace(/_/g, ' '))
    return {
      id: Number(c.id),
      name: String(c.name || ''),
      social: String(c.social || ''),
      social_revenue: String(c.social_revenue || ''),
      last_ticket_at: c.last_ticket_at ? String(c.last_ticket_at) : null,
      last_billing_at: c.last_billing_at ? String(c.last_billing_at) : null,
      reasonCodes,
      reasonLabels,
      reasons: reasonLabels,
    }
  })
  return {
    months: Number(data.months) || 24,
    scanned: Number(data.scanned) || 0,
    total: Number(data.total) || clients.length,
    truncated: Boolean(data.truncated),
    clients,
  }
}

export function buildDormantReportHtml(parsed: ParsedDormantReport, raw: Record<string, unknown>): string {
  const rows = parsed.clients.map((c) => `
    <tr>
      <td>${c.social || c.name}</td>
      <td>${formatCnpj(c.social_revenue)}</td>
      <td>${formatDate(c.last_ticket_at)}</td>
      <td>${formatDate(c.last_billing_at)}</td>
      <td>${c.reasonLabels.join(', ')}</td>
    </tr>`).join('')

  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Empresas sem atividade — AVS Management</title>
<style>
body{font-family:Inter,system-ui,sans-serif;color:#0c1e3a;padding:2rem;background:#eef2f7}
h1{font-size:1.5rem;color:#1a4f8c}
.meta{margin-bottom:1rem;font-size:.9rem}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden}
th,td{border:1px solid #d8e0ea;padding:.5rem .65rem;font-size:.85rem;text-align:left}
th{background:#1a4f8c;color:#fff}
.actions{margin-bottom:1rem}
@media print{.actions{display:none}}
</style></head><body>
<h1>AVS Management — Empresas sem atividade</h1>
<p class="meta">Período: últimos <strong>${parsed.months}</strong> meses · Analisados: <strong>${parsed.scanned}</strong> · Encontrados: <strong>${parsed.total}</strong>${parsed.truncated ? ' (lista truncada)' : ''}</p>
<div class="actions"><button onclick="window.print()">Imprimir</button></div>
<table>
<thead><tr><th>Razão social</th><th>CNPJ</th><th>Último ticket</th><th>Última cobrança</th><th>Motivo</th></tr></thead>
<tbody>${rows || '<tr><td colspan="5">Nenhuma empresa encontrada.</td></tr>'}</tbody>
</table>
<script>console.log(${JSON.stringify(raw)});</script>
</body></html>`
}

export { downloadBlob }
