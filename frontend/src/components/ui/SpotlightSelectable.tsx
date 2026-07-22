import {
  useRef,
  useState,
  type ComponentPropsWithoutRef,
  type ElementType,
  type MouseEvent,
  type ReactNode,
} from 'react'
import { cn } from '@/lib/cn'

export type SpotlightAccent = 'accent' | 'red' | 'purple' | 'green' | 'teal' | 'amber'

/** RGB tuples for spotlight (avoids color-mix + var() issues in gradients). */
const ACCENT_RGB: Record<SpotlightAccent, string> = {
  accent: '29, 78, 216',
  red: '220, 38, 38',
  purple: '124, 58, 237',
  green: '5, 150, 105',
  teal: '13, 148, 136',
  amber: '217, 119, 6',
}

const ACCENT_BORDER: Record<SpotlightAccent, { selected: string; hover: string }> = {
  accent: { selected: 'border-aurora-accent/50', hover: 'border-aurora-accent/40' },
  red: { selected: 'border-aurora-brand-red/50', hover: 'border-aurora-brand-red/40' },
  purple: { selected: 'border-aurora-purple/50', hover: 'border-aurora-purple/40' },
  green: { selected: 'border-aurora-green/50', hover: 'border-aurora-green/40' },
  teal: { selected: 'border-aurora-teal/50', hover: 'border-aurora-teal/40' },
  amber: { selected: 'border-aurora-amber/50', hover: 'border-aurora-amber/40' },
}

const SELECTED_BORDER: Record<SpotlightAccent, string> = {
  accent: 'border-aurora-accent/60',
  red: 'border-aurora-brand-red/60',
  purple: 'border-aurora-purple/60',
  green: 'border-aurora-green/60',
  teal: 'border-aurora-teal/60',
  amber: 'border-aurora-amber/60',
}

type Props<T extends ElementType> = {
  as?: T
  accent?: SpotlightAccent
  selected?: boolean
  variant?: 'surface' | 'sidebar'
  innerClassName?: string
  children: ReactNode
} & Omit<ComponentPropsWithoutRef<T>, 'as' | 'children'>

export function SpotlightSelectable<T extends ElementType = 'div'>({
  as,
  accent = 'accent',
  selected = false,
  variant = 'surface',
  className,
  innerClassName,
  children,
  onMouseMove,
  onMouseEnter,
  onMouseLeave,
  ...props
}: Props<T>) {
  const Component = as || 'div'
  const ref = useRef<HTMLElement>(null)
  const [hover, setHover] = useState(false)
  const [spot, setSpot] = useState({ x: 50, y: 50 })
  const rgb = ACCENT_RGB[accent]
  const borders = ACCENT_BORDER[accent]
  const showSpotlight = hover || selected
  const isSidebar = variant === 'sidebar'

  function handleMouseMove(e: MouseEvent<HTMLElement>) {
    const rect = ref.current?.getBoundingClientRect()
    if (rect) {
      setSpot({
        x: ((e.clientX - rect.left) / rect.width) * 100,
        y: ((e.clientY - rect.top) / rect.height) * 100,
      })
    }
    onMouseMove?.(e as never)
  }

  return (
    <Component
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ref={ref as any}
      className={cn(
        'relative overflow-hidden rounded-lg border transition-[border-color,box-shadow] duration-200',
        isSidebar
          ? cn(
              'border-transparent bg-transparent',
              selected && cn('border-l-2 shadow-sm', SELECTED_BORDER[accent]),
              hover && !selected && 'border-l-2 border-white/20',
            )
          : cn(
              'border-aurora-border bg-aurora-surface',
              selected && cn(borders.selected, 'shadow-sm'),
              hover && !selected && cn(borders.hover, 'shadow-md'),
            ),
        className,
      )}
      onMouseEnter={(e: MouseEvent<HTMLElement>) => {
        setHover(true)
        onMouseEnter?.(e as never)
      }}
      onMouseLeave={(e: MouseEvent<HTMLElement>) => {
        setHover(false)
        setSpot({ x: 50, y: 50 })
        onMouseLeave?.(e as never)
      }}
      onMouseMove={handleMouseMove}
      {...props}
    >
      <div
        aria-hidden
        className={cn(
          'pointer-events-none absolute inset-0 transition-opacity duration-150',
          showSpotlight ? 'opacity-100' : 'opacity-0',
        )}
        style={{
          background: hover
            ? `radial-gradient(${isSidebar ? 180 : 260}px circle at ${spot.x}% ${spot.y}%, rgba(${rgb}, ${isSidebar ? 0.35 : 0.28}), transparent 68%)`
            : selected
              ? `radial-gradient(ellipse at 50% 0%, rgba(${rgb}, ${isSidebar ? 0.18 : 0.12}), transparent 70%)`
              : undefined,
        }}
      />
      <div className={cn('relative z-10', innerClassName)}>{children}</div>
    </Component>
  )
}
