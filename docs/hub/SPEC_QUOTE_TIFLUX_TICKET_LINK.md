# Spec — Vínculo de ticket TiFlux em orçamentos

> Status: aprovada para implementação (fast-follow) · 2026-09-18  
> Plano: `.cursor/plans/hub_avs_management_guide_8941781e.plan.md` (O3 subescopo)  
> Relacionado: `MODULO_ORCAMENTO_CONTRATO.md`  
> Declaração: `Guia+Plano lidos | spec: docs/hub/SPEC_QUOTE_TIFLUX_TICKET_LINK.md | escopo: fast-follow`

## 0) Contrato TiFlux (OpenAPI v2 — confirmado)

Fontes:

- https://api.tiflux.com/api/v2/ (OpenAPI)
- https://guia-de-uso.tiflux.com/integracoes/api-tiflux/api-v2/consulta-de-dados-requisicoes-do-tipo-get.md
- https://guia-de-uso.tiflux.com/integracoes/api-tiflux/api-v2/autenticacao.md
- https://guia-de-uso.tiflux.com/integracoes/api-tiflux/api-v2/insercao-de-dados-requisicoes-do-tipo-post.md

| Ponto | Valor confirmado |
|-------|------------------|
| Ticket unitário | `GET /tickets/{ticket_number}` — **não** existe `?ticket_number=` |
| 200 | objeto do ticket (não envelopado nos exemplos oficiais; tolerar `{"ticket": {...}}`) |
| 404 | ticket inexistente |
| 403 | autenticado sem permissão/licença Tickets — **não** tratar como 404 |
| Auth | `Authorization: Bearer {token}` (mesmo token `Settings.tiflux_api_token`) |
| Fechado | `is_closed: boolean`. `status` é `{id, name, default_close, …}`. `sla_info.solved_in_time` = SLA, **não** fechamento |
| Catálogo | `services_catalog` → `{id, item_name, area_name, catalog_name}`. Comparar **`item_name`** com `"3 - Aprovado"` ou `"Aprovado"` (não `Reprovado`) |
| Listagem | `GET /tickets` com `offset` (página, default 1), `limit` 20–200. Filtros: `client_ids`, `desk_ids` (CSV, máx. 15). Sem filtro por número. Retry 429 + `Retry-After` |

Inventário SQL n8n **não** é fonte de verdade para status/catálogo.

## 1) Objetivo

Na lista de orçamentos, vincular um ticket TiFlux por número, persistir o vínculo, classificar `novo|aprovado|rejeitado` em tempo real e **excluir terminais da contagem de lead**.

`ticket_link_status` ≠ `quote.status`.

## 2) Persistência (`quotes`)

Reutilizar `tiflux_ticket_number`. Colunas novas:

| Coluna | Semântica |
|--------|-----------|
| `ticket_link_status` | `novo` \| `aprovado` \| `rejeitado` \| `NULL` (sem vínculo) |
| `ticket_link_checked_at` | ISO8601 da última verificação |
| `ticket_link_catalog` | último `item_name` lido |
| `ticket_link_snapshot_json` | preview (número, título, cliente, status, catálogo, closed, suggested) para reabrir o dialog sem consultar tickets terminais |

Backfill: quotes com `tiflux_ticket_number` e status NULL → `novo`.  
Callback n8n que grava número: `ticket_link_status = COALESCE(ticket_link_status, 'novo')`.

Constante: `APPROVED_CATALOG_LABEL = "3 - Aprovado"`.

Regras: não fechado → `novo`; fechado + catálogo `3 - Aprovado` **ou** `item_name` `Aprovado` (não `Reprovado`) → `aprovado`; fechado caso contrário → `rejeitado`.

## 3) API hub (`PERMISSION_ORCAMENTOS`)

| Método | Rota | Comportamento |
|--------|------|----------------|
| GET | `/orcamentos/tiflux/tickets` | Lista mesa Comercial + cliente (`client_id`). 422 sem cliente; 503 sem token |
| GET | `/orcamentos/tiflux/tickets/{ticket_number}` | Preview. 404 inexistente; 503 sem token; 403 TiFlux |
| GET | `/orcamentos/{id}/ticket-defaults` | Prefill criar ticket: mesa Comercial, catálogo/prioridade da mesa, solicitantes do cliente, título/descrição do orçamento. 422 sem `tiflux_client_id`; 503 sem token/mesa |
| POST | `/orcamentos/{id}/ticket` | Body `{ticket_number}`. GET + classifica + persiste + snapshot |
| POST | `/orcamentos/{id}/ticket/create` | `POST /tickets` TiFlux (mesa Comercial) + vínculo imediato. 409 se já houver ticket; 422 sem cliente. Token só no backend |
| DELETE | `/orcamentos/{id}/ticket` | Zera número + 4 colunas de vínculo |
| POST | `/orcamentos/refresh-ticket-links` | Body `{quote_ids}`. Servidor **só** consulta os que estão `novo`. Paralelo, 1 client HTTP, throttle. Falha parcial → `failures[]` |

## 4) UI

- Botão **Associar a um Ticket** após PDF; vinculado: `#número` + flag no mesmo slot.
- Dialog **Associar**: ao abrir, lista automática `GET /tickets?client_ids={quote.tiflux_client_id}&desk_ids={TIFLUX_DESK_COMERCIAL_ID}`. Clique seleciona; 1 resultado pré-seleciona. Fallback: buscar por número. Sem `tiflux_client_id`: pedir cliente no wizard.
- Vinculado: snapshot + Trocar / Desvincular.
- Ordem: sem ticket → novo → aprovado → rejeitado (estável).
- Filtro `linkFilter`: todos / sem / com (`novo`) / aprovados / rejeitados.
- Ao abrir a tela: refresh 1× por assinatura `quote_id:ticket_number` só nos `novo`.
- Pipeline (`quoteLead.ts` + filtro lead backend) **exclui** `aprovado`/`rejeitado`.
- Wizard **passo 2 (Revisão)**, ao final: **Associar Ticket** (mesmo dialog da lista) e **Criar ticket**. Vinculado: `#número` + flag no lugar de Associar; Criar some.

## 5) Criar ticket (wizard passo 2)

`POST /tickets` oficial (title, description, `client_id`, `desk_id`, opcionais `services_catalogs_item_id`, `priority_id`, `requestor_id`). **Multipart/form-data** — JSON dispara Rails wrap `:ticket` (40001). Catálogo e solicitante: dropdown com busca, abre no clique da barra.

Prefill (editável no dialog):

| Campo | Fonte |
|-------|--------|
| Mesa | `TIFLUX_DESK_COMERCIAL_ID` (somente leitura) |
| Catálogo | `GET /desks/{id}/services-catalogs-items` — default item `1 -` / Triagem (nunca `3 - Aprovado`) |
| Prioridade | `GET /desks/{id}/priorities` — default Baixa/Low senão a de menor `order` |
| Cliente | `quote.tiflux_client_id` |
| Solicitante | primeiro `GET /clients/{id}/requestors` |
| Título | `quote.title` ou `Orçamento M{id} — {cliente}` |
| Descrição | resumo local (id, cliente, CNPJ, totais) |

Após 201/200 TiFlux: classificar + `link_ticket` (mesmo caminho do Associar). `quote.status` não muda.

## 6) Fora de escopo

- Mudar `quote.status` automaticamente.
- Consultar TiFlux para vínculos já terminais.
- Usar inventário n8n.
- Fechar ticket por esta tela.
- Criar contrato TiFlux (O3 No-Go).
