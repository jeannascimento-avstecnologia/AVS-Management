import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Logo } from '@/components/brand/Logo'
import { BrandTitle } from '@/components/brand/BrandTitle'
import { Card, CardContent } from '@/components/ui/card'

export function AuthLayout({
  children,
  title,
  subtitle,
  showBackLink = true,
}: {
  children: React.ReactNode
  title: string
  subtitle?: string
  showBackLink?: boolean
}) {
  return (
    <div className="flex min-h-screen">
      <div className="flex flex-1 flex-col items-center justify-center px-4 py-10 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 flex flex-col items-center text-center lg:hidden"
        >
          <Logo size="lg" className="mb-4" />
          <BrandTitle size="lg" />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="w-full max-w-md"
        >
          <Card className="border-border/80 shadow-lg">
            <CardContent className="p-8">
              <h2 className="text-xl font-bold tracking-tight">{title}</h2>
              {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
              <div className="mt-6">{children}</div>
            </CardContent>
          </Card>
          {showBackLink && (
            <p className="mt-6 text-center text-sm text-muted-foreground">
              <Link to="/login" className="font-medium text-primary hover:text-brand-red">
                Voltar ao login
              </Link>
            </p>
          )}
        </motion.div>
      </div>

      <div className="relative hidden w-[42%] overflow-hidden bg-primary lg:flex lg:flex-col lg:items-center lg:justify-center lg:p-12">
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage: `radial-gradient(circle at 20% 50%, rgba(220,38,38,0.15) 0%, transparent 50%),
              radial-gradient(circle at 80% 20%, rgba(255,255,255,0.08) 0%, transparent 40%),
              linear-gradient(135deg, transparent 25%, rgba(255,255,255,0.03) 25%, rgba(255,255,255,0.03) 50%, transparent 50%, transparent 75%, rgba(255,255,255,0.03) 75%)`,
            backgroundSize: '100% 100%, 100% 100%, 24px 24px',
          }}
        />
        <div className="relative z-10 flex flex-col items-center text-center">
          <Logo size="lg" className="mb-6" />
          <BrandTitle size="lg" className="text-primary-foreground [&_span]:!text-primary-foreground [&_span.text-brand-red]:!text-brand-red" />
          <p className="mt-4 max-w-xs text-sm text-primary-foreground/80">
            Plataforma interna para operações TiFlux, VHSYS e consultas CNPJ.
          </p>
        </div>
      </div>
    </div>
  )
}
