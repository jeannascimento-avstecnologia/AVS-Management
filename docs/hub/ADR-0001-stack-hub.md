# ADR-0001 — Stack do hub vs Guarda-Mestra

**Status:** Aceito  
**Data:** 2026-07-20  
**Decisores:** Tech Lead (`@programador.mdc`)  
**Contexto:** P0.2 — desbloqueio de schema/código do hub comercial + faturamento

---

## Contexto

A Guarda-Mestra (`.cursor/rules/000-guarda-mestra.mdc`) e o template `docs/GUIA_MESTRE.md` apontam para **Supabase-first**, `org_id` + RLS, Edge Functions, `dnd-kit` e multi-tenant SaaS.

Este repositório (**avs-management**) já é um produto operacional interno com:

- FastAPI (`src/main.py`, `orchestrator.py`, `config.py`)
- SQLite `data/auth.db` + session cookies + CSRF + RBAC (`src/auth/*`)
- Clients TiFlux/VHSYS server-side (`src/integrations/*`)
- React/Vite SPA com `PermissionRoute` / Sidebar

`docs/GUIA_MESTRE.md` **não existe** neste repo. Não há Supabase, nem multi-tenant `org_id`.

---

## Decisão

**Não introduzir Supabase, RLS, Edge Functions nem multi-tenant neste ciclo.**

Stack canônica do hub:

| Camada | Escolha | Justificativa |
|--------|---------|---------------|
| API | FastAPI existente | Já autentica, audita e integra TiFlux/VHSYS |
| Domínio hub | SQLite `data/hub.db` (separado de `auth.db`) | Isola quotes/billing/outbox do auth; mesmo padrão de bootstrap |
| AuthZ | Session + `require_permission(...)` | Equivalente operacional a “policy”; permissões novas no mesmo catálogo |
| Segredos | `.env` / `Settings` (Pydantic) | Tokens nunca no bundle FE |
| Orquestração externa | n8n (2 fluxos) | Management = SoT; n8n = execução |
| Destinos | TiFlux + VHSYS | Já validados em leitura; POSTs via gate dry-run |

### Equivalências de segurança (Guarda → Hub)

| Inegociável Guarda (template) | Equivalente neste repo |
|------------------------------|-------------------------|
| RLS + `org_id` | App single-tenant AVS; isolamento = sessão autenticada + RBAC |
| Edge Functions privilegiadas | Rotas FastAPI + clients server-side; n8n só com HMAC |
| Secrets fora do cliente | `TIFLUX_*`, `VHSYS_*`, `N8N_WEBHOOK_SECRET` só em Settings |
| Audit | `log_action` → `audit_logs` em `auth.db` (ações hub: submit/approve/emit) |
| Upload assinado | PDF local com path UUID fora de web root; tipo/tamanho max (impl. O1.2) |
| Dry-run / gate fiscal | `HUB_DRY_RUN=true` (default) — ADR-0003 |

### Permissões hub (catálogo)

```
orcamentos | aprovar_orcamento | gerar_contrato | faturar | aprovar_fatura
```

Sincronizar BE (`permissions.py`) + FE (`PermissionKey`) na P0.5.  
`gerar_contrato` fica no catálogo já no MVP; **UI/fluxo O3 é fast-follow**.

---

## Consequências

**Positivo**

- Reusa auth, audit, clients e shell UI sem greenfield.
- Um deploy, um modelo mental operacional.
- Gap Guarda documentado; agentes param de puxar Supabase.

**Negativo / trade-offs**

- Sem RLS DB-level: falha de `Depends(require_permission)` = buraco — mitigar com testes 403 (P1.1).
- Dois SQLite (`auth.db` + `hub.db`): FKs cross-DB impossíveis; `created_by` / `approved_by` = IDs lógicos do auth, sem FK.

**Proibido neste ciclo**

- Criar projeto Supabase / migrar auth para JWT multi-tenant.
- Implementar O3 (contrato/follow-up/temperatura UI) dentro do MVP.
- Misturar Python + React + n8n no mesmo PR.

---

## Referências

- `ARQUITETURA.md`
- `.cursor/plans/hub_avs_management_guide_8941781e.plan.md`
- `docs/hub/README.md`
- `.estado_atual.md`
- ADR-0002 (modelo `hub.db`), ADR-0003 (HMAC / outbox / dry-run)
