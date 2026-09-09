import { motion } from 'framer-motion'
import { Check } from 'lucide-react'
import { cn } from '@/lib/cn'

type Props = {
  steps: string[]
  current: number
  className?: string
  accent?: 'blue' | 'green' | 'default'
  /** 0–1 fill for the bar after step i (only while that step is current). Done steps always 100%. */
  segmentFills?: number[]
}

export function WizardStepper({
  steps,
  current,
  className,
  accent = 'default',
  segmentFills,
}: Props) {
  const doneCircle =
    accent === 'blue'
      ? 'border-aurora-accent bg-aurora-accent text-white'
      : accent === 'green'
        ? 'border-aurora-green bg-aurora-green text-white'
        : 'border-primary bg-primary text-primary-foreground'
  const activeCircle =
    accent === 'blue'
      ? 'border-aurora-accent bg-background text-aurora-accent'
      : accent === 'green'
        ? 'border-aurora-green bg-background text-aurora-green'
        : 'border-primary bg-background text-primary'
  const barColor =
    accent === 'blue' ? 'bg-aurora-accent' : accent === 'green' ? 'bg-aurora-green' : 'bg-primary'

  return (
    <nav aria-label="Progresso" className={cn('mb-8', className)}>
      <ol className="flex w-full items-center">
        {steps.map((label, i) => {
          const step = i + 1
          const done = step < current
          const active = step === current
          const isLast = i === steps.length - 1
          const rawFill = done ? 1 : active ? (segmentFills?.[i] ?? 0) : 0
          const fill = Math.min(1, Math.max(0, rawFill))

          return (
            <li
              key={label}
              className={cn('flex min-w-0 items-center', !isLast && 'flex-1')}
            >
              <div className="flex shrink-0 items-center gap-2">
                <div
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors',
                    done && doneCircle,
                    active && activeCircle,
                    !done && !active && 'border-border text-muted-foreground',
                  )}
                >
                  {done ? <Check className="h-4 w-4" /> : step}
                </div>
                <span
                  className={cn(
                    'text-xs font-medium sm:text-sm',
                    active ? 'text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {label}
                </span>
              </div>
              {!isLast && (
                <div
                  className="relative mx-3 h-0.5 min-w-6 flex-1 overflow-hidden rounded-full bg-border"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(fill * 100)}
                  aria-label={`Progresso ${label}`}
                >
                  <motion.div
                    className={cn('absolute inset-y-0 left-0 rounded-full', barColor)}
                    initial={false}
                    animate={{ width: `${fill * 100}%` }}
                    transition={{ duration: 0.25 }}
                  />
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
