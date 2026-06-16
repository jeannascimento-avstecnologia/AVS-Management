import { motion } from 'framer-motion'
import { Check } from 'lucide-react'
import { cn } from '@/lib/cn'

type Props = {
  steps: string[]
  current: number
  className?: string
}

export function WizardStepper({ steps, current, className }: Props) {
  return (
    <nav aria-label="Progresso" className={cn('mb-8', className)}>
      <ol className="flex items-center gap-2">
        {steps.map((label, i) => {
          const step = i + 1
          const done = step < current
          const active = step === current
          return (
            <li key={label} className="flex flex-1 items-center gap-2 last:flex-none">
              <div className="flex min-w-0 flex-1 flex-col items-center gap-1.5 sm:flex-row sm:gap-2">
                <div
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors',
                    done && 'border-primary bg-primary text-primary-foreground',
                    active && 'border-primary bg-background text-primary',
                    !done && !active && 'border-border text-muted-foreground',
                  )}
                >
                  {done ? <Check className="h-4 w-4" /> : step}
                </div>
                <span
                  className={cn(
                    'truncate text-center text-xs font-medium sm:text-left sm:text-sm',
                    active ? 'text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {label}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div className="relative hidden h-0.5 flex-1 overflow-hidden rounded-full bg-border sm:block">
                  {done && (
                    <motion.div
                      className="absolute inset-y-0 left-0 bg-primary"
                      initial={{ width: 0 }}
                      animate={{ width: '100%' }}
                      transition={{ duration: 0.3 }}
                    />
                  )}
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
