import { Download, FileText, Printer } from 'lucide-react'
import { Button } from '../ui/Button'
import {
  buildReportHtml,
  downloadBlob,
  parseConsultReport,
  type ParsedConsultReport,
  type ReportSection,
} from '../../lib/consultReport'

function SectionBlock({ sections }: { sections: ReportSection[] }) {
  if (!sections.length) return null
  return (
    <>
      {sections.map((sec) => (
        <section key={sec.title} className="report-section mb-4">
          <h4 className="mb-2 text-sm font-semibold text-avs-blue">{sec.title}</h4>
          <dl className="grid gap-1 text-sm sm:grid-cols-[minmax(140px,38%)_1fr]">
            {sec.rows.map((row) => (
              <div key={row.label} className="contents">
                <dt className="font-medium text-slate-500">{row.label}</dt>
                <dd className="text-slate-800">{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </>
  )
}

function ReportColumn({
  title,
  parsed,
  side,
}: {
  title: string
  parsed: ParsedConsultReport['tiflux'] | ParsedConsultReport['vhsys']
  side: 'tiflux' | 'vhsys'
}) {
  const lists = 'lists' in parsed ? parsed.lists : []
  const entities = side === 'tiflux' && 'entities' in parsed ? parsed.entities : []

  return (
    <div className="rounded-2xl border border-slate-200 bg-white/90 p-5">
      <h3 className="font-display mb-4 text-lg font-bold text-avs-navy">{title}</h3>

      {parsed.status === 'skipped' && <p className="text-sm text-slate-500">{parsed.message}</p>}
      {parsed.status === 'error' && <p className="text-sm text-red-600">{parsed.message}</p>}

      {parsed.status === 'ok' && (
        <>
          {side === 'vhsys' && 'category' in parsed && parsed.category && (
            <p className="mb-4 text-sm">
              <span className="font-semibold text-slate-600">Categoria:</span> {parsed.category}
            </p>
          )}

          {lists.map((list) => (
            <section key={list.title} className="mb-4">
              <h4 className="mb-2 text-sm font-semibold text-avs-blue">{list.title}</h4>
              <ul className="list-inside list-disc text-sm text-slate-700">
                {list.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          ))}

          <SectionBlock sections={parsed.sections} />

          {entities.map((ent) => (
            <section key={ent.name} className="mb-4">
              <h4 className="mb-1 text-sm font-semibold text-avs-blue">{ent.name}</h4>
              {ent.description && <p className="mb-2 text-xs text-slate-500">{ent.description}</p>}
              <dl className="grid gap-1 text-sm sm:grid-cols-[minmax(120px,38%)_1fr]">
                {ent.fields.map((f) => (
                  <div key={f.label} className="contents">
                    <dt className="font-medium text-slate-500">{f.label}</dt>
                    <dd className="text-slate-800">{f.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </>
      )}
    </div>
  )
}

type Props = {
  raw: Record<string, unknown>
  onNewSearch?: () => void
}

export function ConsultReportView({ raw, onNewSearch }: Props) {
  const parsed = parseConsultReport(raw)
  const safeName = parsed.query.replace(/[^\w.-]+/g, '_') || 'consulta'

  function handlePrint() {
    window.print()
  }

  function handleSaveHtml() {
    const html = buildReportHtml(parsed, raw)
    downloadBlob(html, `relatorio-avs-${safeName}.html`, 'text/html;charset=utf-8')
  }

  function handleSaveJson() {
    downloadBlob(JSON.stringify(raw, null, 2), `relatorio-avs-${safeName}.json`, 'application/json')
  }

  return (
    <div className="consult-report">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-bold text-avs-navy">Relatório de consulta</h2>
          <p className="text-sm text-slate-600">
            Consulta: <strong>{parsed.query}</strong>
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

      <div className="grid gap-6 lg:grid-cols-2">
        <ReportColumn title="TiFlux" parsed={parsed.tiflux} side="tiflux" />
        <ReportColumn title="VHSYS" parsed={parsed.vhsys} side="vhsys" />
      </div>

      {onNewSearch && (
        <div className="no-print mt-6">
          <Button variant="secondary" onClick={onNewSearch}>Nova consulta</Button>
        </div>
      )}
    </div>
  )
}
