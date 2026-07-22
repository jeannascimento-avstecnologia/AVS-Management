import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, Loader2, Landmark } from 'lucide-react'
import { toast } from 'sonner'
import { ApiError, api, type BillingStatus } from '@/api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { usePermission } from '@/hooks/useAuth'
import { formatCnpj, formatDate } from '@/lib/format'
import { btnSecondaryClass, btnTealClass } from '@/lib/ui-classes'

const STATUS_LABELS: Record<BillingStatus, string> = {
  draft: 'Rascunho',
  approved: 'Aprovado',
  awaiting_prefeitura: 'Aguardando prefeitura',
  emitting: 'Emitindo',
  sent: 'Enviado',
  error: 'Erro',
}

function statusVariant(
  status: BillingStatus,
): 'secondary' | 'info' | 'success' | 'destructive' | 'warning' | 'outline' {
  switch (status) {
    case 'draft':
      return 'secondary'
    case 'awaiting_prefeitura':
    case 'emitting':
      return 'warning'
    case 'approved':
    case 'sent':
      return 'success'
    case 'error':
      return 'destructive'
    default:
      return 'outline'
  }
}

function formatBrl(value: number | null | undefined): string {
  if (value == null) return '—'
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function BillingDetailPage() {
  const { id: idParam } = useParams<{ id: string }>()
  const runId = Number(idParam)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const canApprove = usePermission('aprovar_fatura')
  const [nfNumber, setNfNumber] = useState('')
  const [netTotal, setNetTotal] = useState('')

  const detailQuery = useQuery({
    queryKey: ['billing-run', runId],
    queryFn: () => api.getBillingRun(runId),
    enabled: Number.isFinite(runId) && runId > 0,
  })

  const approveMutation = useMutation({
    mutationFn: () => api.approveBillingRun(runId),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['billing-run', runId] })
      void queryClient.invalidateQueries({ queryKey: ['billing-runs'] })
      if (result.status === 'awaiting_prefeitura') {
        toast.success(`#${runId} aguardando NF prefeitura`)
        return
      }
      const dryNote = result.dry_run ? ' (dry-run — sem POST externo)' : ''
      toast.success(`Faturamento #${runId} aprovado${dryNote}`)
    },
    onError: (err: Error) => {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          toast.error('Sem permissão para aprovar fatura.')
          return
        }
        if (err.status === 409) {
          toast.error(err.message || 'Faturamento não elegível para aprovação.')
          return
        }
      }
      toast.error(err.message || 'Falha ao aprovar')
    },
  })

  const prefeituraMutation = useMutation({
    mutationFn: () => {
      const net = Number(netTotal.replace(',', '.'))
      return api.submitBillingPrefeitura(runId, {
        nf_prefeitura_number: nfNumber.trim(),
        net_total: net,
      })
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['billing-run', runId] })
      void queryClient.invalidateQueries({ queryKey: ['billing-runs'] })
      const dryNote = result.dry_run ? ' (dry-run — sem POST externo)' : ''
      toast.success(`NF prefeitura registrada${dryNote}`)
      setNfNumber('')
      setNetTotal('')
    },
    onError: (err: Error) => {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          toast.error('Sem permissão para registrar NF prefeitura.')
          return
        }
        if (err.status === 409) {
          toast.error(err.message || 'Faturamento não elegível para prefeitura.')
          return
        }
      }
      toast.error(err.message || 'Falha ao registrar NF prefeitura')
    },
  })

  function handlePrefeitura(e: React.FormEvent) {
    e.preventDefault()
    if (!nfNumber.trim()) {
      toast.error('Informe o número da NF prefeitura.')
      return
    }
    const net = Number(netTotal.replace(',', '.'))
    if (!Number.isFinite(net) || net <= 0) {
      toast.error('Informe o líquido (net_total) maior que zero.')
      return
    }
    prefeituraMutation.mutate()
  }

  if (!Number.isFinite(runId) || runId <= 0) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          ID inválido. <Link to="/faturamento">Voltar à lista</Link>
        </AlertDescription>
      </Alert>
    )
  }

  if (detailQuery.isPending) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {detailQuery.error instanceof Error
              ? detailQuery.error.message
              : 'Faturamento não encontrado.'}
          </AlertDescription>
        </Alert>
        <Button type="button" className={btnSecondaryClass} onClick={() => navigate('/faturamento')}>
          Voltar à lista
        </Button>
      </div>
    )
  }

  const run = detailQuery.data
  const showApprove = run.status === 'draft' && canApprove
  const showPrefeitura = run.status === 'awaiting_prefeitura' && canApprove

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="mb-1 inline-flex items-center gap-2 rounded-lg bg-aurora-teal-muted px-3 py-1.5 text-aurora-teal">
            <Landmark className="h-4 w-4" />
            <span className="text-xs font-semibold uppercase tracking-wide">Hub · Faturamento</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">Faturamento #{run.id}</h1>
            <Badge variant={statusVariant(run.status)}>{STATUS_LABELS[run.status]}</Badge>
            {run.has_retencao && <Badge variant="outline">Retenção</Badge>}
          </div>
          <p className="text-sm text-muted-foreground">
            {formatCnpj(run.cnpj)} · {run.client_name || 'Cliente não informado'} ·{' '}
            {run.competence}
          </p>
        </div>
        <Button type="button" className={btnSecondaryClass} onClick={() => navigate('/faturamento')}>
          Voltar
        </Button>
      </div>

      <Card className="border-aurora-teal/25 bg-aurora-surface shadow-sm hub-panel-enter">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Resumo</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <p className="text-muted-foreground">Bruto</p>
            <p className="font-medium">{formatBrl(run.gross_total)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Desconto %</p>
            <p className="font-medium">
              {run.discount_pct != null ? `${run.discount_pct}%` : '—'}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Desconto R$</p>
            <p className="font-medium">{formatBrl(run.discount_value)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Líquido</p>
            <p className="font-medium">{formatBrl(run.net_total)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Pagamento</p>
            <p className="font-medium">{run.payment_method || '—'}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Vencimento</p>
            <p className="font-medium">{run.due_date || '—'}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Atualizado</p>
            <p className="font-medium">{formatDate(run.updated_at)}</p>
          </div>
          {run.nf_prefeitura_number && (
            <div>
              <p className="text-muted-foreground">NF prefeitura</p>
              <p className="font-medium">{run.nf_prefeitura_number}</p>
            </div>
          )}
          {run.error_message && (
            <div className="sm:col-span-2">
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{run.error_message}</AlertDescription>
              </Alert>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-aurora-border bg-aurora-surface shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Itens ({run.items.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {run.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum item.</p>
          ) : (
            <ul className="divide-y divide-aurora-border">
              {run.items.map((item) => (
                <li
                  key={item.id}
                  className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.description}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.source}
                      {item.external_ref ? ` · ${item.external_ref}` : ''}
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-medium">{formatBrl(item.amount)}</p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {showApprove && (
        <Card className="border-aurora-border bg-aurora-surface shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Aprovar</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {run.has_retencao
                ? 'Com retenção: status → aguardando prefeitura (sem outbox ainda).'
                : 'Sem retenção: status → aprovado + outbox billing.approved (dry-run).'}
            </p>
            <Button
              type="button"
              className={btnTealClass}
              disabled={approveMutation.isPending}
              onClick={() => approveMutation.mutate()}
            >
              {approveMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              Aprovar fatura
            </Button>
          </CardContent>
        </Card>
      )}

      {run.status === 'draft' && !canApprove && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Sem permissão <code className="text-xs">aprovar_fatura</code> para aprovar este
            rascunho.
          </AlertDescription>
        </Alert>
      )}

      {showPrefeitura && (
        <Card className="border-aurora-border bg-aurora-surface shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">NF Prefeitura</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePrefeitura} className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
              <div className="space-y-2">
                <Label htmlFor="nf-prefeitura">Número NF</Label>
                <Input
                  id="nf-prefeitura"
                  value={nfNumber}
                  onChange={(e) => setNfNumber(e.target.value)}
                  placeholder="NF-123"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="net-total">Valor líquido</Label>
                <Input
                  id="net-total"
                  type="text"
                  inputMode="decimal"
                  value={netTotal}
                  onChange={(e) => setNetTotal(e.target.value)}
                  placeholder="Ex.: 1500,00"
                  required
                />
              </div>
              <Button
                type="submit"
                className={btnTealClass}
                disabled={prefeituraMutation.isPending}
              >
                {prefeituraMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Landmark className="h-4 w-4" />
                )}
                Registrar
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {run.status === 'awaiting_prefeitura' && !canApprove && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Sem permissão <code className="text-xs">aprovar_fatura</code> para registrar NF
            prefeitura.
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}
