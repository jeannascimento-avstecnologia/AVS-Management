import { Monitor, Moon, Sun } from 'lucide-react'
import { motion } from 'framer-motion'
import { useTheme } from '@/contexts/ThemeProvider'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/cn'

const labels = {
  light: 'Tema claro',
  dark: 'Tema escuro',
  system: 'Sistema',
}

export function ThemeToggle({ className }: { className?: string }) {
  const { mode, cycleMode } = useTheme()
  const Icon = mode === 'dark' ? Moon : mode === 'light' ? Sun : Monitor

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={cycleMode}
      className={cn('h-8 w-8', className)}
      aria-label={labels[mode]}
      title={labels[mode]}
    >
      <motion.div animate={{ rotate: mode === 'dark' ? 180 : 0 }} transition={{ duration: 0.3 }}>
        <Icon className="h-4 w-4" />
      </motion.div>
    </Button>
  )
}
