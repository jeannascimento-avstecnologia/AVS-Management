/** Primeiro segmento de rota = grupo do menu (lista). */
const GROUP_HOMES = new Set([
  'orcamentos',
  'faturamento',
  'documentos',
  'cadastrar',
  'inativar',
  'consultar',
  'empresas-inativas',
  'usuarios',
  'perfil',
])

export function groupHomePath(pathname: string): string {
  const seg = pathname.split('/').filter(Boolean)[0]
  if (seg && GROUP_HOMES.has(seg)) {
    return `/${seg}`
  }
  return '/'
}
