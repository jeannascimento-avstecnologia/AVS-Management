/**
 * Título do módulo ao importar um `quote_module_templates`.
 * Contrato ADR/spec: `title` (fallback `name`).
 * Heurística: save-as antigo gravava título do preset (Mensalidade/Implantação)
 * enquanto o nome no catálogo era renomeado — usa o nome visível no picker.
 */
export function moduleTitleFromTemplate(template: {
  name: string
  title: string
}): string {
  const name = template.name.trim()
  const title = template.title.trim()
  if (
    name &&
    title !== name &&
    (title === 'Mensalidade' || title === 'Implantação')
  ) {
    return name
  }
  return title || name
}
