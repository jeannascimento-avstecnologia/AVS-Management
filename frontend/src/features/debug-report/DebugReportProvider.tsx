import {
  createContext,
  use,
  useCallback,
  useEffect,
  useMemo,
  useState,
  useTransition,
  type ReactNode,
} from 'react'
import { useLocation } from 'react-router-dom'
import { toast } from 'sonner'
import {
  getSessionLogSnapshot,
  installSessionLogCollector,
  recordNavigation,
  uninstallSessionLogCollector,
} from './session-log-collector'
import type { DebugReportApp, SessionLogEvent } from './schemas'
import { captureViewportScreenshot } from './capture-viewport'
import { installApiErrorLogging } from './install-api-error-logging'
import { submitDebugReport } from './api/submitDebugReport'
import { DebugReportDialog } from './DebugReportDialog'

interface DebugReportContextValue {
  openReport: () => void
  isPreparing: boolean
}

const DebugReportContext = createContext<DebugReportContextValue | null>(null)

export function useDebugReportTrigger(): DebugReportContextValue {
  const context = use(DebugReportContext)
  if (!context) {
    throw new Error('useDebugReportTrigger must be used within DebugReportProvider')
  }
  return context
}

interface DebugReportProviderProps {
  children: ReactNode
  app: DebugReportApp
}

export function DebugReportProvider({ children, app }: DebugReportProviderProps) {
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [isPreparing, setIsPreparing] = useState(false)
  const [isPending, startTransition] = useTransition()
  const [screenshotDataUrl, setScreenshotDataUrl] = useState<string | null>(null)
  const [sessionLog, setSessionLog] = useState<SessionLogEvent[]>([])

  useEffect(() => {
    installSessionLogCollector()
    const uninstallApiLogging = installApiErrorLogging()
    return () => {
      uninstallSessionLogCollector()
      uninstallApiLogging()
    }
  }, [])

  useEffect(() => {
    recordNavigation(pathname)
  }, [pathname])

  const openReport = useCallback(async () => {
    if (isPreparing || open) return
    setIsPreparing(true)
    try {
      const [screenshot, log] = await Promise.all([
        captureViewportScreenshot(),
        Promise.resolve(getSessionLogSnapshot()),
      ])
      setScreenshotDataUrl(screenshot)
      setSessionLog(log)
      setOpen(true)
    } catch {
      toast.error('Não foi possível capturar a tela. Tente novamente.')
    } finally {
      setIsPreparing(false)
    }
  }, [isPreparing, open])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 'd' || !event.shiftKey || !(event.metaKey || event.ctrlKey)) {
        return
      }
      event.preventDefault()
      void openReport()
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [openReport])

  const handleSubmit = useCallback(
    (values: { title: string; description: string; notes?: string }) => {
      if (!screenshotDataUrl) return

      const notes = values.notes?.trim() ? values.notes.trim() : undefined

      startTransition(async () => {
        try {
          await submitDebugReport({
            title: values.title,
            description: values.description,
            ...(notes ? { notes } : {}),
            screenshotBase64: screenshotDataUrl,
            sessionLog,
            clientMeta: {
              url: window.location.href,
              userAgent: navigator.userAgent,
              viewport: {
                width: window.innerWidth,
                height: window.innerHeight,
              },
              app,
            },
          })
          toast.success('Relatório enviado. Obrigado!')
          setOpen(false)
          setScreenshotDataUrl(null)
          setSessionLog([])
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Falha ao enviar relatório.'
          toast.error(message)
        }
      })
    },
    [app, screenshotDataUrl, sessionLog],
  )

  const value = useMemo(
    () => ({ openReport: () => void openReport(), isPreparing }),
    [isPreparing, openReport],
  )

  return (
    <DebugReportContext value={value}>
      {children}
      <DebugReportDialog
        open={open}
        onOpenChange={setOpen}
        screenshotDataUrl={screenshotDataUrl}
        sessionLog={sessionLog}
        isSubmitting={isPending}
        onSubmit={handleSubmit}
      />
    </DebugReportContext>
  )
}
