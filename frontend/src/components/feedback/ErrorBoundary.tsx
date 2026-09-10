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
    // #region agent log
    fetch('http://127.0.0.1:7624/ingest/4fbad495-1d4e-4120-8a74-d59ccbb75445',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'49cf6c'},body:JSON.stringify({sessionId:'49cf6c',hypothesisId:'F',location:'ErrorBoundary.tsx:componentDidCatch',message:'render crash',data:{err:error.message,stack:(error.stack??'').slice(0,800),componentStack:(info.componentStack??'').slice(0,800)},timestamp:Date.now()})}).catch(()=>{});
    fetch('http://127.0.0.1:7624/ingest/4fbad495-1d4e-4120-8a74-d59ccbb75445',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'95d267'},body:JSON.stringify({sessionId:'95d267',runId:'pre-fix',hypothesisId:'F',location:'ErrorBoundary.tsx:componentDidCatch',message:'render crash',data:{err:error.message,stack:(error.stack??'').slice(0,800),componentStack:(info.componentStack??'').slice(0,800),path:window.location.pathname},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
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
