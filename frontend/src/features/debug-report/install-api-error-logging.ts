import { recordApiError } from './session-log-collector'

function isSameOriginUrl(url: string): boolean {
  if (url.startsWith('/')) return true
  try {
    return new URL(url, window.location.origin).origin === window.location.origin
  } catch {
    return false
  }
}

export function installApiErrorLogging(): () => void {
  const originalFetch = window.fetch.bind(window)

  window.fetch = async (input, init) => {
    const response = await originalFetch(input, init)
    const url = typeof input === 'string' ? input : input instanceof Request ? input.url : input.toString()

    if (!response.ok && isSameOriginUrl(url) && !url.includes('/debug-reports')) {
      let safeUrl = url
      try {
        const parsed = new URL(url, window.location.origin)
        for (const key of [...parsed.searchParams.keys()]) {
          if (/token|secret|password|key|auth/i.test(key)) {
            parsed.searchParams.set(key, '[REDACTED]')
          }
        }
        safeUrl = `${parsed.pathname}${parsed.search}`
      } catch {
        safeUrl = url.split('?')[0] ?? url
      }
      recordApiError(`${response.status} ${response.statusText}`, {
        url: safeUrl,
        status: response.status,
        method: init?.method ?? 'GET',
      })
    }

    return response
  }

  return () => {
    window.fetch = originalFetch
  }
}
