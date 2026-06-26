import { useEffect, useState } from 'react'
import { Pencil } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { SpotlightSelectable } from '@/components/ui/SpotlightSelectable'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

type TifluxProfile = {
  client?: Record<string, unknown>
  desks?: Array<Record<string, unknown>>
  technical_groups?: Array<Record<string, unknown>>
}

function extractIds(items: Array<Record<string, unknown>> | undefined): number[] {
  if (!items?.length) return []
  return items
    .map((item) => Number(item.id))
    .filter((id) => Number.isFinite(id))
}

function initialDeskIds(profile: TifluxProfile): number[] {
  const fromClient = profile.client?.desk_ids
  if (Array.isArray(fromClient) && fromClient.length) {
    return fromClient.map((id) => Number(id)).filter((id) => Number.isFinite(id))
  }
  return extractIds(profile.desks)
}

function initialGroupIds(profile: TifluxProfile): number[] {
  const fromClient = profile.client?.technical_group_ids
  if (Array.isArray(fromClient) && fromClient.length) {
    return fromClient.map((id) => Number(id)).filter((id) => Number.isFinite(id))
  }
  return extractIds(profile.technical_groups)
}

type Props = {
  tifluxClientId: number
  profile: TifluxProfile
  onUpdated: (profile: TifluxProfile) => void
}

export function TifluxBindingEditor({ tifluxClientId, profile, onUpdated }: Props) {
  const [editing, setEditing] = useState(false)
  const [loadingCatalog, setLoadingCatalog] = useState(false)
  const [saving, setSaving] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [catalogDesks, setCatalogDesks] = useState<Array<Record<string, unknown>>>([])
  const [catalogGroups, setCatalogGroups] = useState<Array<Record<string, unknown>>>([])
  const [deskIds, setDeskIds] = useState<number[]>(() => initialDeskIds(profile))
  const [groupIds, setGroupIds] = useState<number[]>(() => initialGroupIds(profile))

  useEffect(() => {
    if (!editing) {
      setDeskIds(initialDeskIds(profile))
      setGroupIds(initialGroupIds(profile))
    }
  }, [profile, editing])

  async function startEditing() {
    setEditing(true)
    setLoadingCatalog(true)
    try {
      const catalog = await api.consultaTifluxOpcoes()
      setCatalogDesks((catalog.desks as Array<Record<string, unknown>>) || [])
      setCatalogGroups((catalog.technical_groups as Array<Record<string, unknown>>) || [])
    } catch (err) {
      setEditing(false)
      toast.error(err instanceof Error ? err.message : 'Não foi possível carregar opções do TiFlux')
    } finally {
      setLoadingCatalog(false)
    }
  }

  function cancelEditing() {
    setDeskIds(initialDeskIds(profile))
    setGroupIds(initialGroupIds(profile))
    setEditing(false)
  }

  async function saveBindings() {
    setSaving(true)
    try {
      const result = await api.consultaTifluxVinculos({
        tiflux_client_id: tifluxClientId,
        desk_ids: deskIds,
        technical_group_ids: groupIds,
      })
      const updated = (result.tiflux?.data || {}) as TifluxProfile
      onUpdated(updated)
      setEditing(false)
      setConfirmOpen(false)
      toast.success('Mesas e atendentes atualizados no TiFlux')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Falha ao salvar no TiFlux')
    } finally {
      setSaving(false)
    }
  }

  function handleSaveClick() {
    if (!deskIds.length || !groupIds.length) {
      toast.error('Selecione ao menos uma mesa e um grupo de atendentes')
      return
    }
    setConfirmOpen(true)
  }

  const desks = editing ? catalogDesks : profile.desks || []
  const groups = editing ? catalogGroups : profile.technical_groups || []

  return (
    <div className="mb-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-primary">Mesas e atendentes</h4>
        {!editing && (
          <Button type="button" variant="outline" size="sm" onClick={startEditing}>
            <Pencil className="h-3.5 w-3.5" />
            Editar mesas e atendentes
          </Button>
        )}
      </div>

      {editing ? (
        <>
          <div>
            <p className="mb-2 text-sm font-medium">Mesas de atendimento</p>
            {loadingCatalog ? (
              <p className="text-sm text-muted-foreground">Carregando opções…</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {catalogDesks.map((d) => {
                  const id = Number(d.id)
                  const checked = deskIds.includes(id)
                  return (
                    <SpotlightSelectable
                      key={id}
                      as="label"
                      accent="accent"
                      selected={checked}
                      className="cursor-pointer p-2 text-sm"
                      innerClassName="flex items-center gap-2"
                    >
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(c) =>
                          setDeskIds((prev) => (c ? [...prev, id] : prev.filter((x) => x !== id)))
                        }
                      />
                      {String(d.display_name || d.name)}
                    </SpotlightSelectable>
                  )
                })}
              </div>
            )}
          </div>
          <div>
            <p className="mb-2 text-sm font-medium">Grupos de atendentes</p>
            {loadingCatalog ? null : (
              <div className="grid max-h-48 gap-2 overflow-y-auto sm:grid-cols-2">
                {catalogGroups.map((g) => {
                  const id = Number(g.id)
                  const checked = groupIds.includes(id)
                  return (
                    <SpotlightSelectable
                      key={id}
                      as="label"
                      accent="accent"
                      selected={checked}
                      className="cursor-pointer p-2 text-sm"
                      innerClassName="flex items-center gap-2"
                    >
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(c) =>
                          setGroupIds((prev) => (c ? [...prev, id] : prev.filter((x) => x !== id)))
                        }
                      />
                      {String(g.name)}
                    </SpotlightSelectable>
                  )
                })}
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={handleSaveClick} loading={saving} disabled={loadingCatalog}>
              Salvar
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={cancelEditing} disabled={saving}>
              Cancelar
            </Button>
          </div>
        </>
      ) : (
        <>
          <section>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Mesas de serviço</p>
            <ul className="list-inside list-disc text-sm">
              {(desks.length ? desks : [{ name: '—' }]).map((d, i) => (
                <li key={String(d.id ?? i)}>
                  {String(d.display_name || d.name || 'Mesa')}
                  {d.active === false ? ' (inativa)' : ''}
                </li>
              ))}
            </ul>
          </section>
          <section>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Grupos de atendentes</p>
            <ul className="list-inside list-disc text-sm">
              {(groups.length ? groups : [{ name: '—' }]).map((g, i) => (
                <li key={String(g.id ?? i)}>{String(g.name || 'Grupo')}</li>
              ))}
            </ul>
          </section>
        </>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar alteração no TiFlux?</AlertDialogTitle>
            <AlertDialogDescription>
              As mesas e grupos de atendentes selecionados serão atualizados para este cliente no TiFlux.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={saving}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={saving}
              onClick={(e) => {
                e.preventDefault()
                void saveBindings()
              }}
            >
              Confirmar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
