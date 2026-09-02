import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, FileText, Loader2, Search, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { api, type QuoteProposalTemplateRead } from '@/api/client'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { btnDangerClass, inputClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

export type QuoteProposalTemplatesPanelProps = {
  embedded?: boolean
  onSelect?: (template: QuoteProposalTemplateRead) => void
}

export function QuoteProposalTemplatesPanel({
  embedded,
  onSelect,
}: QuoteProposalTemplatesPanelProps) {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')

  const listQuery = useQuery({
    queryKey: ['quote-proposal-templates'],
    queryFn: () => api.listQuoteProposalTemplates(),
  })

  const templates = listQuery.data?.templates ?? []
  const filtered = useMemo(() => {
    const q = search.trim().toLocaleLowerCase('pt-BR')
    if (!q) return templates
    return templates.filter((t) => t.name.toLocaleLowerCase('pt-BR').includes(q))
  }, [templates, search])

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteQuoteProposalTemplate(id),
    onSuccess: () => {
      toast.success('Modelo removido')
      void queryClient.invalidateQueries({ queryKey: ['quote-proposal-templates'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Erro ao remover modelo')
    },
  })

  return (
    <div className="space-y-4">
      {!embedded && (
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 shrink-0 text-aurora-info" aria-hidden />
          <h2 className="text-lg font-semibold tracking-tight text-aurora-fg">
            Biblioteca de Orçamentos
          </h2>
        </div>
      )}

      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Pesquisar modelos…"
          className={cn(inputClass, 'pl-8')}
          aria-label="Pesquisar modelos de orçamento"
        />
      </div>

      {listQuery.isError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {listQuery.error instanceof Error
              ? listQuery.error.message
              : 'Não foi possível carregar a biblioteca de orçamentos.'}
          </AlertDescription>
        </Alert>
      )}

      {listQuery.isPending && (
        <div className="space-y-3">
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-16 w-full rounded-xl" />
        </div>
      )}

      {!listQuery.isPending && !listQuery.isError && filtered.length === 0 && (
        <EmptyState
          icon={FileText}
          title={templates.length === 0 ? 'Nenhum modelo salvo' : 'Nenhum resultado'}
          description={
            templates.length === 0
              ? 'No passo 2 do orçamento, use Salvar modelo de orçamento.'
              : 'Tente outro termo de busca.'
          }
        />
      )}

      {!listQuery.isPending && filtered.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2">
          {filtered.map((template) => {
            const count = template.modules.length
            return (
              <li key={template.id}>
                <div
                  className={cn(
                    'flex flex-col gap-2 rounded-lg border border-aurora-border bg-aurora-surface-2/30 p-3',
                    'hover:border-aurora-info/50 hover:bg-aurora-info/5',
                  )}
                >
                  <button
                    type="button"
                    className="min-w-0 text-left"
                    onClick={() => onSelect?.(template)}
                    disabled={!onSelect}
                  >
                    <span className="line-clamp-2 text-sm font-semibold text-foreground">
                      {template.name}
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      {count === 1 ? '1 bloco' : `${count} blocos`}
                      {template.items.length
                        ? ` · ${template.items.length} item(ns)`
                        : ''}
                    </span>
                  </button>
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="outline" className="text-[10px]">
                      Modelo
                    </Badge>
                    <Button
                      type="button"
                      size="sm"
                      className={cn(btnDangerClass, 'h-8 px-2')}
                      disabled={deleteMutation.isPending}
                      onClick={() => {
                        if (window.confirm(`Remover modelo “${template.name}”?`)) {
                          deleteMutation.mutate(template.id)
                        }
                      }}
                      aria-label={`Remover modelo ${template.name}`}
                    >
                      {deleteMutation.isPending && deleteMutation.variables === template.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {onSelect ? null : (
        <p className="text-xs text-muted-foreground">Selecione um modelo para aplicar ao rascunho.</p>
      )}
    </div>
  )
}
