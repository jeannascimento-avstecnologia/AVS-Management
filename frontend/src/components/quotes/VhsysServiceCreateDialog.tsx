import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { z } from 'zod'
import { Loader2 } from 'lucide-react'
import { api, type VhsysCatalogItem } from '@/api/client'
import { Button } from '@/components/ui/button'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { btnGreenClass, btnSecondaryClass } from '@/lib/ui-classes'

const sharedSchema = {
  name: z.string().trim().min(1, 'Informe o nome.'),
  unitValue: z.number().finite().min(0, 'Informe o valor.'),
  costValue: z.number().finite().min(0, 'Informe o valor de custo.'),
  unit: z.string().trim().min(1, 'Informe a unidade.'),
  categoryId: z.number().int().positive('Selecione a categoria.'),
  subcategoryId: z.number().int().positive('Selecione a subcategoria.'),
  status: z.enum(['Ativo', 'Inativo']).optional(),
}

const catalogSchema = z.discriminatedUnion('kind', [
  z.object({
    kind: z.literal('Servico'),
    note: z.string().trim(),
    ...sharedSchema,
  }),
  z.object({
    kind: z.literal('Produto'),
    brand: z.string().trim(),
    description: z.string().trim(),
    ...sharedSchema,
  }),
])

type CatalogKind = 'Servico' | 'Produto'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (item: VhsysCatalogItem) => void
}

function parseMoney(raw: string): number {
  return Number(raw.trim().replace(',', '.'))
}

export function VhsysServiceCreateDialog({ open, onOpenChange, onCreated }: Props) {
  const queryClient = useQueryClient()
  const [kind, setKind] = useState<CatalogKind>('Servico')
  const [name, setName] = useState('')
  const [brand, setBrand] = useState('')
  const [unitValue, setUnitValue] = useState('')
  const [costValue, setCostValue] = useState('')
  const [unit, setUnit] = useState('UN')
  const [categoryId, setCategoryId] = useState('')
  const [subcategoryId, setSubcategoryId] = useState('')
  const [note, setNote] = useState('')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState<'' | 'Ativo' | 'Inativo'>('')
  const [error, setError] = useState<string | null>(null)
  const isProduct = kind === 'Produto'

  useEffect(() => {
    if (!open) return
    setKind('Servico')
    setName('')
    setBrand('')
    setUnitValue('')
    setCostValue('')
    setUnit('UN')
    setCategoryId('')
    setSubcategoryId('')
    setNote('')
    setDescription('')
    setStatus('')
    setError(null)
  }, [open])

  const categoriesQuery = useQuery({
    queryKey: ['vhsys-categories'],
    queryFn: () => api.listVhsysCategories(),
    enabled: open,
    staleTime: 5 * 60_000,
  })
  const categories = categoriesQuery.data?.categories ?? []
  const subcategories = useMemo(() => {
    const cat = categories.find((row) => String(row.id) === categoryId)
    return cat?.subcategories ?? []
  }, [categories, categoryId])

  const createMutation = useMutation({
    mutationFn: (body: {
      name: string
      unit_value: number
      cost_value: number
      unidade_produto: string
      id_categoria: number
      id_subcategoria: number
      tipo_produto: CatalogKind
      observacao?: string
      marca?: string
      descricao?: string
      status_produto?: 'Ativo' | 'Inativo'
    }) => api.createVhsysCatalogItem(body),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ['vhsys-catalog-all'] })
      onCreated(data.item)
      onOpenChange(false)
      const label = data.item.kind === 'servico' ? 'Serviço' : 'Produto'
      toast.success(
        data.created
          ? `${label} cadastrado no VHSYS e incluído no orçamento.`
          : `${label} já existia no VHSYS — incluído no orçamento.`,
      )
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : 'Falha ao cadastrar item.'
      setError(message)
      toast.error(message)
    },
  })

  function submit() {
    const parsed = catalogSchema.safeParse(
      isProduct
        ? {
            kind,
            name,
            brand,
            description,
            unitValue: parseMoney(unitValue),
            costValue: parseMoney(costValue),
            unit,
            categoryId: Number(categoryId),
            subcategoryId: Number(subcategoryId),
            status: status || undefined,
          }
        : {
            kind,
            name,
            note,
            unitValue: parseMoney(unitValue),
            costValue: parseMoney(costValue),
            unit,
            categoryId: Number(categoryId),
            subcategoryId: Number(subcategoryId),
            status: status || undefined,
          },
    )
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Revise os campos.')
      return
    }
    setError(null)
    const data = parsed.data
    createMutation.mutate({
      name: data.name,
      unit_value: data.unitValue,
      cost_value: data.costValue,
      tipo_produto: data.kind,
      unidade_produto: data.unit,
      id_categoria: data.categoryId,
      id_subcategoria: data.subcategoryId,
      ...(data.kind === 'Servico' && data.note ? { observacao: data.note } : {}),
      ...(data.kind === 'Produto' && data.brand ? { marca: data.brand } : {}),
      ...(data.kind === 'Produto' && data.description ? { descricao: data.description } : {}),
      ...(data.status ? { status_produto: data.status } : {}),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-lg"
        onPointerDownOutside={(event) => event.preventDefault()}
        onInteractOutside={(event) => event.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>Novo item</DialogTitle>
          <DialogDescription>Cadastra no VHSYS e inclui uma linha neste bloco.</DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <div className="flex gap-2" role="group" aria-label="Tipo do item">
            <Button
              type="button"
              className={kind === 'Produto' ? btnGreenClass : btnSecondaryClass}
              onClick={() => setKind('Produto')}
            >
              Produto
            </Button>
            <Button
              type="button"
              className={kind === 'Servico' ? btnGreenClass : btnSecondaryClass}
              onClick={() => setKind('Servico')}
            >
              Serviço
            </Button>
          </div>
          <div className="space-y-1">
            <Label htmlFor="vhsys-service-name">Nome</Label>
            <Input id="vhsys-service-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          {isProduct ? (
            <div className="space-y-1">
              <Label htmlFor="vhsys-service-brand">Marca</Label>
              <Input id="vhsys-service-brand" value={brand} onChange={(e) => setBrand(e.target.value)} />
            </div>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <Label htmlFor="vhsys-service-value">{isProduct ? 'Valor de venda' : 'Valor'}</Label>
              <Input
                id="vhsys-service-value"
                inputMode="decimal"
                value={unitValue}
                onChange={(e) => setUnitValue(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="vhsys-service-cost">Valor de custo</Label>
              <Input
                id="vhsys-service-cost"
                inputMode="decimal"
                value={costValue}
                onChange={(e) => setCostValue(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="vhsys-service-unit">Unidade</Label>
              <Input id="vhsys-service-unit" value={unit} onChange={(e) => setUnit(e.target.value)} />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>Categoria</Label>
              <Select
                value={categoryId}
                onValueChange={(value) => {
                  setCategoryId(value)
                  setSubcategoryId('')
                }}
              >
                <SelectTrigger aria-label="Categoria">
                  <SelectValue placeholder="Categoria" />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((cat) => (
                    <SelectItem key={cat.id} value={String(cat.id)}>
                      {cat.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Subcategoria</Label>
              <Select value={subcategoryId} onValueChange={setSubcategoryId} disabled={!categoryId}>
                <SelectTrigger aria-label="Subcategoria">
                  <SelectValue placeholder="Subcategoria" />
                </SelectTrigger>
                <SelectContent>
                  {subcategories.map((sub) => (
                    <SelectItem key={sub.id} value={String(sub.id)}>
                      {sub.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {isProduct ? (
            <div className="space-y-1">
              <Label htmlFor="vhsys-service-description">Descrição</Label>
              <Input
                id="vhsys-service-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          ) : (
            <div className="space-y-1">
              <Label htmlFor="vhsys-service-note">Observação</Label>
              <Input id="vhsys-service-note" value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
          )}
          <div className="space-y-1">
            <Label>Situação</Label>
            <Select value={status || 'none'} onValueChange={(value) => setStatus(value === 'none' ? '' : (value as 'Ativo' | 'Inativo'))}>
              <SelectTrigger aria-label="Situação">
                <SelectValue placeholder="Não informar" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Não informar</SelectItem>
                <SelectItem value="Ativo">Ativo</SelectItem>
                <SelectItem value="Inativo">Inativo</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {error ? <p className="text-xs text-aurora-danger">{error}</p> : null}
          <DialogFooter>
            <Button
              type="button"
              className={btnSecondaryClass}
              onClick={() => onOpenChange(false)}
              disabled={createMutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" className={btnGreenClass} disabled={createMutation.isPending}>
              {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Salvar item
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
