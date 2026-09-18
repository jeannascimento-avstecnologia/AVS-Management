# Guia Mestre — AVS Management

> Fonte de verdade operacional deste repositório. Substitui qualquer guardrail herdado de outro produto (Planner/Supabase).

## Stack real (inegociável)

- **Backend:** FastAPI + Pydantic v2 + SQLite (`data/auth.db` sessão/RBAC; `data/hub.db` domínio comercial).
- **Frontend:** React + TypeScript + Vite + TanStack Query + shadcn/ui.
- **Integrações:** TiFlux API v2 e VHSYS API v2 — tokens **somente server-side** (`Settings` / `.env`).
- **Orquestração:** n8n via outbox HMAC (`avs-hub-commercial`, `avs-hub-billing`). Sem back-end separado além do FastAPI deste repo.
- **Sem** Supabase, Edge Functions, RLS/`org_id` ou pgTAP neste produto.

## Pre-flight

1. Ler este guia.
2. Ler o plano ativo em `.cursor/plans/` (hub comercial = `hub_avs_management_guide_8941781e.plan.md`).
3. SDD: spec aprovada em `docs/` (hub em `docs/hub/`). Sem spec → escrever/atualizar **antes** do código.
4. Segredos nunca no cliente; uploads/PDF fora da web root.
5. Declarar: `Guia+Plano lidos | spec: <arquivo> | escopo: MVP|fast-follow`.

## Inegociáveis do hub

- Toda mutação privilegiada de integração (TiFlux/VHSYS) passa pelo FastAPI. Frontend só chama `/orcamentos/*`, `/faturamento/*`, etc.
- Schema SQLite: colunas novas via `ALTER TABLE` idempotente em `src/hub/models.py` **e** `docs/hub/schema/hub_v1.sql`.
- Permissões RBAC (`PERMISSION_ORCAMENTOS`, …) + `log_action` em mutações.
- TypeScript sem `any` novo; Pydantic v2 sem `Any` de payload quando existir schema.
- `quote.status` (orçamento) e `ticket_link_status` (vínculo TiFlux) são dimensões **independentes**.
- Fast-follow do hub (contrato TiFlux create, audit log avançado, rollup) não entra no MVP de orçamento local.

## Estilo

Caveman: conciso, direto. Não reescrever código inalterado. Questionar rota inferior antes de seguir.
