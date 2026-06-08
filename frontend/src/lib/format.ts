export function formatCnpj(value: string | undefined | null): string {
  if (!value) return '—'
  const digits = String(value).replace(/\D/g, '')
  if (digits.length !== 14) return String(value)
  return digits.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5')
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('pt-BR')
}
