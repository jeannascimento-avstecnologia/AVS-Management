import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const SHORTCUTS = [
  { keys: ['Ctrl', 'K'], desc: 'Abrir paleta de comandos' },
  { keys: ['Ctrl', 'Shift', 'L'], desc: 'Alternar tema' },
  { keys: ['Esc'], desc: 'Fechar modais' },
  { keys: ['?'], desc: 'Mostrar atalhos' },
]

export function KeyboardShortcuts() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === '?' && !e.metaKey && !e.ctrlKey && !(e.target instanceof HTMLInputElement)) {
        e.preventDefault()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Atalhos de teclado</DialogTitle>
        </DialogHeader>
        <ul className="space-y-3 text-sm">
          {SHORTCUTS.map((s) => (
            <li key={s.desc} className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">{s.desc}</span>
              <span className="flex gap-1">
                {s.keys.map((k) => (
                  <kbd key={k} className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-xs">
                    {k}
                  </kbd>
                ))}
              </span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  )
}
