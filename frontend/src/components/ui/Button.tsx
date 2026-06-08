import { motion } from 'framer-motion'
import { cn } from '../../lib/cn'

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
}

const variants = {
  primary: 'bg-gradient-to-r from-avs-blue to-avs-accent text-white shadow-md hover:shadow-lg hover:from-avs-navy hover:to-avs-blue',
  secondary: 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50',
  ghost: 'bg-transparent text-slate-600 hover:bg-slate-100',
  danger: 'bg-red-600 text-white hover:bg-red-700',
}

export function Button({ className, variant = 'primary', children, disabled, ...props }: Props) {
  return (
    <motion.button
      type="button"
      disabled={disabled}
      whileHover={{ scale: disabled ? 1 : 1.02 }}
      whileTap={{ scale: disabled ? 1 : 0.98 }}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:opacity-50',
        variants[variant],
        className,
      )}
      {...(props as object)}
    >
      {children}
    </motion.button>
  )
}
