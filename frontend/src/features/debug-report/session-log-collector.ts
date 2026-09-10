import type { SessionLogEvent, SessionLogEventType } from './schemas'
import { DEBUG_REPORT_MAX_SESSION_EVENTS } from './schemas'

const SENSITIVE_INPUT_PATTERN = /password|senha|secret|token/i
const SECRET_IN_TEXT_PATTERN =
  /(authorization|bearer|access[_-]?token|refresh[_-]?token|api[_-]?key|password|senha|secret)\s*[:=]\s*["']?[^\s"',}]+/gi

function redactSecrets(value: string): string {
  return value
    .replace(/Bearer\s+[A-Za-z0-9._\-]+/gi, 'Bearer [REDACTED]')
    .replace(SECRET_IN_TEXT_PATTERN, '$1=[REDACTED]')
}

type ConsoleMethod = 'error' | 'warn'

interface SessionLogCollectorState {
  events: SessionLogEvent[]
  installed: boolean
  originalConsole: Partial<Record<ConsoleMethod, typeof console.error>>
  handlers: {
    click: (event: MouseEvent) => void
    error: (event: ErrorEvent) => void
    rejection: (event: PromiseRejectionEvent) => void
  } | null
}

const state: SessionLogCollectorState = {
  events: [],
  installed: false,
  originalConsole: {},
  handlers: null,
}

function nowIso(): string {
  return new Date().toISOString()
}

function truncate(value: string, max = 200): string {
  return value.length <= max ? value : `${value.slice(0, max)}…`
}

function pushEvent(type: SessionLogEventType, message: string, meta?: Record<string, unknown>): void {
  const safeMeta = meta
    ? Object.fromEntries(
        Object.entries(meta).map(([key, value]) => [
          key,
          typeof value === 'string' ? redactSecrets(value) : value,
        ]),
      )
    : undefined
  state.events.push({
    ts: nowIso(),
    type,
    message: truncate(redactSecrets(message), 2000),
    meta: safeMeta,
  })
  if (state.events.length > DEBUG_REPORT_MAX_SESSION_EVENTS) {
    state.events.shift()
  }
}

function formatConsoleArgs(args: unknown[]): string {
  return args
    .map((arg) => {
      if (typeof arg === 'string') return arg
      if (arg instanceof Error) return `${arg.name}: ${arg.message}`
      try {
        return JSON.stringify(arg)
      } catch {
        return String(arg)
      }
    })
    .join(' ')
}

function isSensitiveTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
    if (target.type === 'password') return true
    if (SENSITIVE_INPUT_PATTERN.test(target.name)) return true
    if (SENSITIVE_INPUT_PATTERN.test(target.id)) return true
    if (SENSITIVE_INPUT_PATTERN.test(target.autocomplete)) return true
  }
  return false
}

function describeClickTarget(target: EventTarget | null): { message: string; meta: Record<string, unknown> } {
  if (!(target instanceof Element)) {
    return { message: 'click on unknown element', meta: {} }
  }

  const element = target.closest('button, a, [role="button"], input, select, textarea, label') ?? target
  const tag = element.tagName.toLowerCase()
  const testId = element.getAttribute('data-testid')
  const id = element.id || undefined
  const text = truncate((element.textContent ?? '').replace(/\s+/g, ' ').trim(), 80) || undefined

  return {
    message: `click ${tag}${testId ? ` [data-testid=${testId}]` : ''}`,
    meta: { tag, ...(testId ? { testId } : {}), ...(id ? { id } : {}), ...(text ? { text } : {}) },
  }
}

function patchConsole(method: ConsoleMethod): void {
  const original = console[method].bind(console)
  state.originalConsole[method] = original
  console[method] = (...args: unknown[]) => {
    pushEvent(`console.${method}`, formatConsoleArgs(args))
    original(...args)
  }
}

export function installSessionLogCollector(): void {
  if (typeof window === 'undefined' || state.installed) return
  state.installed = true

  patchConsole('error')
  patchConsole('warn')

  const onClick = (event: MouseEvent) => {
    if (isSensitiveTarget(event.target)) return
    const { message, meta } = describeClickTarget(event.target)
    pushEvent('click', message, meta)
  }

  const onError = (event: ErrorEvent) => {
    pushEvent('error', event.message || 'Unknown error', {
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    })
  }

  const onRejection = (event: PromiseRejectionEvent) => {
    const reason = event.reason
    const message =
      reason instanceof Error
        ? `${reason.name}: ${reason.message}`
        : typeof reason === 'string'
          ? reason
          : 'Unhandled promise rejection'
    pushEvent('unhandledrejection', message)
  }

  state.handlers = { click: onClick, error: onError, rejection: onRejection }
  window.addEventListener('click', onClick, true)
  window.addEventListener('error', onError)
  window.addEventListener('unhandledrejection', onRejection)
}

export function uninstallSessionLogCollector(): void {
  if (!state.installed || typeof window === 'undefined') return

  const handlers = state.handlers
  if (handlers) {
    window.removeEventListener('click', handlers.click, true)
    window.removeEventListener('error', handlers.error)
    window.removeEventListener('unhandledrejection', handlers.rejection)
  }

  for (const method of ['error', 'warn'] as const) {
    const original = state.originalConsole[method]
    if (original) console[method] = original
  }

  state.handlers = null
  state.originalConsole = {}
  state.installed = false
}

export function recordNavigation(path: string): void {
  pushEvent('navigation', `navigate to ${path}`, { path })
}

export function recordApiError(message: string, meta?: Record<string, unknown>): void {
  pushEvent('api.error', message, meta)
}

export function getSessionLogSnapshot(): SessionLogEvent[] {
  return [...state.events]
}

export function clearSessionLog(): void {
  state.events = []
}

export function resetSessionLogCollectorForTests(): void {
  uninstallSessionLogCollector()
  state.events = []
}
