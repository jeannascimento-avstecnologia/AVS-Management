import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email('Informe um e-mail válido'),
  password: z.string().min(1, 'Informe a senha'),
  remember_me: z.boolean().optional(),
})

export const forgotPasswordSchema = z.object({
  email: z.string().email('Informe um e-mail válido'),
})

export const resetPasswordSchema = z
  .object({
    password: z
      .string()
      .min(5, 'Mínimo 5 caracteres')
      .regex(/[A-Z]/, 'Inclua uma letra maiúscula')
      .regex(/[a-z]/, 'Inclua uma letra minúscula')
      .regex(/[0-9]/, 'Inclua um número'),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: 'As senhas não coincidem',
    path: ['confirm'],
  })

export const cnpjSchema = z.object({
  cnpj: z
    .string()
    .transform((v) => v.replace(/\D/g, ''))
    .refine((v) => v.length === 14, 'Informe um CNPJ válido'),
})

export const querySchema = z.object({
  query: z.string().min(2, 'Informe CNPJ ou nome'),
})

export type LoginForm = z.infer<typeof loginSchema>
export type ForgotPasswordForm = z.infer<typeof forgotPasswordSchema>
export type ResetPasswordForm = z.infer<typeof resetPasswordSchema>
