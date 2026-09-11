import { cn } from '@/lib/cn'

export const LOGO_SRC = '/static/logo_veivo_gestao.png?v=2'
const LOGO_GESTAO_SRC = '/static/logo_gestao.png?v=1'
const LOGO_VEIVO_WHITE_SRC = '/static/logo_veivo_white.png?v=1'

export type LogoVariant = 'sidebar' | 'topbar' | 'auth' | 'onLight'

type Props = {
  className?: string
  imgClassName?: string
  variant?: LogoVariant
  collapsed?: boolean
}

const variantConfig: Record<
  LogoVariant,
  { img: string; wrapper?: string; blend?: boolean; src: string; alt: string }
> = {
  topbar: {
    img: 'h-9 w-auto max-w-[200px] md:h-10',
    src: LOGO_GESTAO_SRC,
    alt: 'GESTÃO',
  },
  sidebar: {
    img: 'h-9 w-auto max-w-[150px]',
    blend: true,
    src: LOGO_VEIVO_WHITE_SRC,
    alt: 'VEIVO',
  },
  auth: {
    img: 'h-16 w-auto max-w-[240px] sm:h-[4.5rem] sm:max-w-[280px] md:h-20 md:max-w-[300px]',
    blend: true,
    src: LOGO_SRC,
    alt: 'VEIVO Gestão',
  },
  onLight: {
    img: 'h-9 w-auto max-w-[160px]',
    wrapper: 'logo-box-navy',
    src: LOGO_SRC,
    alt: 'VEIVO Gestão',
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
        src={config.src}
        alt={config.alt}
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
