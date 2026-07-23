/**
 * ID local (chaves React / módulos draft).
 * `crypto.randomUUID` exige secure context (HTTPS ou localhost);
 * em HTTP+IP LAN (ex.: http://10.x.x.x) falha → fallback com getRandomValues (CSPRNG).
 * Não usar para tokens de sessão/auth.
 */
export function localId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = new Uint8Array(16)
    crypto.getRandomValues(bytes)
    // RFC 4122 variant 1 + version 4
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
  }
  throw new Error('Geração de ID indisponível neste browser')
}
