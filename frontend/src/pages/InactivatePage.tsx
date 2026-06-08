import { useState } from 'react'
import { toast } from 'sonner'
import { api } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Modal } from '../components/ui/Modal'
import { Spinner } from '../components/ui/Spinner'
import { Stepper } from '../components/ui/Stepper'
import { formatCnpj } from '../lib/format'

export function InactivatePage() {
  const [step, setStep] = useState(1)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)

  const matches = ((preview?.tiflux as Record<string, unknown>)?.matches as Array<Record<string, unknown>>) || []

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const data = await api.inativarPreview(query)
      setPreview(data)
      const m = ((data.tiflux as Record<string, unknown>)?.matches as Array<Record<string, unknown>>) || []
      if (m.length === 1) setSelectedId(Number(m[0].id))
      setStep(2)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro na busca')
    } finally {
      setLoading(false)
    }
  }

  async function handleInactivate() {
    if (!selectedId) return
    setLoading(true)
    try {
      const data = await api.inativar(query, selectedId)
      setResult(data)
      setStep(3)
      setConfirmOpen(false)
      toast.success('Cliente inativado no TiFlux')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao inativar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display mb-6 text-2xl font-bold">Inativar cliente</h1>
      <Stepper steps={['Busca', 'Conferência', 'Resultado']} current={step} />

      {step === 1 && (
        <Card>
          <form onSubmit={handleSearch} className="space-y-4">
            <label className="text-sm font-medium">CNPJ ou nome</label>
            <Input value={query} onChange={(e) => setQuery(e.target.value)} required />
            <Button type="submit" disabled={loading}>{loading ? <Spinner /> : 'Buscar'}</Button>
          </form>
        </Card>
      )}

      {step === 2 && (
        <Card className="space-y-4">
          {!matches.length ? <p className="text-slate-500">Nenhum cliente ativo encontrado no TiFlux.</p> : (
            <div className="space-y-2">
              {matches.map((m) => (
                <label key={String(m.id)} className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3 hover:bg-slate-50">
                  <input type="radio" name="pick" checked={selectedId === Number(m.id)} onChange={() => setSelectedId(Number(m.id))} />
                  <div>
                    <p className="font-medium">{String(m.name || m.social)}</p>
                    <p className="text-xs text-slate-500">CNPJ: {formatCnpj(String(m.social_revenue || ''))}</p>
                  </div>
                </label>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStep(1)}>Voltar</Button>
            <Button disabled={!selectedId} onClick={() => setConfirmOpen(true)}>Inativar no TiFlux</Button>
          </div>
        </Card>
      )}

      {step === 3 && result && (
        <Card>
          <p className="text-green-700">{(result.tiflux as Record<string, unknown>)?.message as string || 'Operação concluída.'}</p>
          <Button className="mt-4" variant="secondary" onClick={() => { setStep(1); setPreview(null); setResult(null) }}>Nova inativação</Button>
        </Card>
      )}

      <Modal open={confirmOpen} title="Confirmar inativação" onClose={() => setConfirmOpen(false)} onConfirm={handleInactivate} confirmLabel={loading ? 'Processando...' : 'Confirmar'}>
        O cliente será inativado no TiFlux (status inativo). Esta ação não remove dados do VHSYS.
      </Modal>
    </div>
  )
}
