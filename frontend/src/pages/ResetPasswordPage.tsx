import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { AuthLayout } from '@/components/auth/AuthLayout'
import { resetPasswordSchema, type ResetPasswordForm } from '@/lib/schemas'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

function readResetToken(): string {
  const hash = window.location.hash
  if (hash.startsWith('#token=')) {
    return decodeURIComponent(hash.slice('#token='.length))
  }
  const params = new URLSearchParams(window.location.search)
  return params.get('token') || ''
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const [token, setToken] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const value = readResetToken()
    if (value) {
      setToken(value)
      window.history.replaceState(null, '', window.location.pathname)
    }
  }, [params])

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordForm>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: '', confirm: '' },
  })

  async function onSubmit(data: ResetPasswordForm) {
    if (!token) {
      toast.error('Link inválido ou expirado.')
      return
    }
    try {
      await api.resetPassword({ token, password: data.password })
      toast.success('Senha redefinida com sucesso.')
      navigate('/login', { replace: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Não foi possível redefinir a senha.')
    }
  }

  if (!token) {
    return (
      <AuthLayout title="Link inválido" subtitle="Solicite um novo link de recuperação de senha.">
        <Link to="/login/forgot" className="text-sm text-primary hover:underline">
          Solicitar novo link
        </Link>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title="Nova senha" subtitle="Mínimo 5 caracteres, com maiúscula, minúscula e número.">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="password">Nova senha</Label>
          <Input id="password" type="password" autoComplete="new-password" {...register('password')} />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirm">Confirmar senha</Label>
          <Input id="confirm" type="password" autoComplete="new-password" {...register('confirm')} />
          {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
        </div>
        <Button type="submit" className="w-full" loading={isSubmitting}>
          Redefinir senha
        </Button>
      </form>
    </AuthLayout>
  )
}
