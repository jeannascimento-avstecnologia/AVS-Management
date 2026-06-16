import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { AuthLayout } from '@/components/auth/AuthLayout'
import { forgotPasswordSchema, type ForgotPasswordForm } from '@/lib/schemas'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const GENERIC_MESSAGE =
  'Se o e-mail estiver cadastrado, enviaremos instruções para redefinir a senha.'

export function ForgotPasswordPage() {
  const [sent, setSent] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordForm>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: '' },
  })

  async function onSubmit(data: ForgotPasswordForm) {
    try {
      const res = await api.forgotPassword(data)
      setSent(true)
      toast.success(res.message || GENERIC_MESSAGE)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Não foi possível enviar o pedido.')
    }
  }

  return (
    <AuthLayout
      title="Esqueci minha senha"
      subtitle="Informe o e-mail cadastrado. Enviaremos um link para redefinir a senha."
    >
      {sent ? (
        <div className="space-y-4 text-sm text-muted-foreground">
          <p>{GENERIC_MESSAGE}</p>
          <p>Verifique sua caixa de entrada e o spam.</p>
          <Link to="/login" className="inline-block text-primary hover:underline">
            Voltar ao login
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">E-mail</Label>
            <Input id="email" type="email" {...register('email')} />
            {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
          </div>
          <Button type="submit" className="w-full" loading={isSubmitting}>
            Enviar link
          </Button>
        </form>
      )}
    </AuthLayout>
  )
}
