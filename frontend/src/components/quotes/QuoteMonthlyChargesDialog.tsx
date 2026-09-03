import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import type { QuoteMonthlyAllocationWrite, QuoteMonthlyDraftWrite } from '@/api/client'
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
    intermediadorName: 'Intermediador',
    intermediador: '',
  }
}

export function QuoteMonthlyChargesDialog({
  open,
  onOpenChange,
  lines,
  canEdit,
  initialDraft,
  saving,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  lines: Line[]
  canEdit: boolean
  initialDraft: QuoteMonthlyDraftWrite | null
  saving: boolean
  onSave: (draft: QuoteMonthlyDraftWrite, selectedLocalKeys: string[]) => Promise<void>
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [splits, setSplits] = useState<Record<string, SplitDraft>>({})

  useEffect(() => {
    if (!open) return
    const nextSplits: Record<string, SplitDraft> = {}
    const selectedKeys = new Set<string>()
    const allocs = initialDraft?.allocations ?? []
    for (const a of allocs) {
      const line = lines.find((l) => l.itemId != null && l.itemId === a.item_id)
      if (!line) continue
      selectedKeys.add(line.localKey)
      nextSplits[line.localKey] = {
        fornecedorName: a.fornecedor_name || 'Fornecedor',
        fornecedor: String(a.fornecedor_amount),
        intermediadorName: a.intermediador_name || 'Intermediador',
        intermediador: String(a.intermediador_amount),
      }
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

  // #region agent log
  useEffect(() => {
    if (!open) return
    fetch('http://127.0.0.1:7624/ingest/4fbad495-1d4e-4120-8a74-d59ccbb75445', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': 'ae8776' },
      body: JSON.stringify({
        sessionId: 'ae8776',
        runId: 'post-fix',
        hypothesisId: 'A',
        location: 'QuoteMonthlyChargesDialog.tsx:totals',
        message: 'per-line split totals',
        data: {
          selectedCount: selected.size,
          model: 'per-line',
          lineChecks,
          allBalanced,
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {})
  }, [open, selected.size, lineChecks, allBalanced])
  // #endregion

  function toggle(key: string) {
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
        intermediador_name: s.intermediadorName.trim() || 'Intermediador',
        intermediador_amount: parseAmt(s.intermediador),
      }
    })
    // #region agent log
    fetch('http://127.0.0.1:7624/ingest/4fbad495-1d4e-4120-8a74-d59ccbb75445', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': 'ae8776' },
      body: JSON.stringify({
        sessionId: 'ae8776',
        runId: 'post-fix',
        hypothesisId: 'C',
        location: 'QuoteMonthlyChargesDialog.tsx:handleSave',
        message: 'payload per-line allocations',
        data: { allocations, keys: chosen.map((l) => l.localKey) },
        timestamp: Date.now(),
      }),
    }).catch(() => {})
    // #endregion
    await onSave({ allocations }, chosen.map((l) => l.localKey))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Mensalidades</DialogTitle>
          <DialogDescription>
            Selecione uma linha para ela descer à tabela. Em cada linha, Fornecedor + Intermediador deve
            somar o total daquela linha. O PDF mostra o produto e, abaixo, as duas cobranças.
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
                      disabled={!canEdit}
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
                      <div className="grid gap-2 sm:grid-cols-2">
                        <div className="space-y-1">
                          <Label className="text-xs">Fornecedor</Label>
                          <div className="flex gap-2">
                            <Input
                              value={s.fornecedorName}
                              disabled={!canEdit}
                              onChange={(e) => patchSplit(line.localKey, { fornecedorName: e.target.value })}
                            />
                            <Input
                              className="w-28"
                              value={s.fornecedor}
                              disabled={!canEdit}
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
                              disabled={!canEdit}
                              onChange={(e) =>
                                patchSplit(line.localKey, { intermediadorName: e.target.value })
                              }
                            />
                            <Input
                              className="w-28"
                              value={s.intermediador}
                              disabled={!canEdit}
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
            <Button type="button" onClick={() => void handleSave()} disabled={saving || !allBalanced}>
              {saving ? 'Salvando…' : 'Aplicar'}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
