import { Bug } from 'lucide-react'
import { useDebugReportTrigger } from './DebugReportProvider'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/cn'

const sidebarGhostBtnClass =
  'bg-transparent shadow-none ring-0 hover:!bg-white/10 hover:shadow-none focus-visible:!bg-transparent focus-visible:ring-0'

type Props = {
  collapsed: boolean
}

export function DebugReportSidebarButton({ collapsed }: Props) {
  const { openReport, isPreparing } = useDebugReportTrigger()
  const label = isPreparing ? 'Capturando...' : 'Reportar problema'

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => void openReport()}
            disabled={isPreparing}
            aria-label="Reportar problema"
            className={cn('w-full text-aurora-sidebar-muted hover:text-aurora-sidebar-fg', sidebarGhostBtnClass)}
          >
            <Bug className="h-4 w-4" />
            <span className="sr-only">{label}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    )
  }

  return (
    <Button
      type="button"
      variant="ghost"
      onClick={() => void openReport()}
      disabled={isPreparing}
      aria-label="Reportar problema"
      className="w-full justify-start text-aurora-sidebar-muted hover:bg-white/10 hover:text-aurora-sidebar-fg"
    >
      <Bug className="mr-2 h-4 w-4" />
      {label}
    </Button>
  )
}
