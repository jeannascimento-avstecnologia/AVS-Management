import { cn } from '@/lib/cn'

export const LOGO_SRC = '/static/Logo_AVS_Management.png?v=1'

export type LogoVariant = 'sidebar' | 'topbar' | 'auth' | 'onLight'

type Props = {
  className?: string
  imgClassName?: string
  variant?: LogoVariant
  collapsed?: boolean
}

const variantConfig: Record<
  LogoVariant,
  { img: string; wrapper?: string; blend?: boolean }
> = {
  topbar: {
    img: 'h-12 w-auto max-w-[200px] md:h-[52px]',
    blend: true,
  },
  sidebar: {
    img: 'h-9 w-auto max-w-[150px]',
    blend: true,
  },
  auth: {
    img: 'h-16 w-auto max-w-[240px] sm:h-[4.5rem] sm:max-w-[280px] md:h-20 md:max-w-[300px]',
    blend: true,
  },
  onLight: {
    img: 'h-9 w-auto max-w-[160px]',
    wrapper: 'logo-box-navy',
  },
}

export function Logo({
  className,
  imgClassName,
  variant = 'onLight',
  collapsed = false,
}: Props) {
  const config = variantConfig[variant]
  const imgSize =
    variant === 'sidebar' && collapsed
      ? 'h-7 w-auto max-w-[3rem]'
      : config.img

  return (
    <div className={cn('inline-flex shrink-0 items-center justify-center', config.wrapper, className)}>
      <img
        src={LOGO_SRC}
        alt="AVS Management"
        className={cn(
          'object-contain object-left',
          imgSize,
          config.blend && 'mix-blend-screen',
          imgClassName,
        )}
      />
    </div>
  )
}
