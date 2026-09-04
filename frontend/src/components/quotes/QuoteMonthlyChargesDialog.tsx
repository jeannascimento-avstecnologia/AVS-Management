import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { api, type QuoteMonthlyAllocationWrite, type QuoteMonthlyDraftWrite } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/cn'

type Line = {
  localKey: string
  itemId: number | null
  section: string
  sectionTitle: string
  name: string
  total: number
}

type SplitDraft = {
  fornecedorName: string
  fornecedor: string
  intermediadorName: string
  intermediador: string
  source: 'vhsys' | 'manual'
  warning: string | null
  vhsysProductId: number | null
  locked: boolean
}

function money(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

function parseAmt(raw: string): number {
  return Number.parseFloat(raw.replace(',', '.')) || 0
}

function emptySplit(): SplitDraft {
  return {
    fornecedorName: 'Fornecedor',
    fornecedor: '',
    intermediadorName: 'AVS TECNOLOGIA',
    intermediador: '',
    source: 'manual',
    warning: null,
    vhsysProductId: null,
    locked: true,
  }
}

function fromAllocation(a: QuoteMonthlyAllocationWrite): SplitDraft {
  return {
    fornecedorName: a.fornecedor_name || 'Fornecedor',
    fornecedor: String(a.fornecedor_amount),
    intermediadorName: a.intermediador_name || 'AVS TECNOLOGIA',
    intermediador: String(a.intermediador_amount),
    source: a.source ?? 'manual',
    warning: a.warning ?? null,
    vhsysProductId: a.vhsys_product_id ?? null,
    locked: (a.source ?? 'manual') === 'vhsys',
  }
}

export function QuoteMonthlyChargesDialog({
  open,
  onOpenChange,
  quoteId,
  lines,
  canEdit,
  initialDraft,
  saving,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  quoteId: number
  lines: Line[]
  canEdit: boolean
  initialDraft: QuoteMonthlyDraftWrite | null
  saving: boolean
  onSave: (draft: QuoteMonthlyDraftWrite, selectedLocalKeys: string[]) => Promise<void>
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [splits, setSplits] = useState<Record<string, SplitDraft>>({})
  const [suggesting, setSuggesting] = useState(false)

  useEffect(() => {
    if (!open) return
    const nextSplits: Record<string, SplitDraft> = {}
    const selectedKeys = new Set<string>()
    const allocs = initialDraft?.allocations ?? []
    for (const a of allocs) {
      const line = lines.find((l) => l.itemId != null && l.itemId === a.item_id)
      if (!line) continue
      selectedKeys.add(line.localKey)
      nextSplits[line.localKey] = fromAllocation(a)
    }
    setSplits(nextSplits)
    setSelected(selectedKeys)
  }, [open, initialDraft, lines])

  const available = lines.filter((l) => !selected.has(l.localKey))
  const chosen = lines.filter((l) => selected.has(l.localKey))

  const lineChecks = useMemo(
    () =>
      chosen.map((line) => {
        const s = splits[line.localKey] ?? emptySplit()
        const sum = round2(parseAmt(s.fornecedor) + parseAmt(s.intermediador))
        const delta = round2(line.total - sum)
        return { key: line.localKey, lineTotal: line.total, sum, delta, ok: Math.abs(delta) <= 0.01 }
      }),
    [chosen, splits],
  )

  const allBalanced = chosen.length === 0 || lineChecks.every((c) => c.ok)

  async function applySuggestion(keys: string[]) {
    const itemIds = keys
      .map((k) => lines.find((l) => l.localKey === k)?.itemId)
      .filter((id): id is number => id != null && id >= 1)
    if (itemIds.length === 0) {
      // #region agent log
      fetch('http://127.0.0.1:7624/ingest/4fbad495-1d4e-4120-8a74-d59ccbb75445',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'ae8776'},body:JSON.stringify({sessionId:'ae8776',runId:'pre-fix',hypothesisId:'E',location:'QuoteMonthlyChargesDialog.tsx:applySuggestion',message:'skip suggest: no persisted item ids',data:{keys,quoteId},timestamp:Date.now()})}).catch(()=>{})
      // #endregion
      return
    }
    setSuggesting(true)
    try {
      const { allocations } = await api.suggestQuoteMonthly(quoteId, itemIds)
      // #region agent log
      fetch('http://127.0.0.1:7624/ingest/4fbad495-1d4e-4120-8a74-d59ccbb75445',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'ae8776'},body:JSON.stringify({sessionId:'ae8776',runId:'pre-fix',hypothesisId:'C',location:'QuoteMonthlyChargesDialog.tsx:applySuggestion',message:'suggest ok',data:{itemIds,allocCount:allocations.length,sources:allocations.map((a)=>a.source),costs:allocations.map((a)=>({f:a.fornecedor_amount,i:a.intermediador_amount}))},timestamp:Date.now()})}).catch(()=>{})
      // #endregion
      setSplits((prev) => {
        const next = { ...prev }
        for (const a of allocations) {
          const line = lines.find((l) => l.itemId === a.item_id)
          if (!line) continue
          next[line.localKey] = fromAllocation(a)
        }
        return next
      })
    } catch (err) {
      // #region agent log
      fetch('http://127.0.0.1:7624/ingest/4fbad495-1d4e-4120-8a74-d59ccbb75445',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'ae8776'},body:JSON.stringify({sessionId:'ae8776',runId:'pre-fix',hypothesisId:'A',location:'QuoteMonthlyChargesDialog.tsx:applySuggestion',message:'suggest failed',data:{itemIds,err:err instanceof Error?err.message:String(err)},timestamp:Date.now()})}).catch(()=>{})
      // #endregion
      toast.error(err instanceof Error ? err.message : 'Falha ao buscar mensalidades no VHSYS.')
    } finally {
      setSuggesting(false)
    }
  }

  function toggle(key: string) {
    const line = lines.find((l) => l.localKey === key)
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
        setSplits((s) => {
          const copy = { ...s }
          delete copy[key]
          return copy
        })
      } else {
        next.add(key)
        setSplits((s) => ({ ...s, [key]: s[key] ?? emptySplit() }))
        if (line?.itemId) {
          void applySuggestion([key])
        } else {
          toast.error('Salve os itens antes de marcar mensalidade.')
        }
      }
      return next
    })
  }

  function patchSplit(key: string, patch: Partial<SplitDraft>) {
    setSplits((prev) => ({ ...prev, [key]: { ...(prev[key] ?? emptySplit()), ...patch } }))
  }

  async function handleSave() {
    if (!canEdit) return
    if (chosen.length === 0) {
      await onSave({ allocations: [] }, [])
      return
    }
    const bad = lineChecks.find((c) => !c.ok)
    if (bad) {
      toast.error('Fornecedor + intermediador deve igualar o total de cada linha selecionada.')
      return
    }
    const allocations: QuoteMonthlyAllocationWrite[] = chosen.map((line) => {
      const s = splits[line.localKey] ?? emptySplit()
      return {
        item_id: line.itemId ?? 0,
        fornecedor_name: s.fornecedorName.trim() || 'Fornecedor',
        fornecedor_amount: parseAmt(s.fornecedor),
        intermediador_name: s.intermediadorName.trim() || 'AVS TECNOLOGIA',
        intermediador_amount: parseAmt(s.intermediador),
        vhsys_product_id: s.vhsysProductId,
        source: s.source,
        warning: s.warning,
      }
    })
    await onSave({ allocations }, chosen.map((l) => l.localKey))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Mensalidades</DialogTitle>
          <DialogDescription>
            Marque a linha inteira. Valores de fornecedor (custo VHSYS) e intermediador (margem)
            vêm do cadastro. PDF mostra o recorte também em Dados de pagamento.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label className="text-xs text-muted-foreground">Linhas do orçamento</Label>
            <div className="mt-1.5 max-h-40 space-y-2 overflow-y-auto rounded-lg border border-aurora-border p-2">
              {available.length === 0 ? (
                <p className="px-2 py-3 text-sm text-muted-foreground">
                  {lines.length === 0 ? 'Nenhuma linha no canvas.' : 'Todas as linhas estão na tabela abaixo.'}
                </p>
              ) : (
                available.map((line) => (
                  <label
                    key={line.localKey}
                    className="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-aurora-surface-2/60"
                  >
                    <Checkbox
                      checked={false}
                      disabled={!canEdit || suggesting}
                      onCheckedChange={() => toggle(line.localKey)}
                    />
                    <span className="min-w-0 flex-1 text-sm">
                      <span className="block text-[11px] text-muted-foreground">{line.sectionTitle}</span>
                      <span className="block truncate">{line.name || '(sem nome)'}</span>
                    </span>
                    <span className="shrink-0 text-sm tabular-nums">{money(line.total)}</span>
                  </label>
                ))
              )}
            </div>
          </div>

          <div>
            <Label>Linhas selecionadas</Label>
            <div className="mt-1.5 space-y-3">
              {chosen.length === 0 ? (
                <p className="rounded-lg border border-dashed border-aurora-border px-3 py-4 text-sm text-muted-foreground">
                  Nenhuma linha selecionada.
                </p>
              ) : (
                chosen.map((line) => {
                  const s = splits[line.localKey] ?? emptySplit()
                  const check = lineChecks.find((c) => c.key === line.localKey)
                  const locked = s.locked && canEdit
                  return (
                    <div
                      key={line.localKey}
                      className="space-y-2 rounded-lg border border-aurora-border p-3"
                    >
                      <div className="flex items-start gap-2">
                        <Checkbox
                          checked
                          disabled={!canEdit}
                          onCheckedChange={() => toggle(line.localKey)}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] text-muted-foreground">{line.sectionTitle}</p>
                          <p className="text-sm font-medium">{line.name || '(sem nome)'}</p>
                        </div>
                        <span className="shrink-0 text-sm font-semibold tabular-nums">
                          {money(line.total)}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded bg-aurora-surface-2 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                          {s.source === 'vhsys' ? 'VHSYS' : 'Manual'}
                        </span>
                        {canEdit ? (
                          <>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={suggesting || line.itemId == null}
                              onClick={() => void applySuggestion([line.localKey])}
                            >
                              Recalcular
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => patchSplit(line.localKey, { locked: !s.locked, source: 'manual' })}
                            >
                              {s.locked ? 'Editar manualmente' : 'Travar'}
                            </Button>
                          </>
                        ) : null}
                      </div>
                      {s.warning ? (
                        <p className="text-xs text-amber-600">{s.warning}</p>
                      ) : null}
                      <div className="grid gap-2 sm:grid-cols-2">
                        <div className="space-y-1">
                          <Label className="text-xs">Fornecedor</Label>
                          <div className="flex gap-2">
                            <Input
                              value={s.fornecedorName}
                              disabled={!canEdit || locked}
                              onChange={(e) => patchSplit(line.localKey, { fornecedorName: e.target.value })}
                            />
                            <Input
                              className="w-28"
                              value={s.fornecedor}
                              disabled={!canEdit || locked}
                              placeholder="0,00"
                              inputMode="decimal"
                              onChange={(e) => patchSplit(line.localKey, { fornecedor: e.target.value })}
                            />
                          </div>
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Intermediador</Label>
                          <div className="flex gap-2">
                            <Input
                              value={s.intermediadorName}
                              disabled={!canEdit || locked}
                              onChange={(e) =>
                                patchSplit(line.localKey, { intermediadorName: e.target.value })
                              }
                            />
                            <Input
                              className="w-28"
                              value={s.intermediador}
                              disabled={!canEdit || locked}
                              placeholder="0,00"
                              inputMode="decimal"
                              onChange={(e) => patchSplit(line.localKey, { intermediador: e.target.value })}
                            />
                          </div>
                        </div>
                      </div>
                      <p
                        className={cn(
                          'text-xs tabular-nums',
                          check?.ok ? 'text-muted-foreground' : 'text-destructive',
                        )}
                      >
                        Linha {money(line.total)} · partes {money(check?.sum ?? 0)}
                        {check && !check.ok ? ` · diferença ${money(check.delta)}` : ''}
                      </p>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
          {canEdit ? (
            <Button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving || suggesting || !allBalanced}
            >
              {saving ? 'Salvando…' : 'Aplicar'}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
