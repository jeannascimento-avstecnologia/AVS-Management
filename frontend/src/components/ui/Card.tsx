import { motion } from 'framer-motion'
import { cn } from '../../lib/cn'

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <motion.div
      whileHover={{ y: -2 }}
      className={cn('glass rounded-2xl p-5 shadow-sm', className)}
    >
      {children}
    </motion.div>
  )
}
