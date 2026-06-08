import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import { ArrowRight } from 'lucide-react'
import { cn } from '../../lib/cn'

type Props = {
  to: string
  title: string
  desc: string
  icon: LucideIcon
  color: string
  glow: string
  delay?: number
}

export function ActionCard({ to, title, desc, icon: Icon, color, glow, delay = 0 }: Props) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay }}>
      <Link to={to} className="block h-full">
        <motion.div
          whileHover={{ y: -4 }}
          className={cn(
            'group relative h-full overflow-hidden rounded-2xl border border-white/70 bg-white/75 p-5 shadow-sm backdrop-blur-md transition-all duration-300',
            'hover:border-transparent hover:shadow-xl',
          )}
          style={{
            ['--card-glow' as string]: glow,
          }}
        >
          <div
            className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
            style={{
              boxShadow: `inset 0 0 0 2px var(--card-glow), 0 0 24px -4px var(--card-glow), 0 8px 32px -8px rgba(12, 30, 58, 0.15)`,
            }}
          />
          <div className={`relative mb-4 inline-flex rounded-xl bg-gradient-to-r ${color} p-3 text-white shadow-md`}>
            <Icon className="h-5 w-5" />
          </div>
          <h2 className="font-display relative mb-1 text-lg font-semibold text-avs-navy">{title}</h2>
          <p className="relative mb-4 text-sm text-slate-600">{desc}</p>
          <span className="relative inline-flex items-center gap-1 text-sm font-semibold text-avs-accent transition-all group-hover:gap-2">
            Acessar <ArrowRight className="h-4 w-4" />
          </span>
        </motion.div>
      </Link>
    </motion.div>
  )
}
