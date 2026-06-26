import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { ThemeProvider } from './contexts/ThemeProvider'
import { CommandPaletteProvider } from './hooks/useCommandPalette'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { PermissionRoute } from './components/auth/PermissionRoute'
import { AppShell } from './components/layout/AppShell'
import { ErrorBoundary } from './components/feedback/ErrorBoundary'
import { KeyboardShortcuts } from './components/feedback/KeyboardShortcuts'
import { AuthProvider } from './hooks/useAuth'
import { Dashboard } from './pages/Dashboard'
import { RegisterPage } from './pages/RegisterPage'
import { InactivatePage } from './pages/InactivatePage'
import { ConsultPage } from './pages/ConsultPage'
import { DormantPage } from './pages/DormantPage'
import { ProfilePage } from './pages/ProfilePage'
import { LoginPage } from './pages/LoginPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { UsersManagePage } from './pages/UsersManagePage'

const queryClient = new QueryClient()

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <CommandPaletteProvider>
            <BrowserRouter>
              <AuthProvider>
                <Routes>
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/login/forgot" element={<ForgotPasswordPage />} />
                  <Route path="/login/reset" element={<ResetPasswordPage />} />
                  <Route element={<ProtectedRoute />}>
                    <Route element={<AppShell />}>
                      <Route index element={<Dashboard />} />
                      <Route
                        path="cadastrar"
                        element={
                          <PermissionRoute permission="cadastrar">
                            <RegisterPage />
                          </PermissionRoute>
                        }
                      />
                      <Route
                        path="inativar"
                        element={
                          <PermissionRoute permission="inativar">
                            <InactivatePage />
                          </PermissionRoute>
                        }
                      />
                      <Route
                        path="consultar"
                        element={
                          <PermissionRoute permission="consultar">
                            <ConsultPage />
                          </PermissionRoute>
                        }
                      />
                      <Route
                        path="empresas-inativas"
                        element={
                          <PermissionRoute permission="empresas_inativas">
                            <DormantPage />
                          </PermissionRoute>
                        }
                      />
                      <Route
                        path="usuarios"
                        element={
                          <PermissionRoute permission="manage_users">
                            <UsersManagePage />
                          </PermissionRoute>
                        }
                      />
                      <Route path="perfil" element={<ProfilePage />} />
                    </Route>
                  </Route>
                </Routes>
                <Toaster richColors position="top-right" closeButton />
                <KeyboardShortcuts />
              </AuthProvider>
            </BrowserRouter>
          </CommandPaletteProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
