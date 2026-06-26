import { useState } from 'react'
import { useAutoAnimate } from '@formkit/auto-animate/react'
import { toast } from 'sonner'
import { CheckCircle2 } from 'lucide-react'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { CnpjInput } from '@/components/ui/CnpjInput'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { WizardStepper } from '@/components/ui/wizard-stepper'
import { SpotlightSelectable } from '@/components/ui/SpotlightSelectable'
import { EmptyState } from '@/components/feedback/EmptyState'
import { formatCnpj } from '@/lib/format'
import { Search } from 'lucide-react'

export function InactivatePage() {
  const [step, setStep] = useState(1)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [listRef] = useAutoAnimate<HTMLDivElement>()

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
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Inativar cliente</h1>
      <p className="mb-6 text-sm text-muted-foreground">Busque por CNPJ ou nome e inative no TiFlux.</p>
      <WizardStepper steps={['Busca', 'Conferência', 'Resultado']} current={step} />

      {step === 1 && (
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleSearch} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="query">CNPJ ou nome</Label>
                <CnpjInput id="query" mode="query" value={query} onValueChange={setQuery} placeholder="CNPJ ou nome" required />
              </div>
              <Button type="submit" loading={loading}>Buscar</Button>
            </form>
          </CardContent>
        </Card>
      )}

      {step === 2 && (
        <Card>
          <CardContent className="space-y-4 pt-6">
            {!matches.length ? (
              <EmptyState icon={Search} title="Nenhum cliente ativo" description="Nenhum cliente ativo encontrado no TiFlux." />
            ) : (
              <RadioGroup value={String(selectedId ?? '')} onValueChange={(v) => setSelectedId(Number(v))}>
                <div ref={listRef} className="space-y-2">
                  {matches.map((m) => {
                    const id = Number(m.id)
                    return (
                      <SpotlightSelectable
                        key={String(m.id)}
                        as="label"
                        accent="red"
                        selected={selectedId === id}
                        className="cursor-pointer p-4"
                        innerClassName="flex items-start gap-3"
                      >
                        <RadioGroupItem value={String(m.id)} className="mt-0.5" />
                        <div>
                          <p className="font-medium">{String(m.name || m.social)}</p>
                          <p className="font-mono text-xs text-muted-foreground">
                            CNPJ: {formatCnpj(String(m.social_revenue || ''))}
                          </p>
                        </div>
                      </SpotlightSelectable>
                    )
                  })}
                </div>
              </RadioGroup>
            )}
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(1)}>Voltar</Button>
              <Button variant="destructive" disabled={!selectedId} onClick={() => setConfirmOpen(true)}>
                Inativar no TiFlux
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {step === 3 && result && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
            <CheckCircle2 className="h-12 w-12 text-emerald-600" />
            <p className="font-medium">
              {(result.tiflux as Record<string, unknown>)?.message as string || 'Operação concluída.'}
            </p>
            <Button variant="outline" onClick={() => { setStep(1); setPreview(null); setResult(null); setQuery('') }}>
              Nova inativação
            </Button>
          </CardContent>
        </Card>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar inativação</AlertDialogTitle>
            <AlertDialogDescription>
              O cliente será inativado no TiFlux (status inativo). Esta ação não remove dados do VHSYS.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleInactivate} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {loading ? 'Processando…' : 'Confirmar'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
