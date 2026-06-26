import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { AuthLayout } from '@/components/auth/AuthLayout'
import { useAuth } from '@/hooks/useAuth'
import { loginSchema, type LoginForm } from '@/lib/schemas'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'

export function LoginPage() {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '', remember_me: false },
  })

  const rememberMe = watch('remember_me')

  async function onSubmit(data: LoginForm) {
    try {
      const res = await api.login(data)
      if (!res?.ok) throw new Error('Não foi possível entrar.')
      const loggedIn = await refresh()
      if (!loggedIn || loggedIn.dev_mode) {
        throw new Error('Autenticação indisponível. Reinicie o servidor após ativar AUTH_ENABLED=true no .env.')
      }
      navigate(res.redirect || '/', { replace: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Não foi possível entrar.')
    }
  }

  return (
    <AuthLayout
      title="Entrar"
      subtitle="Use seu e-mail e senha corporativos"
      tagline="Plataforma interna de gestão de recursos da AVS"
      showBackLink={false}
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">E-mail</Label>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            placeholder="seu.nome@avs.com.br"
            {...register('email')}
          />
          {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Senha</Label>
          <Input id="password" type="password" autoComplete="current-password" {...register('password')} />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
        </div>
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Switch
              id="remember"
              checked={rememberMe}
              onCheckedChange={(v) => setValue('remember_me', v)}
            />
            <Label htmlFor="remember" className="text-sm font-normal text-muted-foreground">
              Lembrar-me
            </Label>
          </div>
          <Link to="/login/forgot" className="text-sm text-primary hover:underline">
            Esqueci minha senha
          </Link>
        </div>
        <Button type="submit" className="w-full" loading={isSubmitting}>
          Entrar
        </Button>
      </form>
    </AuthLayout>
  )
}
