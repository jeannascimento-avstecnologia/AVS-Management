import { useEffect, useMemo, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
  type ColumnDef,
  type PaginationState,
  type SortingState,
} from '@tanstack/react-table'
import { Download, Eye, EyeOff, FileText, MoreHorizontal, Printer, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  buildDormantReportHtml,
  downloadBlob,
  parseDormantReport,
  dormantTruncatedNote,
  type DormantClientRow,
  type ParsedDormantReport,
} from '@/lib/dormantReport'
import { filterAndSortDormantRows, type ReasonFilter, type SortKey } from '@/lib/dormantFilters'
import { applyPaginationUpdate } from '@/lib/dormantPagination'
import { formatCnpj, formatDate } from '@/lib/format'
import { cn } from '@/lib/cn'

type Props = {
  raw: Record<string, unknown>
  onNewReport?: () => void
}

const FILTER_OPTIONS: { id: ReasonFilter; label: string }[] = [
  { id: 'all', label: 'Todas' },
  { id: 'sem_ticket', label: 'Sem ticket' },
  { id: 'sem_cobranca', label: 'Sem cobrança' },
  { id: 'sem_ambos', label: 'Sem ambos' },
]

const SORT_KEYS: SortKey[] = ['social', 'cnpj', 'last_ticket_at', 'last_billing_at', 'reasons']

function toSortKey(id: string | undefined): SortKey {
  if (id && SORT_KEYS.includes(id as SortKey)) return id as SortKey
  return 'social'
}

function buildExportPayload(parsed: ParsedDormantReport, rows: DormantClientRow[]) {
  return {
    ...parsed,
    total: rows.length,
    clients: rows.map((c) => ({
      id: c.id,
      name: c.name,
      social: c.social,
      social_revenue: c.social_revenue,
      last_ticket_at: c.last_ticket_at,
      last_billing_at: c.last_billing_at,
      reasons: c.reasonCodes,
    })),
  }
}

export function DormantReportView({ raw, onNewReport }: Props) {
  const navigate = useNavigate()
  const parsed = useMemo(() => parseDormantReport(raw), [raw])
  const stamp = new Date().toISOString().slice(0, 10)

  const [search, setSearch] = useState('')
  const [reasonFilter, setReasonFilter] = useState<ReasonFilter>('all')
  const [sorting, setSorting] = useState<SortingState>([{ id: 'social', desc: false }])
  const [showCompanies, setShowCompanies] = useState(true)
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 25 })

  const onPaginationChange = useCallback((updater: React.SetStateAction<PaginationState>) => {
    setPagination((prev) => applyPaginationUpdate(prev, updater))
  }, [])

  useEffect(() => {
    setPagination((p) => (p.pageIndex === 0 ? p : { ...p, pageIndex: 0 }))
  }, [search, reasonFilter])

  const filteredRows = useMemo(
    () =>
      filterAndSortDormantRows(parsed.clients, {
        search,
        reasonFilter,
        sortKey: toSortKey(sorting[0]?.id),
        sortDir: sorting[0]?.desc ? 'desc' : 'asc',
      }),
    [parsed.clients, search, reasonFilter, sorting],
  )

  const columns = useMemo<ColumnDef<DormantClientRow>[]>(
    () => [
      {
        accessorKey: 'social',
        header: 'Razão social',
        cell: ({ row }) => <span className="font-medium">{row.original.social || row.original.name}</span>,
      },
      {
        id: 'cnpj',
        accessorFn: (r) => r.social_revenue,
        header: 'CNPJ',
        cell: ({ row }) => <span className="font-mono text-xs">{formatCnpj(row.original.social_revenue)}</span>,
      },
      {
        accessorKey: 'last_ticket_at',
        header: 'Último ticket',
        cell: ({ row }) => formatDate(row.original.last_ticket_at),
      },
      {
        accessorKey: 'last_billing_at',
        header: 'Última cobrança',
        cell: ({ row }) => formatDate(row.original.last_billing_at),
      },
      {
        id: 'reasons',
        header: 'Motivo',
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            {row.original.reasonLabels.map((r) => (
              <Badge key={r} variant="secondary" className="text-xs font-normal">
                {r}
              </Badge>
            ))}
          </div>
        ),
      },
      {
        id: 'actions',
        header: '',
        enableSorting: false,
        cell: ({ row }) => (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={() =>
                  navigate(`/consultar?q=${encodeURIComponent(row.original.social_revenue || row.original.social)}`)
                }
              >
                Consultar
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate(`/inativar?q=${encodeURIComponent(row.original.social || '')}`)}>
                Inativar
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ),
      },
    ],
    [navigate],
  )

  const table = useReactTable({
    data: filteredRows,
    columns,
    state: { sorting, pagination },
    onSortingChange: setSorting,
    onPaginationChange,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    autoResetPageIndex: false,
    manualSorting: true,
  })

  const exportParsed = useMemo(() => ({ ...parsed, total: filteredRows.length, clients: filteredRows }), [parsed, filteredRows])

  function handleSaveHtml() {
    const exportRaw = buildExportPayload(parsed, filteredRows)
    downloadBlob(
      buildDormantReportHtml(exportParsed, exportRaw as unknown as Record<string, unknown>),
      `empresas-sem-atividade-${stamp}.html`,
      'text/html;charset=utf-8',
    )
  }

  return (
    <div className="dormant-report">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Empresas sem atividade</h2>
          <p className="text-sm text-muted-foreground">
            {parsed.months} meses · Analisados: <strong>{parsed.scanned}</strong> · Encontrados:{' '}
            <strong>{parsed.total}</strong>
            {parsed.truncated ? dormantTruncatedNote(parsed) : ''} · Exibindo: <strong>{filteredRows.length}</strong>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowCompanies((v) => !v)}>
            {showCompanies ? (
              <>
                <EyeOff className="h-4 w-4" /> Ocultar
              </>
            ) : (
              <>
                <Eye className="h-4 w-4" /> Exibir
              </>
            )}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <MoreHorizontal className="h-4 w-4" /> Exportar
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => window.print()}>
                <Printer className="mr-2 h-4 w-4" /> Imprimir
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleSaveHtml}>
                <FileText className="mr-2 h-4 w-4" /> HTML
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() =>
                  downloadBlob(
                    JSON.stringify(buildExportPayload(parsed, filteredRows), null, 2),
                    `empresas-${stamp}.json`,
                    'application/json',
                  )
                }
              >
                <Download className="mr-2 h-4 w-4" /> JSON
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {showCompanies && (
        <>
          <div className="no-print mb-4 flex flex-wrap gap-3">
            <div className="relative max-w-sm flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-9" placeholder="Buscar…" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <div className="flex flex-wrap gap-2">
              {FILTER_OPTIONS.map((opt) => (
                <Button
                  key={opt.id}
                  type="button"
                  size="sm"
                  variant={reasonFilter === opt.id ? 'default' : 'outline'}
                  onClick={() => setReasonFilter(opt.id)}
                >
                  {opt.label}
                </Button>
              ))}
            </div>
          </div>

          <div className={cn('overflow-x-auto rounded-xl border border-border', !showCompanies && 'hidden')}>
            <table className="w-full min-w-[800px] text-left text-sm">
              <thead>
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id} className="border-b bg-muted/50">
                    {hg.headers.map((h) => (
                      <th key={h.id} className="p-3 font-semibold">
                        {h.isPlaceholder ? null : h.column.getCanSort() ? (
                          <button
                            type="button"
                            className="flex items-center gap-1 hover:text-primary"
                            onClick={h.column.getToggleSortingHandler()}
                          >
                            {flexRender(h.column.columnDef.header, h.getContext())}
                            {{ asc: ' ↑', desc: ' ↓' }[h.column.getIsSorted() as string] ?? null}
                          </button>
                        ) : (
                          flexRender(h.column.columnDef.header, h.getContext())
                        )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.length === 0 ? (
                  <tr>
                    <td colSpan={columns.length} className="p-8 text-center text-muted-foreground">
                      Nenhuma empresa corresponde aos filtros.
                    </td>
                  </tr>
                ) : (
                  table.getRowModel().rows.map((row) => (
                    <tr key={row.id} className="border-b border-border/60 transition-colors hover:bg-muted/30">
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="p-3">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="no-print mt-4 flex flex-wrap items-center justify-between gap-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Por página</span>
              <Select
                value={String(pagination.pageSize)}
                onValueChange={(v) => onPaginationChange({ pageIndex: 0, pageSize: Number(v) })}
              >
                <SelectTrigger className="h-8 w-[80px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
                Anterior
              </Button>
              <span className="text-muted-foreground">
                {table.getState().pagination.pageIndex + 1} / {table.getPageCount() || 1}
              </span>
              <Button variant="outline" size="sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
                Próxima
              </Button>
            </div>
          </div>
        </>
      )}

      {onNewReport && (
        <div className="no-print mt-6">
          <Button variant="outline" onClick={onNewReport}>
            Gerar novo relatório
          </Button>
        </div>
      )}
    </div>
  )
}
