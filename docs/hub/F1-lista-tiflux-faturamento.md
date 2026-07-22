# F1 — Lista inicial de faturamento via TiFlux

**Status:** MVP  
**Data:** 2026-07-20  
**Declaração:** `Guia+Plano lidos | spec: docs/hub/F1-lista-tiflux-faturamento.md | escopo: MVP`  
**Plano:** `.cursor/plans/hub_avs_management_guide_8941781e.plan.md` (fila no Management; pending/faturar = No-Go)

## Problema

A página `/faturamento` listava só `billing_runs` locais e obrigava montar a fila buscando cliente → contratos. A operação espera ver **dados de faturamento do TiFlux** com filtros (dia/período, empresa).

## Capacidade TiFlux (evidência live + OpenAPI 2026-07-20)

| Endpoint | Status | Uso |
|----------|--------|-----|
| `GET /reports/billings/history` | **Go** | Campos de faturamento (data, cliente, valor, vencimento, NFe, paid/reversal) |
| Params history: `billing_start_date`, `billing_end_date`, `due_start_date`, `due_end_date`, `client_id`, `_type` (`billed`\|`reversed`\|`paid`), `nfe_number`, `ticket_number`, `offset`, `limit` | **Go** | Filtros de período/dia e empresa |
| `GET /contracts` (`status=actives`, `client_ids`) | **Go** | Itens para **criar** `billing_run` |
| `GET /reports/billings/pending` (+ variantes) | **No-Go** (404) | Sem “faturamentos pendentes” / faturar na API v2 |

**Mapeamento escolhido (workaround oficial do plano):**

1. **Lista inicial** = histórico TiFlux (`/reports/billings/history`) filtrado por dia ou competência + cliente.
2. **Montar fila** = contratos ativos do cliente → `POST /faturamento/runs` (fluxo approve/outbox inalterado).
3. **Filas locais** = `billing_runs` (status Management / n8n), secundário na UI.

## API Management (proxy server-side)

Token TiFlux **nunca** no frontend.

| Método | Path | Filtros |
|--------|------|---------|
| `GET` | `/faturamento/tiflux/history` | `billing_day` (YYYY-MM-DD) **ou** `competence` (YYYY-MM) → range; `client_id`; `billing_type`; `due_start_date`/`due_end_date`; `limit`/`offset` |
| `GET` | `/faturamento/tiflux/contracts` | `client_id?`; `status` (default `actives`); `limit`/`offset`; `competence?` → anexa `local_run_id` se existir run para cliente+competência |
| `GET` | `/faturamento/tiflux/clients` | (já existe) autocomplete |
| `GET` | `/faturamento/tiflux/clients/{id}/contracts` | (já existe) |

## UI `/faturamento`

- Aba **TiFlux**: tabela do histórico com filtros dia / competência / cliente / tipo.
- Aba **Filas locais**: `billing_runs` (comportamento anterior).
- **Nova fila**: busca cliente → contratos ativos → cria run (sem regressão).

## Fora de escopo (fast-follow)

- Espelhar “faturar” no TiFlux (RPA / endpoint futuro).
- Pending quando a API passar a existir — substituir mapeamento history→queue.

## Aceite

- [x] `/faturamento` mostra linhas do histórico TiFlux com filtro período/dia + cliente.
- [x] Criar/aprovar `billing_runs` continua funcional.
- [x] pytest nos novos endpoints; tipagem FE sem `any`.
