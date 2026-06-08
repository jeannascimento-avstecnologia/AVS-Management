import { cn } from '../../lib/cn'

export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="mb-6 flex flex-wrap gap-2">
      {steps.map((label, i) => (
        <div
          key={label}
          className={cn(
            'rounded-full px-3 py-1 text-xs font-semibold',
            i + 1 === current ? 'bg-gradient-to-r from-brand-600 to-accent-600 text-white' : 'bg-white text-slate-500 border border-slate-200',
          )}
        >
          {i + 1}. {label}
        </div>
      ))}
    </div>
  )
}
