import { useState } from 'react'
import { useAutoAnimate } from '@formkit/auto-animate/react'
import { toast } from 'sonner'
import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CnpjInput } from '@/components/ui/CnpjInput'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { WizardStepper } from '@/components/ui/wizard-stepper'
import { SpotlightSelectable } from '@/components/ui/SpotlightSelectable'
import { btnAccentClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'
import { formatCnpj } from '@/lib/format'

type IntegrationTarget = 'tiflux' | 'vhsys'

function readDuplicates(preview: Record<string, unknown> | null) {
  const d = (preview?.duplicates as Record<string, unknown> | undefined) || {}
  const dupTf = Boolean(d.tiflux)
  const dupVh = Boolean(d.vhsys)
  return { dupTf, dupVh, bothDup: dupTf && dupVh, onlyTf: dupTf && !dupVh, onlyVh: dupVh && !dupTf }
}

export function RegisterPage() {
  const [step, setStep] = useState(1)
  const [cnpj, setCnpj] = useState('')
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [deskIds, setDeskIds] = useState<number[]>([])
  const [groupIds, setGroupIds] = useState<number[]>([])
  const [overrideInactive, setOverrideInactive] = useState(false)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [listRef] = useAutoAnimate<HTMLDivElement>()

  const company = preview?.company as Record<string, unknown> | undefined
  const opts = preview?.tiflux_options as Record<string, unknown> | undefined
  const desks = (opts?.desks as Array<Record<string, unknown>>) || []
  const groups = (opts?.technical_groups as Array<Record<string, unknown>>) || []
  const { dupTf, dupVh, bothDup, onlyTf, onlyVh } = readDuplicates(preview)
  const needsTifluxConfig = !onlyVh

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

  async function handleIntegrate(targets?: IntegrationTarget[]) {
    if (!company) return
    setLoading(true)
    try {
      const resolvedTargets = targets ?? (bothDup ? undefined : onlyTf ? ['vhsys'] : onlyVh ? ['tiflux'] : undefined)
      const data = await api.integrar({
        company,
        desk_ids: deskIds,
        technical_group_ids: groupIds,
        override_inactive_registration: overrideInactive,
        ...(resolvedTargets ? { targets: resolvedTargets } : {}),
      })

      if (data.all_duplicates) {
        toast.error(String(data.error || 'Cliente já cadastrado nos sistemas selecionados.'))
        return
      }

      setResult(data)
      setStep(3)
      if (data.success && data.partial) {
        toast.success('Cliente cadastrado no sistema pendente.')
      } else if (data.success) {
        toast.success('Cliente integrado!')
      } else {
        toast.error('Não foi possível concluir o cadastro.')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro na integração')
    } finally {
      setLoading(false)
    }
  }

  function resetFlow() {
    setStep(1)
    setPreview(null)
    setResult(null)
    setCnpj('')
  }

  const tfResult = result?.tiflux as Record<string, unknown> | undefined
  const vhResult = result?.vhsys as Record<string, unknown> | undefined

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Cadastrar cliente</h1>
      <p className="mb-6 text-sm text-muted-foreground">Consulte o CNPJ e integre em TiFlux + VHSYS.</p>
      <WizardStepper steps={['CNPJ', 'Revisão', 'Resultado']} current={step} accent="blue" />

      {step === 1 && (
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handlePreview} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="cnpj">CNPJ</Label>
                <CnpjInput
                  id="cnpj"
                  value={cnpj}
                  onValueChange={setCnpj}
                  placeholder="00.000.000/0000-00"
                  required
                />
              </div>
              <Button type="submit" loading={loading} className={cn(btnAccentClass)}>
                Consultar CNPJ
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {step === 2 && company && (
        <div className="space-y-4">
          {bothDup && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Cliente já cadastrado</AlertTitle>
              <AlertDescription>
                Este CNPJ já existe no TiFlux e no VHSYS. Não é possível cadastrar novamente.
              </AlertDescription>
            </Alert>
          )}

          {onlyTf && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Cliente já existe no TiFlux</AlertTitle>
              <AlertDescription>
                Este CNPJ já está cadastrado no TiFlux. Deseja cadastrá-lo apenas no VHSYS?
              </AlertDescription>
            </Alert>
          )}

          {onlyVh && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Cliente já existe no VHSYS</AlertTitle>
              <AlertDescription>
                Este CNPJ já está cadastrado no VHSYS. Deseja cadastrá-lo apenas no TiFlux?
              </AlertDescription>
            </Alert>
          )}

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Dados da empresa</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="font-semibold">{String(company.legal_name || company.trade_name)}</p>
                <p className="font-mono text-muted-foreground">{formatCnpj(String(company.cnpj_digits || ''))}</p>
                <div className="flex gap-2 pt-2">
                  <Badge variant={dupTf ? 'destructive' : 'secondary'}>TiFlux {dupTf ? 'existente' : 'novo'}</Badge>
                  <Badge variant={dupVh ? 'destructive' : 'secondary'}>VHSYS {dupVh ? 'existente' : 'novo'}</Badge>
                </div>
              </CardContent>
            </Card>

            {needsTifluxConfig && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Configuração TiFlux</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div ref={listRef}>
                    <p className="mb-2 text-sm font-medium">Mesas de atendimento</p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {desks.map((d) => {
                        const id = Number(d.id)
                        const checked = deskIds.includes(id)
                        return (
                          <SpotlightSelectable
                            key={id}
                            as="label"
                            accent="accent"
                            selected={checked}
                            className="cursor-pointer p-2 text-sm"
                            innerClassName="flex items-center gap-2"
                          >
                            <Checkbox
                              checked={checked}
                              onCheckedChange={(c) =>
                                setDeskIds((prev) => (c ? [...prev, id] : prev.filter((x) => x !== id)))
                              }
                            />
                            {String(d.display_name || d.name)}
                          </SpotlightSelectable>
                        )
                      })}
                    </div>
                  </div>
                  <div>
                    <p className="mb-2 text-sm font-medium">Grupos de atendentes</p>
                    <div className="grid max-h-48 gap-2 overflow-y-auto sm:grid-cols-2">
                      {groups.map((g) => {
                        const id = Number(g.id)
                        const checked = groupIds.includes(id)
                        return (
                          <SpotlightSelectable
                            key={id}
                            as="label"
                            accent="accent"
                            selected={checked}
                            className="cursor-pointer p-2 text-sm"
                            innerClassName="flex items-center gap-2"
                          >
                            <Checkbox
                              checked={checked}
                              onCheckedChange={(c) =>
                                setGroupIds((prev) => (c ? [...prev, id] : prev.filter((x) => x !== id)))
                              }
                            />
                            {String(g.name)}
                          </SpotlightSelectable>
                        )
                      })}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {Boolean(preview?.requires_inactive_override) && (
            <Alert variant="destructive">
              <AlertTitle>Situação cadastral inativa</AlertTitle>
              <AlertDescription className="flex items-start gap-2 pt-2">
                <Checkbox checked={overrideInactive} onCheckedChange={(v) => setOverrideInactive(!!v)} />
                Autorizo cadastro com situação cadastral inativa na Receita
              </AlertDescription>
            </Alert>
          )}

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setStep(1)}>Voltar</Button>

            {bothDup && (
              <Button variant="outline" onClick={resetFlow}>Cancelar</Button>
            )}

            {onlyTf && (
              <>
                <Button onClick={() => handleIntegrate(['vhsys'])} loading={loading}>
                  Cadastrar no VHSYS
                </Button>
                <Button variant="outline" onClick={resetFlow}>Cancelar</Button>
              </>
            )}

            {onlyVh && (
              <>
                <Button
                  onClick={() => handleIntegrate(['tiflux'])}
                  loading={loading}
                  disabled={!deskIds.length || !groupIds.length}
                >
                  Cadastrar no TiFlux
                </Button>
                <Button variant="outline" onClick={resetFlow}>Cancelar</Button>
              </>
            )}

            {!bothDup && !onlyTf && !onlyVh && (
              <Button
                onClick={() => handleIntegrate()}
                loading={loading}
                disabled={!deskIds.length || !groupIds.length}
              >
                Confirmar cadastro
              </Button>
            )}
          </div>
        </div>
      )}

      {loading && step === 2 && (
        <div className="mt-4 space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      )}

      {step === 3 && result && (
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center gap-3">
              <CheckCircle2
                className={
                  result.all_duplicates
                    ? 'h-8 w-8 text-destructive'
                    : result.success
                      ? 'h-8 w-8 text-emerald-600'
                      : 'h-8 w-8 text-amber-500'
                }
              />
              <div>
                <p className="font-semibold">
                  {result.all_duplicates
                    ? 'Cliente já cadastrado'
                    : result.success
                      ? result.partial
                        ? 'Cadastro concluído em um sistema'
                        : 'Cadastro concluído com sucesso'
                      : 'Cadastro concluído com ressalvas'}
                </p>
                <div className="mt-2 flex gap-2">
                  <Badge variant={tfResult?.skipped ? 'warning' : tfResult?.success ? 'success' : 'destructive'}>
                    TiFlux
                  </Badge>
                  <Badge variant={vhResult?.skipped ? 'warning' : vhResult?.success ? 'success' : 'destructive'}>
                    VHSYS
                  </Badge>
                </div>
              </div>
            </div>
            <Accordion type="single" collapsible>
              <AccordionItem value="details">
                <AccordionTrigger>Detalhes técnicos</AccordionTrigger>
                <AccordionContent>
                  <pre className="overflow-auto rounded-lg bg-muted p-4 text-xs font-mono">{JSON.stringify(result, null, 2)}</pre>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
            <Button variant="outline" onClick={resetFlow}>
              Nova consulta
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
