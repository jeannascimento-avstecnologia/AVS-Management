import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { AlertCircle } from 'lucide-react'
import { api } from '@/api/client'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { CnpjInput } from '@/components/ui/CnpjInput'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { SpotlightSelectable } from '@/components/ui/SpotlightSelectable'
import { digitsOnly, formatCnpj } from '@/lib/format'
import { btnAccentClass, btnSecondaryClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

export type QuoteClientLink = {
  cnpj: string
  client_name: string
  tiflux_client_id: number | null
  vhsys_client_id: number | null
}

type QuoteClientRegisterDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialCnpj?: string
  onLinked: (link: QuoteClientLink) => void
}

function readDuplicates(preview: Record<string, unknown> | null) {
  const d = (preview?.duplicates as Record<string, unknown> | undefined) || {}
  const dupTf = Boolean(d.tiflux)
  const dupVh = Boolean(d.vhsys)
  return {
    dupTf,
    dupVh,
    bothDup: dupTf && dupVh,
    onlyTf: dupTf && !dupVh,
    onlyVh: dupVh && !dupTf,
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function optionalId(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) {
    return Number(value)
  }
  return null
}

function extractClientLink(result: Record<string, unknown>): QuoteClientLink {
  const company = asRecord(result.company)
  const tf = asRecord(result.tiflux)
  const vh = asRecord(result.vhsys)
  const tfData = asRecord(tf?.data)
  const vhData = asRecord(vh?.data)

  const cnpj =
    digitsOnly(String(company?.cnpj_digits || company?.cnpj || result.cnpj || '')) ||
    digitsOnly(String(result.cnpj || ''))

  const client_name = String(
    company?.legal_name || company?.trade_name || '',
  ).trim()

  return {
    cnpj,
    client_name,
    tiflux_client_id: optionalId(tfData?.id),
    vhsys_client_id: optionalId(vhData?.id_cliente) ?? optionalId(vhData?.id),
  }
}

export function QuoteClientRegisterDialog({
  open,
  onOpenChange,
  initialCnpj = '',
  onLinked,
}: QuoteClientRegisterDialogProps) {
  const [step, setStep] = useState<1 | 2>(1)
  const [cnpj, setCnpj] = useState(initialCnpj)
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const [deskIds, setDeskIds] = useState<number[]>([])
  const [groupIds, setGroupIds] = useState<number[]>([])
  const [overrideInactive, setOverrideInactive] = useState(false)

  useEffect(() => {
    if (!open) return
    setStep(1)
    setCnpj(initialCnpj)
    setPreview(null)
    setDeskIds([])
    setGroupIds([])
    setOverrideInactive(false)
    setLoading(false)
  }, [open, initialCnpj])

  const company = asRecord(preview?.company)
  const opts = asRecord(preview?.tiflux_options)
  const desks = (opts?.desks as Array<Record<string, unknown>> | undefined) || []
  const groups = (opts?.technical_groups as Array<Record<string, unknown>> | undefined) || []
  const { dupTf, dupVh, bothDup, onlyTf, onlyVh } = readDuplicates(preview)
  const needsTifluxConfig = !onlyVh

  function finishWithResult(data: Record<string, unknown>) {
    const link = extractClientLink(data)
    if (digitsOnly(link.cnpj).length !== 14) {
      toast.error('Resposta sem CNPJ válido.')
      return
    }
    onLinked(link)
    onOpenChange(false)
    if (data.all_duplicates) {
      toast.success('Cliente já cadastrado — vinculado ao orçamento.')
    } else if (data.success && data.partial) {
      toast.success('Cliente cadastrado no sistema pendente e vinculado.')
    } else if (data.success) {
      toast.success('Cliente integrado e vinculado ao orçamento.')
    } else {
      toast.success('Cliente vinculado ao orçamento.')
    }
  }

  async function handlePreview(e: React.FormEvent) {
    e.preventDefault()
    if (digitsOnly(cnpj).length !== 14) {
      toast.error('Informe um CNPJ válido (14 dígitos).')
      return
    }
    setLoading(true)
    try {
      const data = await api.previewCnpj(cnpj)
      setPreview(data)
      const d = asRecord(data.tiflux_options)
      const def = asRecord(d?.defaults)
      const deskRaw = def?.desk_ids
      const groupRaw = def?.technical_group_ids
      setDeskIds(
        Array.isArray(deskRaw) ? deskRaw.map((x) => Number(x)).filter((n) => Number.isFinite(n)) : [],
      )
      setGroupIds(
        Array.isArray(groupRaw)
          ? groupRaw.map((x) => Number(x)).filter((n) => Number.isFinite(n))
          : [],
      )
      setStep(2)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao consultar CNPJ')
    } finally {
      setLoading(false)
    }
  }

  /** Sempre ambos os sistemas: duplicata devolve ID via skipped+data; cria o que faltar. */
  async function handleIntegrate() {
    if (!company) return
    setLoading(true)
    try {
      const data = await api.integrarForQuote({
        company,
        desk_ids: deskIds,
        technical_group_ids: groupIds,
        override_inactive_registration: overrideInactive,
      })

      if (!data.success && !data.all_duplicates && !data.partial) {
        toast.error(String(data.error || 'Não foi possível concluir o cadastro.'))
        return
      }

      finishWithResult(data)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro na integração')
    } finally {
      setLoading(false)
    }
  }

  const needsDesks = !dupTf
  const canConfirm = !needsDesks || (deskIds.length > 0 && groupIds.length > 0)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Cadastrar cliente</DialogTitle>
          <DialogDescription>
            Consulta CNPJ e integra TiFlux/VHSYS sem sair do orçamento. Itens do rascunho
            permanecem intactos.
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <form onSubmit={handlePreview} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="quote-reg-cnpj">CNPJ</Label>
              <CnpjInput
                id="quote-reg-cnpj"
                value={cnpj}
                onValueChange={setCnpj}
                placeholder="00.000.000/0000-00"
                required
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className={btnSecondaryClass}
                onClick={() => onOpenChange(false)}
                disabled={loading}
              >
                Cancelar
              </Button>
              <Button type="submit" loading={loading} className={cn(btnAccentClass)}>
                Consultar CNPJ
              </Button>
            </div>
          </form>
        )}

        {step === 2 && company && (
          <div className="space-y-4">
            {bothDup && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Cliente já cadastrado</AlertTitle>
                <AlertDescription>
                  CNPJ existe no TiFlux e no VHSYS. Você pode vincular os IDs existentes a este
                  orçamento.
                </AlertDescription>
              </Alert>
            )}

            {onlyTf && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Já existe no TiFlux</AlertTitle>
                <AlertDescription>
                  Deseja cadastrar apenas no VHSYS e vincular ao orçamento?
                </AlertDescription>
              </Alert>
            )}

            {onlyVh && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Já existe no VHSYS</AlertTitle>
                <AlertDescription>
                  Deseja cadastrar apenas no TiFlux e vincular ao orçamento?
                </AlertDescription>
              </Alert>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2 rounded-lg border border-aurora-border p-3 text-sm">
                <p className="font-semibold">
                  {String(company.legal_name || company.trade_name || '—')}
                </p>
                <p className="font-mono text-muted-foreground">
                  {formatCnpj(String(company.cnpj_digits || ''))}
                </p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <Badge variant={dupTf ? 'destructive' : 'secondary'}>
                    TiFlux {dupTf ? 'existente' : 'novo'}
                  </Badge>
                  <Badge variant={dupVh ? 'destructive' : 'secondary'}>
                    VHSYS {dupVh ? 'existente' : 'novo'}
                  </Badge>
                </div>
              </div>

              {needsTifluxConfig && (
                <div className="space-y-3 rounded-lg border border-aurora-border p-3">
                  <p className="text-sm font-medium">Mesas TiFlux</p>
                  <div className="grid max-h-36 gap-2 overflow-y-auto sm:grid-cols-2">
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
                              setDeskIds((prev) =>
                                c ? [...prev, id] : prev.filter((x) => x !== id),
                              )
                            }
                          />
                          {String(d.display_name || d.name)}
                        </SpotlightSelectable>
                      )
                    })}
                  </div>
                  <p className="text-sm font-medium">Grupos</p>
                  <div className="grid max-h-36 gap-2 overflow-y-auto sm:grid-cols-2">
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
                              setGroupIds((prev) =>
                                c ? [...prev, id] : prev.filter((x) => x !== id),
                              )
                            }
                          />
                          {String(g.name)}
                        </SpotlightSelectable>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>

            {Boolean(preview?.requires_inactive_override) && (
              <Alert variant="destructive">
                <AlertTitle>Situação cadastral inativa</AlertTitle>
                <AlertDescription className="flex items-start gap-2 pt-2">
                  <Checkbox
                    checked={overrideInactive}
                    onCheckedChange={(v) => setOverrideInactive(!!v)}
                  />
                  Autorizo cadastro com situação cadastral inativa na Receita
                </AlertDescription>
              </Alert>
            )}

            {loading && (
              <div className="space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className={btnSecondaryClass}
                disabled={loading}
                onClick={() => setStep(1)}
              >
                Voltar
              </Button>

              <Button
                type="button"
                className={btnAccentClass}
                loading={loading}
                disabled={!canConfirm}
                onClick={() => void handleIntegrate()}
              >
                {bothDup
                  ? 'Usar cliente existente'
                  : onlyTf
                    ? 'Cadastrar VHSYS e vincular'
                    : onlyVh
                      ? 'Cadastrar TiFlux e vincular'
                      : 'Confirmar e vincular'}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
