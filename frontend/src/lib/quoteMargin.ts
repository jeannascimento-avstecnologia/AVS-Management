import type { QuoteMarginKind, VhsysCatalogItem } from '@/api/client'

const LICENSE_NEEDLES = ['licen', 'm365', 'microsoft 365', 'backup'] as const

export function inferMarginKindFromCatalog(
  item: Pick<VhsysCatalogItem, 'kind' | 'name'> & { tipo_produto?: string | null },
): QuoteMarginKind | null {
  const tipoRaw = (item.tipo_produto ?? '').trim()
  const tipo =
    tipoRaw ||
    (item.kind === 'servico' ? 'Servico' : item.kind === 'produto' ? 'Produto' : '')
  const folded = tipo.toLocaleLowerCase('pt-BR')
  if (folded === 'servico' || folded === 'serviço' || folded === 'service') {
    return 'implantacao'
  }
  if (folded === 'produto' || folded === 'product') {
    const needle = item.name.toLowerCase()
    if (LICENSE_NEEDLES.some((t) => needle.includes(t))) return 'licenca'
    return 'produto'
  }
  return null
}
