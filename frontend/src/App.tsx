import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { ThemeProvider } from './contexts/ThemeProvider'
import { CommandPaletteProvider } from './hooks/useCommandPalette'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { AppShell } from './components/layout/AppShell'
import { ErrorBoundary } from './components/feedback/ErrorBoundary'
import { KeyboardShortcuts } from './components/feedback/KeyboardShortcuts'
import { AuthProvider } from './hooks/useAuth'
import { Dashboard } from './pages/Dashboard'
import { RegisterPage } from './pages/RegisterPage'
import { InactivatePage } from './pages/InactivatePage'
import { ConsultPage } from './pages/ConsultPage'
import { DormantPage } from './pages/DormantPage'
import { LoginPage } from './pages/LoginPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'

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
                      <Route path="cadastrar" element={<RegisterPage />} />
                      <Route path="inativar" element={<InactivatePage />} />
                      <Route path="consultar" element={<ConsultPage />} />
                      <Route path="empresas-inativas" element={<DormantPage />} />
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
