import { useEffect, useState } from 'react'
import { useAutoAnimate } from '@formkit/auto-animate/react'
import { toast } from 'sonner'
import { AlertCircle } from 'lucide-react'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { CnpjInput } from '@/components/ui/CnpjInput'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { SpotlightSelectable } from '@/components/ui/SpotlightSelectable'
import { WizardStepper } from '@/components/ui/wizard-stepper'
import { ConsultReportView } from '@/components/consult/ConsultReportView'
import { btnAccentClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'
import { formatCnpj } from '@/lib/format'

const RECENT_KEY = 'avs-consult-recent'

function loadRecent(): string[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') as string[]
  } catch {
    return []
  }
}

function saveRecent(q: string) {
  const list = [q, ...loadRecent().filter((x) => x !== q)].slice(0, 5)
  localStorage.setItem(RECENT_KEY, JSON.stringify(list))
}

function notFoundMessage(system: 'TiFlux' | 'VHSYS', searchMode: string | undefined, displayQuery: string) {
  if (searchMode === 'cnpj') {
    const cnpj = formatCnpj(displayQuery.replace(/\D/g, ''))
    return `Este CNPJ (${cnpj}) não está cadastrado no ${system}.`
  }
  return `Nenhum cliente encontrado no ${system} para esta busca.`
}

export function ConsultPage() {
  const [step, setStep] = useState(1)
  const [query, setQuery] = useState('')
  const [recent, setRecent] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [tfId, setTfId] = useState<number | null>(null)
  const [vhId, setVhId] = useState<number | null>(null)
  const [skipTf, setSkipTf] = useState(false)
  const [skipVh, setSkipVh] = useState(false)
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [listRef] = useAutoAnimate<HTMLDivElement>()

  useEffect(() => setRecent(loadRecent()), [])

  const tf = preview?.tiflux as Record<string, unknown> | undefined
  const vh = preview?.vhsys as Record<string, unknown> | undefined
  const searchMode = preview?.search_mode as string | undefined
  const displayQuery = String(preview?.query ?? query)
  const tfMatches = (tf?.matches_active as Array<Record<string, unknown>>) || []
  const vhActive = (vh?.matches_active as Array<Record<string, unknown>>) || []
  const vhTrash = (vh?.matches_trash as Array<Record<string, unknown>>) || []
  const tfFound = Boolean(tf?.found)
  const vhFound = Boolean(vh?.found)
  const onlyInTiflux = tfFound && !vhFound
  const onlyInVhsys = !tfFound && vhFound
  const notFoundAnywhere = !tfFound && !vhFound

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const data = await api.consultaPreview(query)
      setPreview(data)
      saveRecent(query.trim())
      setRecent(loadRecent())
      setTfId(null)
      setVhId(null)
      setSkipTf(false)
      setSkipVh(false)
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

  const needsTf = tfFound && !skipTf
  const needsVh = vhFound && !skipVh
  const hasSelection = needsTf || needsVh
  const canSubmit = hasSelection && (!needsTf || !!tfId) && (!needsVh || !!vhId)

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Consultar status do cliente</h1>
      <p className="mb-6 text-sm text-muted-foreground">Relatório completo nos sistemas TiFlux e VHSYS.</p>
      <WizardStepper steps={['Busca', 'Seleção', 'Relatório']} current={step} accent="blue" />

      {step === 1 && (
        <Card>
          <CardContent className="space-y-4 pt-6">
            <form onSubmit={handleSearch} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="query">CNPJ ou nome</Label>
                <CnpjInput id="query" mode="query" value={query} onValueChange={setQuery} placeholder="CNPJ ou nome" required />
              </div>
              <Button type="submit" loading={loading} className={cn(btnAccentClass)}>
                Buscar
              </Button>
            </form>
            {recent.length > 0 && (
              <div className="border-t border-border pt-4">
                <p className="mb-2 text-xs font-medium uppercase text-muted-foreground">Buscas recentes</p>
                <div className="flex flex-wrap gap-2">
                  {recent.map((r) => (
                    <Button key={r} type="button" variant="outline" size="sm" onClick={() => setQuery(r)}>
                      {r}
                    </Button>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {step === 2 && preview && (
        <div className="space-y-4">
          {onlyInTiflux && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Este cliente está cadastrado apenas no <strong>TiFlux</strong>. Não consta no VHSYS.
              </AlertDescription>
            </Alert>
          )}
          {onlyInVhsys && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Este cliente está cadastrado apenas no <strong>VHSYS</strong>. Não consta no TiFlux.
              </AlertDescription>
            </Alert>
          )}
          {notFoundAnywhere && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {searchMode === 'cnpj'
                  ? `Este CNPJ (${formatCnpj(displayQuery.replace(/\D/g, ''))}) não está cadastrado no TiFlux nem no VHSYS.`
                  : 'Nenhum cliente encontrado no TiFlux nem no VHSYS para esta busca.'}
              </AlertDescription>
            </Alert>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardContent className="space-y-4 pt-6">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">TiFlux</h3>
                  {tfFound && (
                    <div className="flex items-center gap-2">
                      <Switch id="skip-tf" checked={skipTf} onCheckedChange={setSkipTf} />
                      <Label htmlFor="skip-tf" className="text-xs text-muted-foreground">Não consultar</Label>
                    </div>
                  )}
                </div>
                {!tfFound ? (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{notFoundMessage('TiFlux', searchMode, displayQuery)}</AlertDescription>
                  </Alert>
                ) : !skipTf ? (
                  <RadioGroup value={String(tfId ?? '')} onValueChange={(v) => setTfId(Number(v))}>
                    <div ref={listRef} className="space-y-2">
                      {tfMatches.map((m) => {
                        const id = Number(m.id)
                        return (
                          <SpotlightSelectable
                            key={String(m.id)}
                            as="label"
                            accent="accent"
                            selected={tfId === id}
                            className="cursor-pointer p-3 text-sm"
                            innerClassName="flex items-start gap-3"
                          >
                            <RadioGroupItem value={String(m.id)} className="mt-0.5" />
                            <span>{String(m.name)} — <span className="font-mono">{formatCnpj(String(m.social_revenue || ''))}</span></span>
                          </SpotlightSelectable>
                        )
                      })}
                    </div>
                  </RadioGroup>
                ) : (
                  <p className="text-sm text-muted-foreground">TiFlux será ignorado nesta consulta.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardContent className="space-y-4 pt-6">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">VHSYS</h3>
                  {vhFound && (
                    <div className="flex items-center gap-2">
                      <Switch id="skip-vh" checked={skipVh} onCheckedChange={setSkipVh} />
                      <Label htmlFor="skip-vh" className="text-xs text-muted-foreground">Não consultar</Label>
                    </div>
                  )}
                </div>
                {!vhFound ? (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{notFoundMessage('VHSYS', searchMode, displayQuery)}</AlertDescription>
                  </Alert>
                ) : !skipVh ? (
                  <RadioGroup value={String(vhId ?? '')} onValueChange={(v) => setVhId(Number(v))}>
                    <div className="space-y-2">
                      {[...vhActive, ...vhTrash].map((m) => {
                        const id = Number(m.id)
                        return (
                          <SpotlightSelectable
                            key={String(m.id)}
                            as="label"
                            accent="accent"
                            selected={vhId === id}
                            className="cursor-pointer p-3 text-sm"
                            innerClassName="flex items-start gap-3"
                          >
                            <RadioGroupItem value={String(m.id)} className="mt-0.5" />
                            <span>{String(m.fantasia_cliente || m.razao_cliente)} — <span className="font-mono">{formatCnpj(String(m.cnpj_cliente || ''))}</span></span>
                          </SpotlightSelectable>
                        )
                      })}
                    </div>
                  </RadioGroup>
                ) : (
                  <p className="text-sm text-muted-foreground">VHSYS será ignorado nesta consulta.</p>
                )}
              </CardContent>
            </Card>

            <div className="flex gap-2 lg:col-span-2">
              <Button variant="outline" onClick={() => setStep(1)}>Voltar</Button>
              <Button onClick={handleDetail} loading={loading} disabled={!canSubmit}>
                Gerar relatório
              </Button>
            </div>
          </div>
        </div>
      )}

      {step === 3 && detail && (
        <ConsultReportView
          raw={detail}
          tifluxClientId={skipTf ? null : tfId}
          onTifluxUpdated={setDetail}
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
      )}
    </div>
  )
}
