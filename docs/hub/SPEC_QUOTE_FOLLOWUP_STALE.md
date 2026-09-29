# Spec — Destaque de orçamento enviado sem retorno no TiFlux

> Status: aprovada para implementação (fast-follow) · 2026-09-29  
> Plano: `.cursor/plans/hub_avs_management_guide_8941781e.plan.md` (O3, só o destaque; sem e-mail)  
> Relacionado: `SPEC_QUOTE_TIFLUX_TICKET_LINK.md`  
> Declaração: `Guia+Plano lidos | spec: docs/hub/SPEC_QUOTE_FOLLOWUP_STALE.md | escopo: fast-follow`

## 1) Objetivo

Na lista de orçamentos, destacar os enviados cujo ticket TiFlux aberto está sem movimentação há 5 dias ou mais.

`quote.status` e `ticket_link_status` continuam dimensões independentes. Inatividade não muda nenhum dos dois.

## 2) Elegibilidade

As três condições juntas:

| Condição | Valor |
|----------|--------|
| `quote.status` | `sent` |
| ticket | número preenchido e `ticket_link_status = novo` |
| relógio | `ticket_activity_at` ou, se vazio, `sent_at`, com idade ≥ 5 dias |

Fora: rascunho, submetido, aprovado, rejeitado, contratado, ticket `aprovado`/`rejeitado`, enviado sem ticket, enviado há menos de 5 dias.

Não usar `quotes.updated_at`. Refresh do vínculo e edição local mexem nesse campo.

Constante: `FOLLOWUP_STALE_DAYS = 5`. Idade em dias inteiros (`floor` de segundos / 86400).

Campos calculados na leitura (`QuoteRead`), sem cron:

| Campo | Semântica |
|-------|-----------|
| `followup_stale` | `true` só quando elegível e idade ≥ 5 |
| `followup_idle_days` | dias desde a âncora quando elegível; `null` fora |

## 3) Persistência (`quotes`)

| Coluna | Semântica |
|--------|-----------|
| `ticket_activity_at` | ISO8601 da última movimentação considerada |
| `ticket_activity_fingerprint` | catálogo + responsável + estágio + status |

ALTER idempotente em `src/hub/models.py` e colunas em `docs/hub/schema/hub_v1.sql`.

Vincular ou desvincular zera as duas colunas.

## 4) Sinal (mesmo GET do refresh)

`POST /orcamentos/refresh-ticket-links` já consulta `GET /tickets/{n}` nos vínculos `novo`. Sem request extra.

Do payload:

- timestamp: primeiro preenchido entre `updated_at`, `last_update`, `created_at`
- fingerprint: `services_catalog.item_name`, responsável (`responsible_id` ou `responsible`), estágio (`stage` / `stage_name`), `status.name`

No apply:

- fingerprint mudou (catálogo, responsável, estágio ou status) → `ticket_activity_at` = agora. O `updated_at` antigo do ticket não segura o relógio.
- fingerprint igual e timestamp mais novo → avança (resposta que só bumpa `updated_at`)
- fingerprint igual e timestamp igual ou ausente → não avança (o GET da lista não é movimentação)
- falha TiFlux → mantém o valor anterior

`mark-sent` com ticket vinculado grava baseline `ticket_activity_at = sent_at` e o fingerprint depois do PUT (estágio/responsável que o hub gravou). Dry-run usa o mesmo baseline sem HTTP. Os 5 dias contam a partir do envio.

## 5) UI

Card elegível: borda de alerta e badge `Sem retorno há N dias` ao lado do status do orçamento.

Faixas de ticket e a ordem da spec de vínculo não mudam. Sem aba nova.

## 6) Mock local

`QUOTE_FOLLOWUP_MOCK=1` (default off). Com o flag, `GET` dos números `9001`–`9004` devolve payload fixo e não chama a API. Outros números seguem o fluxo normal.

`python scripts/seed_quote_followup_mock.py` grava no `hub.db`:

| Número | Cenário | Destaque depois do refresh |
|--------|---------|----------------------------|
| 9001 | enviado há 8 dias, fingerprint parado | sim |
| 9002 | enviado há 8 dias, `updated_at` de ontem | não |
| 9003 | enviado há 2 dias, sem movimento | não |
| 9004 | enviado há 10 dias, ticket fechado aprovado | não |

## 7) Fora

- e-mail / cron n8n
- mudar `quote.status` por inatividade
- `GET /tickets/{n}/answers`
- consultar tickets terminais
