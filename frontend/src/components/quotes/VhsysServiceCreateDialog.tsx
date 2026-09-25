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

const serviceSchema = z.object({
  name: z.string().trim().min(1, 'Informe o nome.'),
  unitValue: z.number().finite().min(0, 'Informe o valor.'),
  costValue: z.number().finite().min(0, 'Informe o valor de custo.'),
  unit: z.string().trim().min(1, 'Informe a unidade.'),
  categoryId: z.number().int().positive('Selecione a categoria.'),
  subcategoryId: z.number().int().positive('Selecione a subcategoria.'),
  note: z.string().trim(),
  status: z.enum(['Ativo', 'Inativo']).optional(),
})

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
  const [name, setName] = useState('')
  const [unitValue, setUnitValue] = useState('')
  const [costValue, setCostValue] = useState('')
  const [unit, setUnit] = useState('UN')
  const [categoryId, setCategoryId] = useState('')
  const [subcategoryId, setSubcategoryId] = useState('')
  const [note, setNote] = useState('')
  const [status, setStatus] = useState<'' | 'Ativo' | 'Inativo'>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setName('')
    setUnitValue('')
    setCostValue('')
    setUnit('UN')
    setCategoryId('')
    setSubcategoryId('')
    setNote('')
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
      tipo_produto: 'Servico'
      observacao?: string
      status_produto?: 'Ativo' | 'Inativo'
    }) => api.createVhsysCatalogItem(body),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ['vhsys-catalog-all'] })
      onCreated(data.item)
      onOpenChange(false)
      toast.success(
        data.created
          ? 'Serviço cadastrado no VHSYS e incluído no orçamento.'
          : 'Serviço já existia no VHSYS — incluído no orçamento.',
      )
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : 'Falha ao cadastrar serviço.'
      setError(message)
      toast.error(message)
    },
  })

  function submit() {
    const parsed = serviceSchema.safeParse({
      name,
      unitValue: parseMoney(unitValue),
      costValue: parseMoney(costValue),
      unit,
      categoryId: Number(categoryId),
      subcategoryId: Number(subcategoryId),
      note,
      status: status || undefined,
    })
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
      tipo_produto: 'Servico',
      unidade_produto: data.unit,
      id_categoria: data.categoryId,
      id_subcategoria: data.subcategoryId,
      ...(data.note ? { observacao: data.note } : {}),
      ...(data.status ? { status_produto: data.status } : {}),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Novo serviço</DialogTitle>
          <DialogDescription>Cadastra no VHSYS e inclui uma linha neste bloco.</DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="vhsys-service-name">Nome</Label>
            <Input id="vhsys-service-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <Label htmlFor="vhsys-service-value">Valor</Label>
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
          <div className="space-y-1">
            <Label htmlFor="vhsys-service-note">Observação</Label>
            <Input id="vhsys-service-note" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
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
              Salvar serviço
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
