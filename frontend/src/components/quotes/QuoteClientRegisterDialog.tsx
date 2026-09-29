import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { AlertCircle } from 'lucide-react'
import {
  api,
  type PersonType,
  type QuoteClientAddress,
  type QuoteClientCompanyPayload,
  type QuoteClientPreviewResponse,
  type QuoteClientRegisterResponse,
} from '@/api/client'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { SpotlightSelectable } from '@/components/ui/SpotlightSelectable'
import {
  digitsOnly,
  formatClientDocument,
  isClientDocument,
  isValidCpf,
  maskCpfInput,
} from '@/lib/format'
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
  initialPersonType?: PersonType
  initialDocument?: string
  onLinked: (link: QuoteClientLink) => void
}

const EMPTY_ADDRESS: QuoteClientAddress = {
  street: '',
  number: '',
  complement: '',
  district: '',
  city: '',
  state: '',
  zip_code: '',
}

function readDuplicates(preview: QuoteClientPreviewResponse | null) {
  const dupTf = Boolean(preview?.duplicates.tiflux)
  const dupVh = Boolean(preview?.duplicates.vhsys)
  return {
    dupTf,
    dupVh,
    bothDup: dupTf && dupVh,
    onlyTf: dupTf && !dupVh,
    onlyVh: dupVh && !dupTf,
  }
}

function optionalId(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) {
    return Number(value)
  }
  return null
}

function companyFromPreview(
  company: QuoteClientCompanyPayload,
  person: PersonType,
): QuoteClientCompanyPayload {
  const address = company.address ?? EMPTY_ADDRESS
  const personType = company.person_type === 'PF' || company.person_type === 'PJ' ? company.person_type : person
  return {
    person_type: personType,
    cnpj_digits: digitsOnly(company.cnpj_digits || ''),
    legal_name: company.legal_name || '',
    trade_name: company.trade_name || '',
    phone: company.phone || '',
    email: company.email || '',
    status_active: company.status_active !== false,
    registration_status: company.registration_status || '',
    address: {
      street: address.street || '',
      number: address.number || '',
      complement: address.complement || '',
      district: address.district || '',
      city: address.city || '',
      state: address.state || '',
      zip_code: address.zip_code || '',
    },
  }
}

function extractClientLink(result: QuoteClientRegisterResponse, fallback: QuoteClientCompanyPayload): QuoteClientLink {
  const company = result.company
  const tf = result.tiflux.data
  const vh = result.vhsys.data
  const nested = vh?.data
  const cnpj = digitsOnly(company?.cnpj_digits || fallback.cnpj_digits)
  const client_name = String(company?.legal_name || company?.trade_name || fallback.legal_name || '').trim()
  return {
    cnpj,
    client_name,
    tiflux_client_id: optionalId(tf?.id),
    vhsys_client_id: optionalId(vh?.id_cliente) ?? optionalId(vh?.id) ?? optionalId(nested?.id_cliente) ?? optionalId(nested?.id),
  }
}

export function QuoteClientRegisterDialog({
  open,
  onOpenChange,
  initialPersonType = 'PJ',
  initialDocument = '',
  onLinked,
}: QuoteClientRegisterDialogProps) {
  const [step, setStep] = useState<1 | 2>(1)
  const [personType, setPersonType] = useState<PersonType>(initialPersonType)
  const [documentValue, setDocumentValue] = useState(initialDocument)
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<QuoteClientPreviewResponse | null>(null)
  const [company, setCompany] = useState<QuoteClientCompanyPayload | null>(null)
  const [deskIds, setDeskIds] = useState<number[]>([])
  const [groupIds, setGroupIds] = useState<number[]>([])
  const [overrideInactive, setOverrideInactive] = useState(false)

  useEffect(() => {
    if (!open) return
    setStep(1)
    setPersonType(initialPersonType)
    setDocumentValue(
      initialPersonType === 'PF' ? maskCpfInput(initialDocument) : initialDocument,
    )
    setPreview(null)
    setCompany(null)
    setDeskIds([])
    setGroupIds([])
    setOverrideInactive(false)
    setLoading(false)
  }, [open, initialPersonType, initialDocument])

  const desks = preview?.tiflux_options.desks ?? []
  const groups = preview?.tiflux_options.technical_groups ?? []
  const { dupTf, dupVh, bothDup, onlyTf, onlyVh } = readDuplicates(preview)
  const needsDesks = !dupTf
  const needsTifluxConfig = needsDesks
  const canConfirm = Boolean(
    company &&
      company.legal_name.trim() &&
      isClientDocument(company.cnpj_digits) &&
      (!needsDesks || (deskIds.length > 0 && groupIds.length > 0)) &&
      (!preview?.requires_inactive_override || overrideInactive),
  )

  function patchCompany(patch: Partial<QuoteClientCompanyPayload>) {
    setCompany((prev) => (prev ? { ...prev, ...patch } : prev))
  }

  function patchAddress(patch: Partial<QuoteClientAddress>) {
    setCompany((prev) =>
      prev ? { ...prev, address: { ...prev.address, ...patch } } : prev,
    )
  }

  function finishWithResult(data: QuoteClientRegisterResponse, draft: QuoteClientCompanyPayload) {
    const tfOk = Boolean(data.tiflux?.success)
    if (!tfOk) {
      toast.error(
        data.partial_message ||
          data.tiflux?.error ||
          'TiFlux não confirmou o cliente. Sem o TiFlux ele não pode ser vinculado.',
      )
      return
    }
    const link = extractClientLink(data, draft)
    if (!isClientDocument(link.cnpj) || link.tiflux_client_id == null) {
      toast.error('Resposta sem cliente TiFlux utilizável.')
      return
    }
    onLinked(link)
    onOpenChange(false)
    if (data.partial_message) {
      toast.warning(data.partial_message)
      return
    }
    if (data.all_duplicates) {
      toast.success('Cliente já cadastrado — vinculado ao orçamento.')
      return
    }
    toast.success('Cliente cadastrado e vinculado ao orçamento.')
  }

  async function handlePreview(e: React.FormEvent) {
    e.preventDefault()
    const digits = digitsOnly(documentValue)
    if (personType === 'PJ' && !isClientDocument(digits)) {
      toast.error('Informe um CNPJ válido (14 dígitos).')
      return
    }
    if (personType === 'PF' && !isValidCpf(digits)) {
      toast.error('Informe um CPF válido (11 dígitos).')
      return
    }
    setLoading(true)
    try {
      const data = await api.previewQuoteClient({ person_type: personType, document: digits })
      setPreview(data)
      const draft = companyFromPreview(data.company, personType)
      setCompany(draft)
      const def = data.tiflux_options.defaults
      setDeskIds((def?.desk_ids ?? []).map((x) => Number(x)).filter((n) => Number.isFinite(n)))
      setGroupIds(
        (def?.technical_group_ids ?? []).map((x) => Number(x)).filter((n) => Number.isFinite(n)),
      )
      setStep(2)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao consultar documento')
    } finally {
      setLoading(false)
    }
  }

  async function handleIntegrate() {
    if (!company) return
    if (needsDesks && (deskIds.length === 0 || groupIds.length === 0)) {
      toast.error('Selecione ao menos uma mesa e um grupo. Sem isso o cliente fica invisível no TiFlux.')
      return
    }
    setLoading(true)
    try {
      const data = await api.registerQuoteClient({
        company,
        desk_ids: deskIds,
        technical_group_ids: groupIds,
        override_inactive_registration: overrideInactive,
      })
      if (!data.success && !data.all_duplicates && !data.partial) {
        toast.error(data.error || 'Não foi possível concluir o cadastro.')
        return
      }
      finishWithResult(data, company)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro na integração')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Cadastrar novo cliente</DialogTitle>
          <DialogDescription>
            Pessoa jurídica consulta o CNPJ na BrasilAPI. Pessoa física segue direto para a revisão.
            O cadastro grava em TiFlux e VHSYS sem sair do orçamento.
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <form onSubmit={handlePreview} className="space-y-4">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Tipo de pessoa">
              <Button
                type="button"
                className={cn(btnSecondaryClass, personType === 'PJ' && 'border-aurora-green text-aurora-green')}
                onClick={() => {
                  setPersonType('PJ')
                  setDocumentValue('')
                }}
              >
                Pessoa jurídica
              </Button>
              <Button
                type="button"
                className={cn(btnSecondaryClass, personType === 'PF' && 'border-aurora-green text-aurora-green')}
                onClick={() => {
                  setPersonType('PF')
                  setDocumentValue('')
                }}
              >
                Pessoa física
              </Button>
            </div>
            <div className="space-y-2">
              <Label htmlFor="quote-reg-doc">{personType === 'PF' ? 'CPF' : 'CNPJ'}</Label>
              {personType === 'PJ' ? (
                <CnpjInput
                  id="quote-reg-doc"
                  value={documentValue}
                  onValueChange={setDocumentValue}
                  placeholder="00.000.000/0000-00"
                  required
                />
              ) : (
                <Input
                  id="quote-reg-doc"
                  inputMode="numeric"
                  autoComplete="off"
                  value={documentValue}
                  placeholder="000.000.000-00"
                  required
                  onChange={(e) => setDocumentValue(maskCpfInput(e.target.value))}
                />
              )}
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
                {personType === 'PJ' ? 'Consultar CNPJ' : 'Continuar'}
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
                  Documento existe no TiFlux e no VHSYS. Você pode vincular os IDs existentes a este
                  orçamento.
                </AlertDescription>
              </Alert>
            )}
            {onlyTf && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Já existe no TiFlux</AlertTitle>
                <AlertDescription>O cadastro cria só no VHSYS e vincula o TiFlux existente.</AlertDescription>
              </Alert>
            )}
            {onlyVh && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Já existe no VHSYS</AlertTitle>
                <AlertDescription>O cadastro cria só no TiFlux e vincula os dois.</AlertDescription>
              </Alert>
            )}

            <div className="flex flex-wrap gap-2">
              <Badge variant={dupTf ? 'destructive' : 'secondary'}>
                TiFlux {dupTf ? 'existente' : 'novo'}
              </Badge>
              <Badge variant={dupVh ? 'destructive' : 'secondary'}>
                VHSYS {dupVh ? 'existente' : 'novo'}
              </Badge>
              <span className="font-mono text-xs text-muted-foreground">
                {formatClientDocument(company.cnpj_digits)}
              </span>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="quote-reg-legal">{personType === 'PF' ? 'Nome' : 'Razão social'}</Label>
                <Input
                  id="quote-reg-legal"
                  value={company.legal_name}
                  onChange={(e) => patchCompany({ legal_name: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="quote-reg-trade">{personType === 'PF' ? 'Nome social' : 'Nome fantasia'}</Label>
                <Input
                  id="quote-reg-trade"
                  value={company.trade_name}
                  onChange={(e) => patchCompany({ trade_name: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="quote-reg-email">E-mail</Label>
                <Input
                  id="quote-reg-email"
                  value={company.email}
                  onChange={(e) => patchCompany({ email: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="quote-reg-phone">Telefone</Label>
                <Input
                  id="quote-reg-phone"
                  value={company.phone}
                  onChange={(e) => patchCompany({ phone: e.target.value })}
                />
              </div>
              <div className="space-y-1 sm:col-span-2">
                <Label htmlFor="quote-reg-street">Logradouro</Label>
                <Input
                  id="quote-reg-street"
                  value={company.address.street}
                  onChange={(e) => patchAddress({ street: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="quote-reg-number">Número</Label>
                <Input
                  id="quote-reg-number"
                  value={company.address.number}
                  onChange={(e) => patchAddress({ number: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="quote-reg-district">Bairro</Label>
                <Input
                  id="quote-reg-district"
                  value={company.address.district}
                  onChange={(e) => patchAddress({ district: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="quote-reg-city">Cidade</Label>
                <Input
                  id="quote-reg-city"
                  value={company.address.city}
                  onChange={(e) => patchAddress({ city: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="quote-reg-state">UF</Label>
                <Input
                  id="quote-reg-state"
                  value={company.address.state}
                  maxLength={2}
                  onChange={(e) => patchAddress({ state: e.target.value.toUpperCase() })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="quote-reg-zip">CEP</Label>
                <Input
                  id="quote-reg-zip"
                  value={company.address.zip_code}
                  onChange={(e) => patchAddress({ zip_code: e.target.value })}
                />
              </div>
            </div>

            {needsTifluxConfig && (
              <div className="space-y-3 rounded-lg border border-aurora-border p-3">
                <div>
                  <p className="text-sm font-medium">Mesas TiFlux</p>
                  <p className="text-xs text-muted-foreground">
                    Mesa e grupo são obrigatórios. Sem os dois o cliente é criado e fica invisível no painel.
                  </p>
                </div>
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
                            setDeskIds((prev) => (c ? [...prev, id] : prev.filter((x) => x !== id)))
                          }
                        />
                        {d.display_name || d.name}
                      </SpotlightSelectable>
                    )
                  })}
                </div>
                <p className="text-sm font-medium">Grupos de atendentes</p>
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
                            setGroupIds((prev) => (c ? [...prev, id] : prev.filter((x) => x !== id)))
                          }
                        />
                        {g.name}
                      </SpotlightSelectable>
                    )
                  })}
                </div>
              </div>
            )}

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
