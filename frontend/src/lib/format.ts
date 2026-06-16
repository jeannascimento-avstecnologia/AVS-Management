export function formatCnpj(value: string | undefined | null): string {
  if (!value) return '—'
  const digits = String(value).replace(/\D/g, '')
  if (digits.length !== 14) return String(value)
  return digits.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5')
}

/** Máscara parcial enquanto o usuário digita (até 14 dígitos). */
export function maskCnpjInput(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 14)
  if (!digits) return ''

  let out = digits.slice(0, 2)
  if (digits.length > 2) out += `.${digits.slice(2, 5)}`
  if (digits.length > 5) out += `.${digits.slice(5, 8)}`
  if (digits.length > 8) out += `/${digits.slice(8, 12)}`
  if (digits.length > 12) out += `-${digits.slice(12, 14)}`
  return out
}

/** Formata como CNPJ se só houver dígitos/pontuação; caso contrário mantém texto (busca por nome). */
export function formatQueryInput(value: string): string {
  const letters = value.replace(/[\d.\s/-]/g, '')
  if (letters.length > 0) return value
  return maskCnpjInput(value)
}

export function digitsOnly(value: string): string {
  return value.replace(/\D/g, '')
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('pt-BR')
}
