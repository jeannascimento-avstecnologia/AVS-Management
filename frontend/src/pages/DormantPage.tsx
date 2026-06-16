import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { api, type DormantProgress } from '@/api/client'
import { DormantReportView } from '@/components/dormant/DormantReportView'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const PHASE_LABELS: Record<DormantProgress['phase'], string> = {
  start: 'Iniciando varredura…',
  tickets: 'Consultando tickets',
  billing: 'Consultando cobranças',
  scanning: 'Analisando clientes',
}

export function DormantPage() {
  const [loading, setLoading] = useState(false)
  const [months, setMonths] = useState('24')
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [progress, setProgress] = useState<DormantProgress | null>(null)
  const cancelRef = useRef<(() => void) | null>(null)

  async function load() {
    setLoading(true)
    setProgress(null)
    setData(null)
    const m = Number(months)
    const stream = api.dormantReportStream((p) => setProgress(p), m, 100)
    cancelRef.current = stream.cancel
    try {
      const res = await stream.promise
      setProgress({
        phase: 'scanning',
        scanned: Number(res.scanned),
        found: Number(res.total),
        limit: 100,
        scan_cap: Number(res.scanned) || 100,
        percent: 100,
      })
      setData(res)
      toast.success(`Relatório gerado: ${res.total} empresa(s)`)
    } catch (err) {
      if (err instanceof Error && err.message !== 'CANCELLED') {
        toast.error(err.message)
      }
    } finally {
      setLoading(false)
      cancelRef.current = null
    }
  }

  function cancel() {
    cancelRef.current?.()
    cancelRef.current = null
    setLoading(false)
    setProgress(null)
    toast.info('Geração do relatório cancelada')
  }

  const progressLabel = progress
    ? `${PHASE_LABELS[progress.phase]} · ${progress.scanned}/${progress.scan_cap} · ${progress.found} inativa(s)`
    : 'Preparando…'

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Empresas sem atividade</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Sem ticket ou cobrança no TiFlux no período selecionado.
      </p>

      {!data && (
        <Card className="mb-6">
          <CardContent className="space-y-4 pt-6">
            <div className="flex flex-wrap items-end gap-4">
              <div className="space-y-2">
                <p className="text-sm font-medium">Período</p>
                <Select value={months} onValueChange={setMonths} disabled={loading}>
                  <SelectTrigger className="w-[140px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="12">12 meses</SelectItem>
                    <SelectItem value="24">24 meses</SelectItem>
                    <SelectItem value="36">36 meses</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={load} loading={loading}>Gerar relatório</Button>
              {loading && (
                <Button variant="outline" onClick={cancel}>Cancelar</Button>
              )}
            </div>
            {loading && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{progressLabel}</span>
                  <span className="font-mono text-xs">{progress?.percent ?? 0}%</span>
                </div>
                <Progress value={progress?.percent ?? 2} />
                {progress?.current_client && (
                  <Badge variant="secondary" className="font-normal">
                    {progress.current_client}
                  </Badge>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {data && (
        <DormantReportView raw={data} onNewReport={() => { setData(null); setProgress(null) }} />
      )}
    </div>
  )
}
