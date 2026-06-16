import { Download, FileText, MoreHorizontal, Printer } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  buildReportHtml,
  downloadBlob,
  parseConsultReport,
  type ParsedConsultReport,
  type ReportSection,
} from '@/lib/consultReport'

function SectionBlock({ sections }: { sections: ReportSection[] }) {
  if (!sections.length) return null
  return (
    <>
      {sections.map((sec) => (
        <section key={sec.title} className="report-section mb-4">
          <h4 className="mb-2 text-sm font-semibold text-primary">{sec.title}</h4>
          <dl className="grid gap-1 text-sm sm:grid-cols-[minmax(140px,38%)_1fr]">
            {sec.rows.map((row) => (
              <div key={row.label} className="contents">
                <dt className="font-medium text-muted-foreground">{row.label}</dt>
                <dd>{row.value}</dd>
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
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {parsed.status === 'skipped' && <p className="text-sm text-muted-foreground">{parsed.message}</p>}
        {parsed.status === 'error' && <p className="text-sm text-destructive">{parsed.message}</p>}

        {parsed.status === 'ok' && (
          <>
            {side === 'vhsys' && 'category' in parsed && parsed.category && (
              <p className="mb-4 text-sm">
                <span className="font-semibold text-muted-foreground">Categoria:</span> {parsed.category}
              </p>
            )}
            {lists.map((list) => (
              <section key={list.title} className="mb-4">
                <h4 className="mb-2 text-sm font-semibold text-primary">{list.title}</h4>
                <ul className="list-inside list-disc text-sm">
                  {list.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
            ))}
            <SectionBlock sections={parsed.sections} />
            {entities.map((ent) => (
              <section key={ent.name} className="mb-4">
                <h4 className="mb-1 text-sm font-semibold text-primary">{ent.name}</h4>
                {ent.description && <p className="mb-2 text-xs text-muted-foreground">{ent.description}</p>}
                <dl className="grid gap-1 text-sm sm:grid-cols-[minmax(120px,38%)_1fr]">
                  {ent.fields.map((f) => (
                    <div key={f.label} className="contents">
                      <dt className="font-medium text-muted-foreground">{f.label}</dt>
                      <dd>{f.value}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </>
        )}
      </CardContent>
    </Card>
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
    downloadBlob(buildReportHtml(parsed, raw), `relatorio-avs-${safeName}.html`, 'text/html;charset=utf-8')
  }

  function handleSaveJson() {
    downloadBlob(JSON.stringify(raw, null, 2), `relatorio-avs-${safeName}.json`, 'application/json')
  }

  return (
    <div className="consult-report">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Relatório de consulta</h2>
          <p className="text-sm text-muted-foreground">
            Consulta: <strong className="text-foreground">{parsed.query}</strong>
          </p>
        </div>
        <div className="flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <MoreHorizontal className="h-4 w-4" /> Exportar
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handlePrint}>
                <Printer className="mr-2 h-4 w-4" /> Imprimir
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleSaveHtml}>
                <FileText className="mr-2 h-4 w-4" /> Salvar HTML
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleSaveJson}>
                <Download className="mr-2 h-4 w-4" /> Baixar JSON
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <Tabs defaultValue="compare">
        <TabsList className="no-print mb-4">
          <TabsTrigger value="tiflux">TiFlux</TabsTrigger>
          <TabsTrigger value="vhsys">VHSYS</TabsTrigger>
          <TabsTrigger value="compare">Comparar</TabsTrigger>
        </TabsList>
        <TabsContent value="tiflux">
          <ReportColumn title="TiFlux" parsed={parsed.tiflux} side="tiflux" />
        </TabsContent>
        <TabsContent value="vhsys">
          <ReportColumn title="VHSYS" parsed={parsed.vhsys} side="vhsys" />
        </TabsContent>
        <TabsContent value="compare">
          <div className="grid gap-6 lg:grid-cols-2">
            <ReportColumn title="TiFlux" parsed={parsed.tiflux} side="tiflux" />
            <ReportColumn title="VHSYS" parsed={parsed.vhsys} side="vhsys" />
          </div>
        </TabsContent>
      </Tabs>

      {onNewSearch && (
        <div className="no-print mt-6">
          <Button variant="outline" onClick={onNewSearch}>Nova consulta</Button>
        </div>
      )}
    </div>
  )
}
