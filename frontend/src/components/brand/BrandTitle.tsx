import { cn } from '@/lib/cn'

type Props = {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizes = {
  sm: 'text-base tracking-[0.04em]',
  md: 'text-xl tracking-[0.04em]',
  lg: 'text-2xl tracking-[0.05em]',
}

export function BrandTitle({ className, size = 'md' }: Props) {
  return (
    <h1
      className={cn('font-brand font-extrabold uppercase', sizes[size], className)}
      aria-label="AVS Management"
    >
      <span className="text-brand-red">A</span>
      <span className="text-brand-navy">VS </span>
      <span className="text-brand-red">M</span>
      <span className="text-brand-navy">ANAGEMENT</span>
    </h1>
  )
}
