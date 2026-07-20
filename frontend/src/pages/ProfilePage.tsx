import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { useAuth } from '@/hooks/useAuth'
import { changePasswordSchema, profileSchema, type ChangePasswordForm, type ProfileForm } from '@/lib/schemas'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

export function ProfilePage() {
  const { refresh } = useAuth()
  const [loading, setLoading] = useState(true)
  const [email, setEmail] = useState('')
  const [passwordOpen, setPasswordOpen] = useState(false)

  const profileForm = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: { name: '', backup_email: '', phone: '' },
  })

  const passwordForm = useForm<ChangePasswordForm>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: '', password: '', confirm: '' },
  })

  useEffect(() => {
    api
      .getProfile()
      .then((data) => {
        setEmail(data.email)
        profileForm.reset({
          name: data.name,
          backup_email: data.backup_email || '',
          phone: data.phone || '',
        })
      })
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Erro ao carregar perfil'))
      .finally(() => setLoading(false))
  }, [profileForm])

  async function onSaveProfile(data: ProfileForm) {
    try {
      await api.updateProfile({
        name: data.name,
        backup_email: data.backup_email.trim(),
        phone: (data.phone || '').trim(),
      })
      await refresh()
      toast.success('Perfil atualizado')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar perfil')
    }
  }

  async function onChangePassword(data: ChangePasswordForm) {
    try {
      const res = await api.changePassword({
        current_password: data.current_password,
        new_password: data.password,
        confirm_password: data.confirm,
      })
      toast.success(res.message || 'Senha alterada')
      passwordForm.reset()
      setPasswordOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao alterar senha')
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Perfil</h1>
        <p className="mt-1 text-sm text-aurora-muted">Configurações da conta e segurança.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configurações</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-aurora-muted">Carregando…</p>
          ) : (
            <form onSubmit={profileForm.handleSubmit(onSaveProfile)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">E-mail</Label>
                <Input id="email" value={email} disabled readOnly className="bg-aurora-surface-2" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Nome</Label>
                <Input id="name" {...profileForm.register('name')} />
                {profileForm.formState.errors.name && (
                  <p className="text-xs text-destructive">{profileForm.formState.errors.name.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="backup_email">E-mail de backup</Label>
                <Input id="backup_email" type="email" {...profileForm.register('backup_email')} />
                {profileForm.formState.errors.backup_email && (
                  <p className="text-xs text-destructive">{profileForm.formState.errors.backup_email.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Telefone</Label>
                <Input id="phone" type="tel" placeholder="(00) 00000-0000" {...profileForm.register('phone')} />
              </div>
              <Button type="submit" loading={profileForm.formState.isSubmitting}>
                Salvar alterações
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Senha</CardTitle>
        </CardHeader>
        <CardContent>
          <Dialog open={passwordOpen} onOpenChange={setPasswordOpen}>
            <DialogTrigger asChild>
              <Button variant="outline">Alterar senha</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Alterar senha</DialogTitle>
              </DialogHeader>
              <form onSubmit={passwordForm.handleSubmit(onChangePassword)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="current_password">Senha atual</Label>
                  <Input
                    id="current_password"
                    type="password"
                    autoComplete="current-password"
                    {...passwordForm.register('current_password')}
                  />
                  {passwordForm.formState.errors.current_password && (
                    <p className="text-xs text-destructive">
                      {passwordForm.formState.errors.current_password.message}
                    </p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Nova senha</Label>
                  <Input
                    id="password"
                    type="password"
                    autoComplete="new-password"
                    {...passwordForm.register('password')}
                  />
                  {passwordForm.formState.errors.password && (
                    <p className="text-xs text-destructive">{passwordForm.formState.errors.password.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm">Confirmar nova senha</Label>
                  <Input
                    id="confirm"
                    type="password"
                    autoComplete="new-password"
                    {...passwordForm.register('confirm')}
                  />
                  {passwordForm.formState.errors.confirm && (
                    <p className="text-xs text-destructive">{passwordForm.formState.errors.confirm.message}</p>
                  )}
                </div>
                <Button type="submit" loading={passwordForm.formState.isSubmitting} className="w-full">
                  Confirmar alteração
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </CardContent>
      </Card>
    </div>
  )
}
