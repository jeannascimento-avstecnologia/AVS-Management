import { useState } from 'react'
import { toast } from 'sonner'
import { api } from '../api/client'
import { DormantReportView } from '../components/dormant/DormantReportView'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Spinner } from '../components/ui/Spinner'

export function DormantPage() {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<Record<string, unknown> | null>(null)

  async function load() {
    setLoading(true)
    const startedAt = Date.now()
    // #region agent log
    fetch('http://127.0.0.1:7478/ingest/8cfaa81f-b56e-4ac1-8010-5fd779a0abab',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d84fb3'},body:JSON.stringify({sessionId:'d84fb3',location:'DormantPage.tsx:load:start',message:'dormant load clicked',data:{startedAt},timestamp:Date.now(),hypothesisId:'B',runId:'post-fix'})}).catch(()=>{});
    // #endregion
    try {
      const res = await api.dormantReport()
      // #region agent log
      fetch('http://127.0.0.1:7478/ingest/8cfaa81f-b56e-4ac1-8010-5fd779a0abab',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d84fb3'},body:JSON.stringify({sessionId:'d84fb3',location:'DormantPage.tsx:load:success',message:'dormant api success',data:{elapsedMs:Date.now()-startedAt,total:res.total,scanned:res.scanned,clientsLen:Array.isArray(res.clients)?res.clients.length:null,truncated:res.truncated},timestamp:Date.now(),hypothesisId:'C',runId:'post-fix'})}).catch(()=>{});
      // #endregion
      setData(res)
      toast.success(`Relatório gerado: ${res.total} empresa(s)`)
    } catch (err) {
      // #region agent log
      fetch('http://127.0.0.1:7478/ingest/8cfaa81f-b56e-4ac1-8010-5fd779a0abab',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d84fb3'},body:JSON.stringify({sessionId:'d84fb3',location:'DormantPage.tsx:load:error',message:'dormant api failed',data:{elapsedMs:Date.now()-startedAt,error:err instanceof Error?err.message:String(err)},timestamp:Date.now(),hypothesisId:'A',runId:'post-fix'})}).catch(()=>{});
      // #endregion
      toast.error(err instanceof Error ? err.message : 'Erro ao gerar relatório')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="font-display mb-2 text-2xl font-bold text-avs-navy">Empresas sem atividade (24 meses)</h1>
      <p className="mb-6 text-sm text-slate-600">
        Empresas sem ticket/chamado ou sem cobrança no TiFlux nos últimos 24 meses.
      </p>

      {!data && (
        <Card className="mb-6">
          <Button onClick={load} disabled={loading}>
            {loading ? <><Spinner /> Gerando relatório...</> : 'Gerar relatório'}
          </Button>
          {loading && (
            <p className="mt-3 text-sm text-slate-500">
              Consultando TiFlux… isso pode levar alguns minutos dependendo da quantidade de clientes.
            </p>
          )}
        </Card>
      )}

      {data && (
        <Card className="!border-0 !bg-transparent !p-0 !shadow-none">
          <DormantReportView raw={data} onNewReport={() => setData(null)} />
        </Card>
      )}
    </div>
  )
}
