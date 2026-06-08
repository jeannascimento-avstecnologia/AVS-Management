import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AuthProvider } from './hooks/useAuth'
import { AppShell } from './components/layout/AppShell'
import { Dashboard } from './pages/Dashboard'
import { RegisterPage } from './pages/RegisterPage'
import { InactivatePage } from './pages/InactivatePage'
import { ConsultPage } from './pages/ConsultPage'
import { DormantPage } from './pages/DormantPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="cadastrar" element={<RegisterPage />} />
            <Route path="inativar" element={<InactivatePage />} />
            <Route path="consultar" element={<ConsultPage />} />
            <Route path="empresas-inativas" element={<DormantPage />} />
          </Route>
        </Routes>
        <Toaster richColors position="top-right" />
      </AuthProvider>
    </BrowserRouter>
  )
}
