import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function AvsBrandTexture(_props: { className?: string }) {
  return null
}

export function AvsBrandPanel({
  children,
  className,
}: {
  children?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'aurora-sidebar-pattern relative overflow-hidden text-aurora-sidebar-fg',
        className,
      )}
    >
      {children && <div className="relative z-10">{children}</div>}
    </div>
  )
}
