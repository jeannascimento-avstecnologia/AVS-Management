import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { VhsysCatalogCategory } from '@/api/client'

const NONE = '__none__'

type Props = {
  categories: VhsysCatalogCategory[]
  categoryId: number | null
  subcategoryId: number | null
  onCategoryId: (id: number | null) => void
  onSubcategoryId: (id: number | null) => void
  disabled?: boolean
  loading?: boolean
  error?: string | null
  categoryAriaLabel?: string
  subcategoryAriaLabel?: string
}

function parseSelectId(value: string): number | null {
  if (value === NONE) return null
  const id = Number(value)
  return Number.isFinite(id) && id > 0 ? id : null
}

export function VhsysCategoryFields({
  categories,
  categoryId,
  subcategoryId,
  onCategoryId,
  onSubcategoryId,
  disabled = false,
  loading = false,
  error = null,
  categoryAriaLabel = 'Categoria VHSYS',
  subcategoryAriaLabel = 'Subcategoria VHSYS',
}: Props) {
  const categorySelectValue = categoryId != null ? String(categoryId) : NONE
  const selected = categories.find((cat) => cat.id === categoryId) ?? null
  const subcategories = selected?.subcategories ?? []
  const validSubcategory =
    subcategoryId != null && subcategories.some((sub) => sub.id === subcategoryId)
  const subcategorySelectValue = validSubcategory ? String(subcategoryId) : NONE
  const subcategoryDisabled = disabled || loading || categoryId == null || subcategories.length === 0

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">Categoria VHSYS</Label>
        <Select
          value={categorySelectValue}
          disabled={disabled || loading}
          onValueChange={(v) => {
            onCategoryId(parseSelectId(v))
            onSubcategoryId(null)
          }}
        >
          <SelectTrigger aria-label={categoryAriaLabel}>
            <SelectValue placeholder="Todas as categorias" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>Todas as categorias</SelectItem>
            {categories.map((cat) => (
              <SelectItem key={cat.id} value={String(cat.id)}>
                {cat.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">Subcategoria VHSYS</Label>
        <Select
          value={subcategorySelectValue}
          disabled={subcategoryDisabled}
          onValueChange={(v) => onSubcategoryId(parseSelectId(v))}
        >
          <SelectTrigger aria-label={subcategoryAriaLabel}>
            <SelectValue placeholder="Todas as subcategorias" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>Todas as subcategorias</SelectItem>
            {subcategories.map((sub) => (
              <SelectItem key={sub.id} value={String(sub.id)}>
                {sub.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {error ? (
        <p className="text-[11px] text-aurora-danger sm:col-span-2">{error}</p>
      ) : (
        <p className="text-[11px] text-muted-foreground sm:col-span-2">
          Filtra a busca de itens
          {subcategoryId != null
            ? ' pela subcategoria selecionada'
            : categoryId != null
              ? ' pela categoria selecionada'
              : ''}
          {categoryId != null && subcategories.length === 0
            ? '. Esta categoria não tem subcategorias ativas.'
            : '.'}
        </p>
      )}
    </div>
  )
}
