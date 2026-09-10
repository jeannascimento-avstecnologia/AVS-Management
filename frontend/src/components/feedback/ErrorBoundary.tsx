import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { groupHomePath } from '@/lib/groupHome'

type Props = { children: ReactNode }
type State = { hasError: boolean; message?: string }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary', error, info)
    const home = groupHomePath(window.location.pathname)
    if (window.location.pathname !== home) {
      window.location.replace(home)
    }
  }

  render() {
    if (this.state.hasError) {
      const home = groupHomePath(window.location.pathname)
      return (
        <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-8 text-center">
          <div className="rounded-full bg-destructive/10 p-4">
            <AlertTriangle className="h-8 w-8 text-destructive" />
          </div>
          <h2 className="text-lg font-semibold">Algo deu errado</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            {this.state.message || 'Ocorreu um erro inesperado.'}
          </p>
          <Button onClick={() => window.location.replace(home)}>Voltar</Button>
        </div>
      )
    }
    return this.props.children
  }
}
