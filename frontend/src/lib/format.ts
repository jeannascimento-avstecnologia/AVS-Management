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

export function formatCpf(value: string | undefined | null): string {
  if (!value) return '—'
  const digits = digitsOnly(String(value))
  if (digits.length !== 11) return String(value)
  return digits.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4')
}

export function maskCpfInput(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 11)
  if (!digits) return ''
  let out = digits.slice(0, 3)
  if (digits.length > 3) out += `.${digits.slice(3, 6)}`
  if (digits.length > 6) out += `.${digits.slice(6, 9)}`
  if (digits.length > 9) out += `-${digits.slice(9, 11)}`
  return out
}

function calcCheckDigit(numbers: number[], weights: number[]): number {
  const total = numbers.reduce((sum, n, i) => sum + n * (weights[i] ?? 0), 0)
  const remainder = total % 11
  return remainder < 2 ? 0 : 11 - remainder
}

export function isValidCpf(value: string): boolean {
  const digits = digitsOnly(value)
  if (digits.length !== 11 || /^(\d)\1+$/.test(digits)) return false
  const numbers = [...digits].map((c) => Number(c))
  const first = calcCheckDigit(numbers.slice(0, 9), [10, 9, 8, 7, 6, 5, 4, 3, 2])
  if (first !== numbers[9]) return false
  const second = calcCheckDigit(numbers.slice(0, 10), [11, 10, 9, 8, 7, 6, 5, 4, 3, 2])
  return second === numbers[10]
}

export function isValidCnpj(value: string): boolean {
  const digits = digitsOnly(value)
  if (digits.length !== 14 || /^(\d)\1+$/.test(digits)) return false
  const numbers = [...digits].map((c) => Number(c))
  const first = calcCheckDigit(numbers.slice(0, 12), [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
  if (first !== numbers[12]) return false
  const second = calcCheckDigit(numbers.slice(0, 13), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
  return second === numbers[13]
}

export function isClientDocument(value: string): boolean {
  const digits = digitsOnly(value)
  if (digits.length === 11) return isValidCpf(digits)
  if (digits.length === 14) return isValidCnpj(digits)
  return false
}

export function formatClientDocument(value: string | undefined | null): string {
  const digits = digitsOnly(value || '')
  if (digits.length === 11) return formatCpf(digits)
  if (digits.length === 14) return formatCnpj(value)
  if (!value) return '—'
  return String(value)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('pt-BR')
}
