import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import type { QuoteMonthlyChargeWrite, QuoteMonthlyDraftWrite } from '@/api/client'
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

type ChargeDraft = {
  key: string
  name: string
  amount: string
}

function money(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function round2(n: number): number {
  return Math.round(n * 100) / 100
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
  const [charges, setCharges] = useState<ChargeDraft[]>([])

  useEffect(() => {
    if (!open) return
    const nextCharges =
      initialDraft?.charges?.length
        ? initialDraft.charges.map((c, i) => ({
            key: `c-${i}`,
            name: c.name,
            amount: String(c.amount),
          }))
        : [
            { key: 'c-0', name: 'Fornecedor', amount: '' },
            { key: 'c-1', name: 'Intermediador', amount: '' },
          ]
    setCharges(nextCharges)
    const selectedKeys = new Set<string>()
    const ids = new Set(initialDraft?.license_item_ids ?? [])
    if (ids.size) {
      for (const line of lines) {
        if (line.itemId != null && ids.has(line.itemId)) selectedKeys.add(line.localKey)
      }
    }
    setSelected(selectedKeys)
  }, [open, initialDraft, lines])

  const licenseTotal = useMemo(
    () => round2(lines.filter((l) => selected.has(l.localKey)).reduce((s, l) => s + l.total, 0)),
    [lines, selected],
  )

  const chargesTotal = useMemo(
    () => round2(charges.reduce((s, c) => s + (Number.parseFloat(c.amount.replace(',', '.')) || 0), 0)),
    [charges],
  )

  const delta = round2(licenseTotal - chargesTotal)
  const balanced = selected.size === 0 ? charges.every((c) => !c.amount.trim()) : Math.abs(delta) <= 0.01

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  async function handleSave() {
    if (!canEdit) return
    const selectedLines = lines.filter((l) => selected.has(l.localKey))
    const parsed: QuoteMonthlyChargeWrite[] = charges
      .map((c, i) => ({
        name: c.name.trim(),
        amount: Number.parseFloat(c.amount.replace(',', '.')) || 0,
        sort_order: i,
      }))
      .filter((c) => c.name.length > 0)

    if (selectedLines.length === 0) {
      await onSave({ license_item_ids: [], charges: [] }, [])
      return
    }
    if (parsed.length === 0) {
      toast.error('Inclua ao menos uma mensalidade (ex.: fornecedor).')
      return
    }
    if (Math.abs(delta) > 0.01) {
      toast.error(
        `Soma das mensalidades (${money(chargesTotal)}) deve ser igual ao total das linhas (${money(licenseTotal)}).`,
      )
      return
    }
    const ids = selectedLines
      .map((l) => l.itemId)
      .filter((id): id is number => id != null)
    await onSave(
      {
        license_item_ids: ids,
        charges: parsed,
      },
      selectedLines.map((l) => l.localKey),
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Mensalidades</DialogTitle>
          <DialogDescription>
            Selecione linhas de qualquer bloco. A soma das cobranças deve bater com o total das linhas.
            As linhas continuam no bloco original e também entram na seção Mensalidades do PDF (fora do total).
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="max-h-56 space-y-2 overflow-y-auto rounded-lg border border-aurora-border p-2">
            {lines.length === 0 ? (
              <p className="px-2 py-3 text-sm text-muted-foreground">Nenhuma linha no canvas.</p>
            ) : (
              lines.map((line) => (
                <label
                  key={line.localKey}
                  className="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-aurora-surface-2/60"
                >
                  <Checkbox
                    checked={selected.has(line.localKey)}
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

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Cobranças</Label>
              {canEdit ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    setCharges((prev) => [...prev, { key: `c-${Date.now()}`, name: '', amount: '' }])
                  }
                >
                  <Plus className="h-4 w-4" />
                  Mensalidade
                </Button>
              ) : null}
            </div>
            {charges.map((c) => (
              <div key={c.key} className="flex gap-2">
                <Input
                  value={c.name}
                  disabled={!canEdit}
                  placeholder="Fornecedor / Intermediador"
                  onChange={(e) =>
                    setCharges((prev) =>
                      prev.map((x) => (x.key === c.key ? { ...x, name: e.target.value } : x)),
                    )
                  }
                />
                <Input
                  className="w-36"
                  value={c.amount}
                  disabled={!canEdit}
                  placeholder="0,00"
                  inputMode="decimal"
                  onChange={(e) =>
                    setCharges((prev) =>
                      prev.map((x) => (x.key === c.key ? { ...x, amount: e.target.value } : x)),
                    )
                  }
                />
                {canEdit ? (
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    aria-label="Remover cobrança"
                    onClick={() => setCharges((prev) => prev.filter((x) => x.key !== c.key))}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                ) : null}
              </div>
            ))}
          </div>

          <p className={cn('text-sm tabular-nums', balanced ? 'text-muted-foreground' : 'text-destructive')}>
            Linhas {money(licenseTotal)} · Mensalidades {money(chargesTotal)}
            {selected.size > 0 && !balanced ? ` · diferença ${money(delta)}` : ''}
          </p>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
          {canEdit ? (
            <Button type="button" onClick={() => void handleSave()} disabled={saving}>
              {saving ? 'Salvando…' : 'Aplicar'}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
