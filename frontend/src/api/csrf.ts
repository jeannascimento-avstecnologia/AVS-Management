let csrfToken: string | null = null

const CSRF_EXEMPT = ['/auth/login', '/auth/forgot-password', '/auth/reset-password']

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

export function getCsrfToken() {
  return csrfToken
}

export function isCsrfExempt(url: string) {
  return CSRF_EXEMPT.some((path) => url === path || url.startsWith(`${path}?`))
}

export async function refreshCsrfToken(): Promise<string | null> {
  const res = await fetch('/auth/csrf', { credentials: 'include' })
  if (!res.ok) {
    csrfToken = null
    return null
  }
  const data = (await res.json()) as { csrf_token?: string | null }
  csrfToken = data.csrf_token ?? null
  return csrfToken
}
