# Hub Comercial + Faturamento — Specs (SDD)

Índice das especificações versionadas no repo **avs-management**.  
Plano ativo: `.cursor/plans/hub_avs_management_guide_8941781e.plan.md`  
Estado: `.estado_atual.md`

**Proveniência das fontes:** pasta OneDrive `NFE/` (fora deste git), copiada em 2026-07-20.  
**Não copiado (de propósito):** `.tiflux_token`, `.vhsys_credentials`, áudio, frames, transcrições — permanecem em `NFE/`.

---

## Gap Guarda-Mestra / GUIA_MESTRE

| Item | Status |
|------|--------|
| `docs/GUIA_MESTRE.md` neste repo | **AUSENTE** |
| Guarda-Mestra (`.cursor/rules/000-guarda-mestra.mdc`) | Template Supabase/`org_id`/RLS — **não governa** este produto |
| Fonte arquitetural deste hub | `ARQUITETURA.md` + este diretório + plano hub |

**ADRs (P0.2 — feitos):**

| ADR | Arquivo | Decisão |
|-----|---------|---------|
| ADR-0001 | [ADR-0001-stack-hub.md](./ADR-0001-stack-hub.md) | FastAPI + SQLite hub; Guarda Supabase **não** governa; equiv. RBAC/HMAC/secrets/`log_action`/`HUB_DRY_RUN` |
| ADR-0002 | [ADR-0002-hub-db-model.md](./ADR-0002-hub-db-model.md) | Tabelas `hub.db` + contratos Quote/Billing/Outbox |
| ADR-0003 | [ADR-0003-hmac-outbox-dry-run.md](./ADR-0003-hmac-outbox-dry-run.md) | HMAC `X-AVS-Signature`, outbox, gate fiscal dry-run |

**Status MVP (2026-07-20):** P0–O2.2 + F1.1–F1.2 **feitos**; O2.3/F1.3 = spec + JSON import (wiring ops); O3 = **fast-follow**.  
**P1.1:** **GO dry-run** com ressalvas — veredicto em [P1-aceitacao-mvp.md](./P1-aceitacao-mvp.md) (38 pytest + `tsc`; smoke UI M1–M10 + live n8n pendentes). Live (`HUB_DRY_RUN=false`) = **NO-GO**.

---

## Escopo: MVP vs fast-follow

Ordem de entrega do plano: **P0 → O1 → O2 → F1** (MVP) → **O3** (fast-follow) → **P1** (QA/docs).

| Fase | Escopo | MVP? | Status | Specs |
|------|--------|------|--------|-------|
| **P0** | Estado, perms, `hub.db`, Settings/env | MVP | **done** (P0.1–P0.5) | este README + ADRs |
| **O1** | CRUD orçamento + UI + PDF local | MVP | **done** (O1.1–O1.5) | `MODULO_ORCAMENTO_CONTRATO.md` §2, sketches |
| **O2** | Clients + webhook commercial + n8n | MVP | O2.0–O2.2 **done**; O2.3 **spec/import** | `MODULO` §4 + `PRE_REQUISITOS.md` + `n8n/` |
| **F1** | Fila faturamento + n8n billing + retenção | MVP | F1.1–F1.2 **done**; F1.3 **spec/import** | `ANALISE` + checklist + sketch fat + `n8n/` |
| **O3** | Contrato TiFlux + follow-up + temperatura | **fast-follow** | fora do MVP | `MODULO` §2.5, §3, §8 O3 |
| **Timers n8n** (`avs-hub-timers`) | Cron follow-up / retry billing | **fast-follow** | fora do MVP | `PRE_REQUISITOS.md` Fluxo 3 |
| **P1** | Testes dry-run + aceite financeiro | MVP | P1.1 **GO dry-run** (ressalvas) | [P1-aceitacao-mvp.md](./P1-aceitacao-mvp.md) |

---

## Paths dos documentos

| Arquivo | Função |
|---------|--------|
| [ADR-0001-stack-hub.md](./ADR-0001-stack-hub.md) | Stack FastAPI/SQLite vs Guarda-Mestra |
| [ADR-0002-hub-db-model.md](./ADR-0002-hub-db-model.md) | Modelo `hub.db` + payloads |
| [ADR-0003-hmac-outbox-dry-run.md](./ADR-0003-hmac-outbox-dry-run.md) | HMAC + outbox + `HUB_DRY_RUN` |
| [MODULO_ORCAMENTO_CONTRATO.md](./MODULO_ORCAMENTO_CONTRATO.md) | Spec Orçamento → OS/ticket → Contrato |
| [PRE_REQUISITOS.md](./PRE_REQUISITOS.md) | Gates API TiFlux/VHSYS + desenho 2 fluxos n8n |
| [O2.0-api-go-nogo.md](./O2.0-api-go-nogo.md) | Matriz Go/No-Go endpoints (O2.0) — bloqueia O3 se sem contrato API |
| [n8n/](./n8n/) | O2.3 `avs-hub-commercial` + F1.3 `avs-hub-billing` — spec + JSON import esqueleto |
| [ANALISE_PROJETO_AUTOMACAO.md](./ANALISE_PROJETO_AUTOMACAO.md) | Análise as-is faturamento mensal + regras |
| [F1-lista-tiflux-faturamento.md](./F1-lista-tiflux-faturamento.md) | Lista `/faturamento` via histórico TiFlux + filtros (pending = No-Go) |
| [CHECKLIST_PRE_AUTOMACAO.md](./CHECKLIST_PRE_AUTOMACAO.md) | Checklist Go/No-go pré-automação billing |
| [P1-aceitacao-mvp.md](./P1-aceitacao-mvp.md) | P1.1 — aceite MVP dry-run (pytest + checklist UI) |
| [SPEC_CONSULTA_DOCUMENTOS.md](./SPEC_CONSULTA_DOCUMENTOS.md) | Busca orçamentos/PDFs/faturamentos por empresa ou ordem |
| [sketch-fluxo-completo.html](./sketch-fluxo-completo.html) | UI ref orçamento/comercial |
| [sketch-fluxo-faturamento.html](./sketch-fluxo-faturamento.html) | UI ref fila faturamento |
| `test-*.sh` / `verify-all.sh` | Probes API (creds via env — nunca commit) |

---

## Fila de PRs unitários (P0.3+)

Um especialista / um PR. Nunca Python + React + n8n juntos.

| PR | ID | Especialista | Entrega | Status |
|----|----|--------------|---------|--------|
| 1 | P0.3 | `@SQL.mdc` | DDL `hub.db` (7 tabelas) | **done** |
| 2 | P0.4 | `@python.mdc` | `HubDatabase` + Settings/`HUB_*`/`N8N_*` | **done** |
| 3a | P0.5a | `@python.mdc` | Perms `permissions.py` + seed | **done** |
| 3b | P0.5b | `@Typescript.mdc` | `PermissionKey` + Sidebar + routes | **done** |
| 4 | O1.1 | `@python.mdc` | CRUD `/orcamentos` | **done** |
| 5 | O1.2 | `@python.mdc` | PDF local UUID | **done** |
| 6 | O1.3 | `@UI.mdc`/`@Typescript.mdc` | Lista orçamentos | **done** |
| 7 | O1.4 | `@UI.mdc`/`@Typescript.mdc` | Wizard 3 passos | **done** |
| 8 | O1.5 | `@UI.mdc`/`@Typescript.mdc` | Modal cliente overlay | **done** (código) |
| 9 | O2.0 | `@searcher.mdc` | Validar POST APIs | **done** |
| 10 | O2.1 | `@python.mdc` | Extensões clients (só Go) | **done** |
| 11 | O2.2 | `@python.mdc`+`@security.mdc` | Outbox + HMAC + callback | **done** |
| 12 | O2.3 | n8n / ops | `avs-hub-commercial` | **spec/import** — wiring ops |
| 13 | F1.1 | `@python.mdc` | API billing | **done** |
| 14 | F1.2 | `@UI.mdc`/`@Typescript.mdc` | UI faturamento | **done** |
| 15 | F1.3 | n8n + callback | `avs-hub-billing` | **spec/import** — wiring ops |
| — | O3.* | — | **fast-follow** — fora do MVP | bloqueado (No-Go contrato API) |
| 16 | P1.1 | `@tester.mdc` | pytest + tsc dry-run | **GO dry-run** (ressalvas) |

### Mapeamento paths antigos (plano / NFE) → repo

| Citação no plano / NFE | Path estável no repo |
|------------------------|----------------------|
| `NFE/MODULO_ORCAMENTO_CONTRATO.md` | `docs/hub/MODULO_ORCAMENTO_CONTRATO.md` |
| `NFE/PRE_REQUISITOS.md` | `docs/hub/PRE_REQUISITOS.md` |
| `NFE/ANALISE_PROJETO_AUTOMACAO.md` | `docs/hub/ANALISE_PROJETO_AUTOMACAO.md` |
| `NFE/CHECKLIST_PRE_AUTOMACAO.md` | `docs/hub/CHECKLIST_PRE_AUTOMACAO.md` |
| `NFE/sketch-fluxo-completo.html` | `docs/hub/sketch-fluxo-completo.html` |
| `NFE/sketch-fluxo-faturamento.html` | `docs/hub/sketch-fluxo-faturamento.html` |
| `NFE/test-*.sh`, `verify-all.sh` | `docs/hub/` (mesmo nome) |
| `NFE/transcricao.*`, `frames/`, áudio | **fora do repo** — só em `NFE/` |

Fonte OneDrive (trabalho):  
`/Users/jean.nascimento/Library/CloudStorage/OneDrive-AVSTecnologia®/NFE/`

---

## Checklist de aceite — MVP

Alinhado ao plano §Critérios de aceite + fases P0–F1 (sem O3).  
**Fonte de veredicto P1.1:** [P1-aceitacao-mvp.md](./P1-aceitacao-mvp.md) · estado: `.estado_atual.md`

### P0 — Fundação
- [x] Specs neste `docs/hub/` (P0.1)
- [x] ADRs stack / hub.db / HMAC+outbox (P0.2)
- [x] Schema `hub.db` + bootstrap Settings/env (`HUB_*`, `N8N_*`, `HUB_DRY_RUN`) (P0.3→P0.4)
- [x] Permissões: `orcamentos`, `aprovar_orcamento`, `gerar_contrato`, `faturar`, `aprovar_fatura` (P0.5 BE+FE)

### O1 — Orçamento local
- [x] Orçamento salvo no Management sobrevive reload (O1.1 / O1.4)
- [x] Modal cadastro cliente overlay **não perde** itens do orçamento (O1.5 — código; smoke UI = ops)
- [x] Wizard 3 passos (cliente / itens implantação+mensalidade / revisão) + autosave (O1.4)
- [x] PDF local com path UUID fora de web root (O1.2)
- [x] Lista + nav/Dashboard com gates (O1.3); filtro temperatura UI = O3

### O2 — Comercial via n8n
- [x] `O2.0` Go: endpoints TiFlux/VHSYS validados (`O2.0-api-go-nogo.md`)
- [x] Submit dry-run → outbox + IDs simulados; **sem POST externo** (O2.2)
- [x] Webhook HMAC `X-AVS-Signature` + outbox + callback (O2.2)
- [ ] Fluxo n8n `avs-hub-commercial` — **spec + JSON import** em `n8n/`; wiring live = ops (O2.3)
- [x] Segredos ausentes do bundle frontend (server-side `.env`)

### F1 — Faturamento
- [x] Fila do mês API + UI: montar run, aprovar dry-run / branch prefeitura (F1.1 + F1.2)
- [x] Approve/prefeitura → outbox dry-run (pytest); ticket 3 anexos live = n8n (F1.3)
- [x] Input retenção: nº NF + valor líquido → `billing.nf_prefeitura` (F1.1)
- [ ] Fluxo n8n `avs-hub-billing` — **spec + JSON import** em `n8n/`; wiring live = ops (F1.3)
- [ ] `HUB_DRY_RUN=false` só após aceite financeiro explícito + O2.3/F1.3

### Segurança / RBAC (transversal MVP)
- [x] Usuário sem permissão: API 403 (pytest); nav FE gated (código — smoke UI ops)
- [x] Tokens TiFlux/VHSYS só server-side
- [x] `log_action` em approve/submit/emit (hub)

### P1 — QA MVP
- [x] pytest dry-run + RBAC 403 — **P1.1** 38 passed + `tsc --noEmit` OK ([P1-aceitacao-mvp.md](./P1-aceitacao-mvp.md))
- [x] Aceite dry-run documentado — **GO com ressalvas** (live = **NO-GO**)
- [ ] Smoke UI browser M1–M10 (ops)
- [ ] Stress/edge HMAC/outbox retry
- [ ] Aceite financeiro para `HUB_DRY_RUN=false` (após O2.3/F1.3)

---

## Checklist de aceite — fast-follow (O3 + timers)

**Não implementar no MVP.** O3 = **fast-follow** (bloqueado: API TiFlux sem POST contrato — O2.0 No-Go).

- [ ] Aprovar orçamento → UI revisão itens → gerar contrato TiFlux (`gerar_contrato`)
- [ ] Temperatura de lead + filtros na listagem
- [ ] Follow-up e-mail (sem resposta X dias) — Fluxo 3 timers ou Wait no commercial
- [ ] Gate: API create contract / stage confirmada em O2.0 antes de merge O3

---

## Ordem de handoff

1. ~~P0.1–P0.5 / O1.* / O2.0–O2.2 / F1.1–F1.2~~ — **feito**  
2. ~~P1.1 QA dry-run~~ — **GO com ressalvas** → [P1-aceitacao-mvp.md](./P1-aceitacao-mvp.md)  
3. **Próximos:** smoke UI M1–M10 (ops) · O2.3/F1.3 import n8n (ops) · O3 = fast-follow  
4. Estado vivo: `.estado_atual.md`

---

## Confidencialidade

- Nunca versionar JWT/tokens VHSYS, webhooks secrets, `.env` real.
- Scripts de probe usam `TIFLUX_TOKEN` / `VHSYS_*` via ambiente.
- Placeholders na doc: `[SUA_CHAVE_AQUI]` / env vars.
