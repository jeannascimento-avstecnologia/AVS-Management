import { Download, FileText, Printer } from 'lucide-react'
import { Button } from '../ui/Button'
import {
  buildDormantReportHtml,
  downloadBlob,
  parseDormantReport,
} from '../../lib/dormantReport'
import { formatCnpj, formatDate } from '../../lib/format'

type Props = {
  raw: Record<string, unknown>
  onNewReport?: () => void
}

export function DormantReportView({ raw, onNewReport }: Props) {
  const parsed = parseDormantReport(raw)
  const stamp = new Date().toISOString().slice(0, 10)

  function handlePrint() {
    window.print()
  }

  function handleSaveHtml() {
    downloadBlob(buildDormantReportHtml(parsed, raw), `empresas-sem-atividade-${stamp}.html`, 'text/html;charset=utf-8')
  }

  function handleSaveJson() {
    downloadBlob(JSON.stringify(raw, null, 2), `empresas-sem-atividade-${stamp}.json`, 'application/json')
  }

  return (
    <div className="dormant-report">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-bold text-avs-navy">Relatório — empresas sem atividade</h2>
          <p className="text-sm text-slate-600">
            Últimos <strong>{parsed.months}</strong> meses · Analisados: <strong>{parsed.scanned}</strong> · Encontrados:{' '}
            <strong>{parsed.total}</strong>
            {parsed.truncated ? ' (lista truncada)' : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={handlePrint}>
            <Printer className="h-4 w-4" /> Imprimir
          </Button>
          <Button variant="secondary" onClick={handleSaveHtml}>
            <FileText className="h-4 w-4" /> Salvar HTML
          </Button>
          <Button variant="secondary" onClick={handleSaveJson}>
            <Download className="h-4 w-4" /> Baixar JSON
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white/90">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="border-b bg-avs-navy text-white">
              <th className="p-3">Razão social</th>
              <th className="p-3">CNPJ</th>
              <th className="p-3">Último ticket</th>
              <th className="p-3">Última cobrança</th>
              <th className="p-3">Motivo</th>
            </tr>
          </thead>
          <tbody>
            {parsed.clients.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-6 text-center text-slate-500">
                  Nenhuma empresa inativa encontrada no período.
                </td>
              </tr>
            ) : (
              parsed.clients.map((c) => (
                <tr key={c.id} className="border-b border-slate-100 hover:bg-slate-50/80">
                  <td className="p-3 font-medium">{c.social || c.name}</td>
                  <td className="p-3">{formatCnpj(c.social_revenue)}</td>
                  <td className="p-3">{formatDate(c.last_ticket_at)}</td>
                  <td className="p-3">{formatDate(c.last_billing_at)}</td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-1">
                      {c.reasons.map((r) => (
                        <span key={r} className="rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-700">
                          {r}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {onNewReport && (
        <div className="no-print mt-6">
          <Button variant="secondary" onClick={onNewReport}>Gerar novo relatório</Button>
        </div>
      )}
    </div>
  )
}
