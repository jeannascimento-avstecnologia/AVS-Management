import { useEffect } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Bug, Loader2 } from 'lucide-react'
import { DebugReportFormSchema, type DebugReportFormValues, type SessionLogEvent } from './schemas'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

interface DebugReportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  screenshotDataUrl: string | null
  sessionLog: SessionLogEvent[]
  isSubmitting: boolean
  onSubmit: (values: DebugReportFormValues) => void
}

function shortcutLabel(): string {
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
  return isMac ? '⌘⇧D' : 'Ctrl+Shift+D'
}

export function DebugReportDialog({
  open,
  onOpenChange,
  screenshotDataUrl,
  sessionLog,
  isSubmitting,
  onSubmit,
}: DebugReportDialogProps) {
  const form = useForm<DebugReportFormValues>({
    resolver: zodResolver(DebugReportFormSchema),
    defaultValues: { title: '', description: '', notes: '' },
  })

  useEffect(() => {
    if (!open) {
      form.reset({ title: '', description: '', notes: '' })
    }
  }, [form, open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[720px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Bug className="h-5 w-5 text-aurora-brand-red" />
            Reportar problema
          </DialogTitle>
          <DialogDescription>
            Captura e contexto coletados automaticamente. Atalho: {shortcutLabel()}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_220px]">
          <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} id="debug-report-form">
            <div className="space-y-2">
              <Label htmlFor="debug-report-title">Título</Label>
              <Input id="debug-report-title" placeholder="Resumo do problema" {...form.register('title')} />
              {form.formState.errors.title ? (
                <p className="text-xs text-aurora-danger">{form.formState.errors.title.message}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="debug-report-description">Descrição</Label>
              <Textarea
                id="debug-report-description"
                placeholder="O que aconteceu? O que você esperava?"
                className="min-h-[100px]"
                {...form.register('description')}
              />
              {form.formState.errors.description ? (
                <p className="text-xs text-aurora-danger">{form.formState.errors.description.message}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="debug-report-notes">Observações</Label>
              <Textarea
                id="debug-report-notes"
                placeholder="Passos para reproduzir, contexto extra (opcional)"
                className="min-h-[80px]"
                {...form.register('notes')}
              />
              {form.formState.errors.notes ? (
                <p className="text-xs text-aurora-danger">{form.formState.errors.notes.message}</p>
              ) : null}
            </div>
          </form>

          <div className="space-y-3">
            <div className="overflow-hidden rounded-lg border border-aurora-border bg-aurora-surface-2">
              {screenshotDataUrl ? (
                <img
                  src={screenshotDataUrl}
                  alt="Captura da tela"
                  className="aspect-video w-full object-contain"
                />
              ) : (
                <div className="flex aspect-video items-center justify-center text-sm text-aurora-muted">
                  Sem captura
                </div>
              )}
            </div>
            <p className="text-xs text-aurora-muted">Captura automática ao abrir</p>

            <Accordion type="single" collapsible>
              <AccordionItem value="logs" className="border-aurora-border">
                <AccordionTrigger className="rounded-md border border-aurora-border px-3 py-2 text-left text-sm hover:no-underline hover:bg-aurora-accent-muted/40">
                  Registro: {sessionLog.length} eventos
                </AccordionTrigger>
                <AccordionContent>
                  <pre className="mt-2 max-h-32 overflow-auto rounded-md border border-aurora-border bg-aurora-surface-2 p-2 text-[11px] leading-relaxed text-aurora-muted">
                    {sessionLog.length > 0
                      ? sessionLog.map((event) => `[${event.ts}] ${event.type}: ${event.message}`).join('\n')
                      : 'Nenhum evento registrado nesta sessão.'}
                  </pre>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            Cancelar
          </Button>
          <Button type="submit" form="debug-report-form" disabled={isSubmitting || !screenshotDataUrl}>
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Enviando...
              </>
            ) : (
              'Enviar relatório'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
