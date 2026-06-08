import { useState } from 'react'
import { toast } from 'sonner'
import { api } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Spinner } from '../components/ui/Spinner'
import { Stepper } from '../components/ui/Stepper'
import { formatCnpj } from '../lib/format'

export function RegisterPage() {
  const [step, setStep] = useState(1)
  const [cnpj, setCnpj] = useState('')
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [deskIds, setDeskIds] = useState<number[]>([])
  const [groupIds, setGroupIds] = useState<number[]>([])
  const [overrideInactive, setOverrideInactive] = useState(false)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)

  const company = preview?.company as Record<string, unknown> | undefined
  const opts = preview?.tiflux_options as Record<string, unknown> | undefined
  const desks = (opts?.desks as Array<Record<string, unknown>>) || []
  const groups = (opts?.technical_groups as Array<Record<string, unknown>>) || []

  async function handlePreview(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const data = await api.previewCnpj(cnpj)
      setPreview(data)
      const d = data.tiflux_options as Record<string, unknown>
      const def = d?.defaults as Record<string, number[]> | undefined
      setDeskIds(def?.desk_ids || [])
      setGroupIds(def?.technical_group_ids || [])
      setStep(2)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao consultar CNPJ')
    } finally {
      setLoading(false)
    }
  }

  async function handleIntegrate() {
    if (!company) return
    setLoading(true)
    try {
      const data = await api.integrar({
        company,
        desk_ids: deskIds,
        technical_group_ids: groupIds,
        override_inactive_registration: overrideInactive,
      })
      setResult(data)
      setStep(3)
      toast.success(data.success ? 'Cliente integrado!' : 'Integração parcial')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro na integração')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display mb-6 text-2xl font-bold">Cadastrar cliente</h1>
      <Stepper steps={['CNPJ', 'Revisão', 'Resultado']} current={step} />

      {step === 1 && (
        <Card>
          <form onSubmit={handlePreview} className="space-y-4">
            <label className="text-sm font-medium">CNPJ</label>
            <Input value={cnpj} onChange={(e) => setCnpj(e.target.value)} placeholder="00.000.000/0000-00" required />
            <Button type="submit" disabled={loading}>{loading ? <Spinner /> : 'Consultar CNPJ'}</Button>
          </form>
        </Card>
      )}

      {step === 2 && company && (
        <Card className="space-y-4">
          <div>
            <h2 className="font-semibold">{String(company.legal_name || company.trade_name)}</h2>
            <p className="text-sm text-slate-500">CNPJ: {formatCnpj(String(company.cnpj_digits || ''))}</p>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-semibold text-brand-700">Mesas de atendimento</h3>
            <div className="grid gap-2 sm:grid-cols-2">
              {desks.map((d) => (
                <label key={String(d.id)} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={deskIds.includes(Number(d.id))} onChange={(e) => {
                    const id = Number(d.id)
                    setDeskIds((prev) => e.target.checked ? [...prev, id] : prev.filter((x) => x !== id))
                  }} />
                  {String(d.display_name || d.name)}
                </label>
              ))}
            </div>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-semibold text-brand-700">Grupos de atendentes</h3>
            <div className="grid gap-2 sm:grid-cols-2 max-h-48 overflow-y-auto">
              {groups.map((g) => (
                <label key={String(g.id)} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={groupIds.includes(Number(g.id))} onChange={(e) => {
                    const id = Number(g.id)
                    setGroupIds((prev) => e.target.checked ? [...prev, id] : prev.filter((x) => x !== id))
                  }} />
                  {String(g.name)}
                </label>
              ))}
            </div>
          </div>
          {Boolean(preview?.requires_inactive_override) && (
            <label className="flex items-center gap-2 text-sm text-amber-700">
              <input type="checkbox" checked={overrideInactive} onChange={(e) => setOverrideInactive(e.target.checked)} />
              Autorizo cadastro com situação cadastral inativa na Receita
            </label>
          )}
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStep(1)}>Voltar</Button>
            <Button onClick={handleIntegrate} disabled={loading || !deskIds.length || !groupIds.length}>
              {loading ? <Spinner /> : 'Confirmar cadastro'}
            </Button>
          </div>
        </Card>
      )}

      {step === 3 && result && (
        <Card>
          <p className={result.success ? 'text-green-700' : 'text-amber-700'}>
            {result.success ? 'Cadastro concluído com sucesso.' : 'Cadastro concluído com ressalvas.'}
          </p>
          <pre className="mt-4 overflow-auto rounded-xl bg-slate-50 p-4 text-xs">{JSON.stringify(result, null, 2)}</pre>
          <Button className="mt-4" variant="secondary" onClick={() => { setStep(1); setPreview(null); setResult(null) }}>Nova consulta</Button>
        </Card>
      )}
    </div>
  )
}
