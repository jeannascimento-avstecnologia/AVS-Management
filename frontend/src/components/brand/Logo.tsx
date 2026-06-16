import { cn } from '@/lib/cn'

const LOGO_SRC = '/static/logo-avs.png'

type Props = {
  className?: string
  imgClassName?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizes = {
  sm: 'h-8',
  md: 'h-10',
  lg: 'h-12',
}

export function Logo({ className, imgClassName, size = 'md' }: Props) {
  return (
    <div className={cn('logo-panel inline-flex', className)}>
      <img
        src={LOGO_SRC}
        alt="AVS Tecnologia"
        className={cn('w-auto object-contain', sizes[size], imgClassName)}
      />
    </div>
  )
}
