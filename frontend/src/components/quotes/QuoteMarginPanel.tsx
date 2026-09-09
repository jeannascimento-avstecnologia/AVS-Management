import { Loader2, Lock, Repeat, Wallet } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/cn'
import { btnSecondaryClass, inputClass, quoteInsetClass } from '@/lib/ui-classes'
import type {
  QuoteMarginKind,
  QuoteMarginRead,
  QuoteModule,
} from '@/api/client'

function money(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export type MarginDraftItem = {
  localKey: string
  itemId: number | null
  section: string
  name: string
  qty: string
  unit_value: string
  unit_cost: number | null
  margin_kind: QuoteMarginKind | null
}

export type MarginDraftModule = {
  id: string
  title: string
  legacy_kind: QuoteModule['legacy_kind']
  internal_labor_hours: string
  internal_hourly_cost: string
}

const KIND_LABEL: Record<QuoteMarginKind, string> = {
  implantacao: 'Implantação',
  licenca: 'Licença',
  produto: 'Produto',
}

type Props = {
  margin: QuoteMarginRead | null
  loading: boolean
  canEdit: boolean
  modules: MarginDraftModule[]
  items: MarginDraftItem[]
  refreshing: boolean
  onRefreshCosts: () => void
  onPatchModule: (id: string, patch: Partial<MarginDraftModule>) => void
  onPatchItem: (localKey: string, patch: Partial<MarginDraftItem>) => void
}

export function QuoteMarginPanel({
  margin,
  loading,
  canEdit,
  modules,
  items,
  refreshing,
  onRefreshCosts,
  onPatchModule,
  onPatchItem,
}: Props) {
  const revenue = margin?.oneshot.revenue ?? 0
  const costTotal = (margin?.oneshot.cogs ?? 0) + (margin?.oneshot.labor_cost ?? 0)
  const profit = margin?.oneshot.profit ?? 0
  const hours = margin?.oneshot.hours ?? 0
  const profitClass = profit < 0 ? 'text-aurora-danger' : 'text-aurora-green'
  const defaultRate = margin?.default_analyst_hourly_cost ?? 0

  return (
    <div className="space-y-4">
      <Card className="border-l-4 border-l-aurora-green">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center gap-2">
            <Wallet className="h-4 w-4 text-aurora-green" aria-hidden />
            <CardTitle className="text-base">Custo vs lucro</CardTitle>
            <Badge variant="outline" className="text-muted-foreground">
              Passo 3
            </Badge>
            <Badge
              variant="outline"
              className="border-aurora-amber/40 bg-aurora-amber-muted text-aurora-amber"
            >
              <Lock className="mr-1 h-3 w-3" />
              Não aparece no PDF
            </Badge>
            <Button
              type="button"
              size="sm"
              className={cn(btnSecondaryClass, 'ml-auto')}
              disabled={!canEdit || refreshing}
              onClick={onRefreshCosts}
              aria-busy={refreshing}
            >
              {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Atualizar custos VHSYS
            </Button>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Por módulo. Envio e PDF continuam no passo Revisão.
          </p>
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {loading && !margin ? (
          <p className="text-sm text-muted-foreground sm:col-span-full">Carregando margem…</p>
        ) : (
          <>
            <Kpi label="Receita" value={money(revenue)} />
            <Kpi label="Custo" value={money(costTotal)} hint="COGS + horas" />
            <Kpi
              label="Lucro"
              value={money(profit)}
              valueClass={profitClass}
            />
            <Kpi
              label="Horas"
              value={hours.toLocaleString('pt-BR')}
              hint={margin?.incomplete ? 'Custos VHSYS incompletos' : undefined}
            />
          </>
        )}
      </div>

      {modules.map((mod) => {
        const stats = margin?.modules.find((m) => m.id === mod.id)
        const modItems = items.filter((i) => i.section === mod.id)
        const showLabor =
          stats?.show_implant_labor ||
          mod.legacy_kind === 'implantacao' ||
          modItems.some((i) => i.margin_kind === 'implantacao')
        const isImplant = mod.legacy_kind === 'implantacao' || mod.id === 'implantacao'
        const isMonthly = mod.legacy_kind === 'mensalidade' || mod.id === 'mensalidade'
        return (
          <Card
            key={mod.id}
            className={cn(
              'border-l-4',
              isImplant
                ? 'border-l-aurora-accent'
                : isMonthly
                  ? 'border-l-aurora-brand-red'
                  : 'border-l-aurora-info',
            )}
          >
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-base">{mod.title}</CardTitle>
                <Badge variant="secondary">{modItems.length} item(ns)</Badge>
              </div>
              {stats ? (
                <p className="mt-1 text-xs text-muted-foreground tabular-nums">
                  Receita {money(stats.revenue)} · Custo {money(stats.cogs + stats.labor_cost)} ·
                  Lucro {money(stats.profit)}
                </p>
              ) : null}
            </CardHeader>
            <CardContent className="space-y-3">
              {showLabor ? (
                <div className={cn(quoteInsetClass)}>
                  <p className="text-sm font-medium">Implantação — horas do analista</p>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor={`mh-${mod.id}`}>Horas</Label>
                      <Input
                        id={`mh-${mod.id}`}
                        inputMode="decimal"
                        disabled={!canEdit}
                        value={mod.internal_labor_hours}
                        placeholder="0"
                        className={inputClass}
                        onChange={(e) =>
                          onPatchModule(mod.id, { internal_labor_hours: e.target.value })
                        }
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor={`mr-${mod.id}`}>R$/h analista (custo)</Label>
                      <Input
                        id={`mr-${mod.id}`}
                        inputMode="decimal"
                        disabled={!canEdit}
                        value={mod.internal_hourly_cost}
                        placeholder={String(defaultRate)}
                        className={inputClass}
                        onChange={(e) =>
                          onPatchModule(mod.id, { internal_hourly_cost: e.target.value })
                        }
                      />
                      <p className="text-[11px] text-muted-foreground">
                        Vazio usa o padrão ({money(defaultRate)}). Zero gravado não cai no padrão.
                      </p>
                    </div>
                  </div>
                </div>
              ) : null}

              {modItems.length === 0 ? (
                <p className="rounded-lg border border-dashed border-aurora-border px-3 py-4 text-sm text-muted-foreground">
                  Sem itens neste módulo.
                </p>
              ) : (
                <ul className="space-y-2">
                  {modItems.map((item) => (
                    <li
                      key={item.localKey}
                      className="space-y-2 rounded-lg border border-border bg-muted/30 px-3 py-2"
                    >
                      <div className="flex justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            {item.name.trim() || '(sem nome)'}
                          </p>
                          <p className="text-[11px] text-muted-foreground">Qtd {item.qty || '—'}</p>
                        </div>
                        {item.margin_kind ? (
                          <Badge variant="outline">{KIND_LABEL[item.margin_kind]}</Badge>
                        ) : null}
                      </div>

                      {!item.margin_kind ? (
                        <div className="flex flex-wrap gap-1.5">
                          {(['implantacao', 'licenca', 'produto'] as const).map((kind) => (
                            <Button
                              key={kind}
                              type="button"
                              size="sm"
                              className={btnSecondaryClass}
                              disabled={!canEdit}
                              onClick={() => onPatchItem(item.localKey, { margin_kind: kind })}
                            >
                              {KIND_LABEL[kind]}
                            </Button>
                          ))}
                        </div>
                      ) : null}

                      {item.margin_kind === 'produto' || item.margin_kind === 'licenca' ? (
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                          <div className="space-y-1">
                            <Label className="text-xs text-muted-foreground">Custo</Label>
                            <Input
                              inputMode="decimal"
                              disabled={!canEdit}
                              className={inputClass}
                              value={item.unit_cost != null ? String(item.unit_cost) : ''}
                              placeholder="VHSYS"
                              onChange={(e) => {
                                const raw = e.target.value.trim()
                                onPatchItem(item.localKey, {
                                  unit_cost: raw === '' ? null : Number(raw.replace(',', '.')) || 0,
                                })
                              }}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs text-muted-foreground">Venda</Label>
                            <Input
                              inputMode="decimal"
                              disabled={!canEdit}
                              className={inputClass}
                              value={item.unit_value}
                              onChange={(e) =>
                                onPatchItem(item.localKey, { unit_value: e.target.value })
                              }
                            />
                          </div>
                        </div>
                      ) : null}

                      {item.margin_kind && canEdit ? (
                        <button
                          type="button"
                          className="text-[11px] text-muted-foreground underline"
                          onClick={() => onPatchItem(item.localKey, { margin_kind: null })}
                        >
                          Trocar tipo
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        )
      })}

      <Card className="border-l-4 border-l-aurora-brand-red">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center gap-2">
            <Repeat className="h-4 w-4 text-aurora-brand-red" aria-hidden />
            <CardTitle className="text-base">Recorrente (mensalidades)</CardTitle>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Split já definido no passo Revisão → Mensalidades. Não edite aqui.
          </p>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className={quoteInsetClass}>
            <p className="text-xs text-muted-foreground">Receita</p>
            <p className="text-sm font-semibold tabular-nums">
              {money(margin?.recurring.revenue ?? 0)}
            </p>
          </div>
          <div className={quoteInsetClass}>
            <p className="text-xs text-muted-foreground">Fornecedor</p>
            <p className="text-sm font-semibold tabular-nums">
              {money(margin?.recurring.fornecedor ?? 0)}
            </p>
          </div>
          <div className={quoteInsetClass}>
            <p className="text-xs text-muted-foreground">Intermediador AVS</p>
            <p className="text-sm font-semibold tabular-nums">
              {money(margin?.recurring.intermediador ?? 0)}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function Kpi({
  label,
  value,
  hint,
  valueClass,
}: {
  label: string
  value: string
  hint?: string
  valueClass?: string
}) {
  return (
    <div className={quoteInsetClass}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn('text-sm font-semibold tabular-nums', valueClass)}>{value}</p>
      {hint ? <p className="text-[11px] text-muted-foreground">{hint}</p> : null}
    </div>
  )
}
