import { useState } from 'react'
import { toast } from 'sonner'
import { api } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Spinner } from '../components/ui/Spinner'
import { Stepper } from '../components/ui/Stepper'
import { ConsultReportView } from '../components/consult/ConsultReportView'
import { formatCnpj } from '../lib/format'

export function ConsultPage() {
  const [step, setStep] = useState(1)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [tfId, setTfId] = useState<number | null>(null)
  const [vhId, setVhId] = useState<number | null>(null)
  const [skipTf, setSkipTf] = useState(false)
  const [skipVh, setSkipVh] = useState(false)
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)

  const tf = preview?.tiflux as Record<string, unknown> | undefined
  const vh = preview?.vhsys as Record<string, unknown> | undefined
  const tfMatches = (tf?.matches_active as Array<Record<string, unknown>>) || []
  const vhActive = (vh?.matches_active as Array<Record<string, unknown>>) || []
  const vhTrash = (vh?.matches_trash as Array<Record<string, unknown>>) || []

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const data = await api.consultaPreview(query)
      setPreview(data)
      setStep(2)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro na busca')
    } finally {
      setLoading(false)
    }
  }

  async function handleDetail() {
    setLoading(true)
    try {
      const data = await api.consultaDetalhe({
        query,
        tiflux_client_id: skipTf ? null : tfId,
        vhsys_client_id: skipVh ? null : vhId,
      })
      setDetail(data)
      setStep(3)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao carregar detalhe')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="font-display mb-6 text-2xl font-bold">Consultar status do cliente</h1>
      <Stepper steps={['Busca', 'Seleção', 'Relatório']} current={step} />

      {step === 1 && (
        <Card>
          <form onSubmit={handleSearch} className="space-y-4">
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="CNPJ ou nome" required />
            <Button type="submit" disabled={loading}>{loading ? <Spinner /> : 'Buscar'}</Button>
          </form>
        </Card>
      )}

      {step === 2 && preview && (
        <Card className="space-y-6">
          {Boolean(tf?.found) && (
            <div>
              <h3 className="mb-2 font-semibold">TiFlux</h3>
              <label className="mb-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={skipTf} onChange={(e) => setSkipTf(e.target.checked)} /> Não consultar TiFlux</label>
              {!skipTf && tfMatches.map((m) => (
                <label key={String(m.id)} className="mb-2 flex gap-2 rounded-xl border p-3 text-sm">
                  <input type="radio" name="tf" checked={tfId === Number(m.id)} onChange={() => setTfId(Number(m.id))} />
                  <span>{String(m.name)} — {formatCnpj(String(m.social_revenue || ''))}</span>
                </label>
              ))}
            </div>
          )}
          {Boolean(vh?.found) && (
            <div>
              <h3 className="mb-2 font-semibold">VHSYS (ativos)</h3>
              <label className="mb-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={skipVh} onChange={(e) => setSkipVh(e.target.checked)} /> Não consultar VHSYS</label>
              {!skipVh && [...vhActive, ...vhTrash].map((m) => (
                <label key={String(m.id)} className="mb-2 flex gap-2 rounded-xl border p-3 text-sm">
                  <input type="radio" name="vh" checked={vhId === Number(m.id)} onChange={() => setVhId(Number(m.id))} />
                  <span>{String(m.fantasia_cliente || m.razao_cliente)} — {formatCnpj(String(m.cnpj_cliente || ''))}</span>
                </label>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStep(1)}>Voltar</Button>
            <Button
              onClick={handleDetail}
              disabled={
                loading
                || (Boolean(tf?.found) && !skipTf && !tfId)
                || (Boolean(vh?.found) && !skipVh && !vhId)
                || (!((Boolean(tf?.found) && !skipTf) || (Boolean(vh?.found) && !skipVh)))
              }
            >
              {loading ? <Spinner /> : 'Gerar relatório'}
            </Button>
          </div>
        </Card>
      )}

      {step === 3 && detail && (
        <Card className="!p-0 overflow-hidden border-0 bg-transparent shadow-none">
          <ConsultReportView
            raw={detail}
            onNewSearch={() => {
              setStep(1)
              setPreview(null)
              setDetail(null)
              setTfId(null)
              setVhId(null)
              setSkipTf(false)
              setSkipVh(false)
            }}
          />
        </Card>
      )}
    </div>
  )
}
