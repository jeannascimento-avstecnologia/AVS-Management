import { Link } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { ArrowRight } from 'lucide-react'
import { SpotlightSelectable } from '@/components/ui/SpotlightSelectable'
import { cn } from '@/lib/cn'

type Props = {
  to: string
  title: string
  desc: string
  icon: LucideIcon
  accent?: 'accent' | 'red' | 'purple'
}

export function ActionCard({ to, title, desc, icon: Icon, accent = 'accent' }: Props) {
  const iconColor =
    accent === 'red' ? 'text-aurora-brand-red' : accent === 'purple' ? 'text-aurora-purple' : 'text-aurora-accent'
  const bannerClass =
    accent === 'red'
      ? 'bg-aurora-brand-red/15 text-aurora-brand-red'
      : accent === 'purple'
        ? 'bg-aurora-purple/15 text-aurora-purple'
        : 'bg-aurora-accent-muted text-aurora-accent'

  return (
    <Link to={to} className="block h-full group hub-panel-enter">
      <SpotlightSelectable
        accent={accent}
        className="h-full shadow-sm hover:-translate-y-0.5 hover:shadow-md transition-transform"
        innerClassName="flex h-full flex-col p-6"
      >
        <div className={cn('mb-4 inline-flex items-center gap-2 rounded-lg px-3 py-2', bannerClass)}>
          <Icon className={cn('h-5 w-5', iconColor)} />
          <h2 className="text-sm font-semibold uppercase tracking-wide">{title}</h2>
        </div>
        <p className="mb-6 flex-1 text-sm leading-relaxed text-aurora-muted">{desc}</p>
        <span
          className={cn(
            'inline-flex items-center gap-1.5 text-sm font-semibold transition-colors',
            accent === 'red'
              ? 'text-aurora-brand-red'
              : accent === 'purple'
                ? 'text-aurora-purple'
                : 'text-aurora-muted group-hover:text-aurora-accent',
          )}
        >
          Acessar
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
        </span>
      </SpotlightSelectable>
    </Link>
  )
}
