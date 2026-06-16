import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import { ArrowRight } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/cn'

type Props = {
  to: string
  title: string
  desc: string
  icon: LucideIcon
  accent?: 'navy' | 'red'
  delay?: number
}

export function ActionCard({ to, title, desc, icon: Icon, accent = 'navy', delay = 0 }: Props) {
  const iconColor = accent === 'red' ? 'text-brand-red' : 'text-primary'
  const bannerClass = accent === 'red' ? 'bg-brand-red/15 text-brand-red' : 'bg-primary/15 text-primary'

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.25 }}
    >
      <Link to={to} className="block h-full group">
        <Card className="relative h-full overflow-hidden border-border/80 transition-all duration-200 hover:-translate-y-1 hover:shadow-md">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-brand-red/5 opacity-0 transition-opacity group-hover:opacity-100" />
          <CardContent className="flex h-full flex-col p-6">
            <div
              className={cn(
                'mb-4 inline-flex items-center gap-2 rounded-lg px-3 py-2',
                bannerClass,
              )}
            >
              <Icon className={cn('h-5 w-5', iconColor)} />
              <h2 className="text-sm font-semibold uppercase tracking-wide">{title}</h2>
            </div>
            <p className="mb-6 flex-1 text-sm leading-relaxed text-muted-foreground">{desc}</p>
            <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary transition-colors group-hover:text-brand-red">
              Acessar
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </span>
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  )
}
