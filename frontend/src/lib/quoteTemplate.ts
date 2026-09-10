/** CNPJ checksum-válido só para rascunho de modelo sem cliente. */
export const QUOTE_TEMPLATE_PLACEHOLDER_CNPJ = '00000000000191'
export const QUOTE_TEMPLATE_PLACEHOLDER_NAME = 'Modelo de orçamento'

export function isQuoteTemplatePlaceholderCnpj(
  cnpj: string | null | undefined,
): boolean {
  return String(cnpj ?? '').replace(/\D/g, '') === QUOTE_TEMPLATE_PLACEHOLDER_CNPJ
}
