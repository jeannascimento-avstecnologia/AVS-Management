# P1.1 — Aceite MVP dry-run (E2E)

**Data:** 2026-07-20  
**Tester:** `@tester.mdc`  
**Escopo:** MVP dry-run (hub local + outbox + HMAC). **Sem O3. Sem n8n live.**

`Guia+Plano lidos | spec: docs/hub | escopo: MVP E2E | passo: P1.1`

---

## Veredicto

| Campo | Valor |
|-------|--------|
| **GO / NO-GO** | **GO com ressalvas** |
| MVP E2E dry-run | **Aceito com ressalvas** |
| Live (`HUB_DRY_RUN=false`) | **NO-GO** — exige O2.3/F1.3 + aceite financeiro |

---

## 1. Automatizado (evidência)

### pytest (`.venv/bin/python`)

```text
tests/test_quotes.py
tests/test_hub_db.py
tests/test_hub_outbox.py
tests/test_billing.py
tests/test_auth_permissions.py
→ 38 passed (≈5.1s)
```

| Área | Resultado |
|------|-----------|
| hub.db schema / settings | PASS |
| quotes CRUD + templates + approve | PASS |
| PDF generate/download + 403 | PASS |
| submit/outbox dry-run + mark-sent | PASS |
| HMAC callback (valid / invalid / missing) | PASS |
| billing CRUD + artifacts | PASS |
| billing approve dry-run + retenção/prefeitura | PASS |
| RBAC hub keys + API 403 | PASS |

### TypeScript

```text
cd frontend && npx tsc --noEmit
→ exit 0 (sem erros)
```

---

## 2. Checklist manual curto (UI)

Pré-req: `npm run dev:local` (API `:8000` + Vite). Admin seed com all perms; user sem grant para gates.

| # | Passo | Esperado | Status P1.1 |
|---|-------|----------|-------------|
| M1 | Login admin | Sessão ok; Dashboard | ☐ ops (browser) |
| M2 | Sidebar/Dashboard → **Orçamentos** | Nav + card visíveis (`orcamentos`) | ☐ ops — **code OK** (Sidebar/Dashboard/`PermissionRoute`) |
| M3 | Criar orçamento → wizard 3 passos → autosave | Persiste após reload | ☐ ops — **API OK** (pytest CRUD) |
| M4 | Gerar PDF | Download UUID local | ☐ ops — **API OK** (pytest PDF) |
| M5 | Submit com `HUB_DRY_RUN=true` | Outbox `sent`/`simulated`; **sem POST externo** | ☐ ops — **API OK** (pytest outbox) |
| M6 | Sidebar/Dashboard → **Faturamento** | Nav + card (`faturar`) | ☐ ops — **code OK** |
| M7 | Criar run → Aprovar | Outbox billing dry-run | ☐ ops — **API OK** (pytest billing) |
| M8 | Run com retenção → Prefeitura | Status `awaiting_prefeitura` → NF | ☐ ops — **API OK** |
| M9 | User **sem** `orcamentos` / `faturar` | Sem nav; API 403 | ☐ ops — **API OK** (pytest 403) |
| M10 | User com `faturar` **sem** `aprovar_fatura` | Lista ok; botões Aprovar/NF gated | ☐ ops — **code OK** (`usePermission`) |

**Nota sessão P1.1:** API health `200` em `:8000`. Vite em conflito de porta nesta máquina — walkthrough browser **não executado** aqui; marcar M1–M10 quando ops fumaçar UI.

---

## 3. Fora de escopo (não bloqueia dry-run)

| Item | Status |
|------|--------|
| O3 contrato / temperatura UI / follow-up | **fora** |
| O2.3 n8n `avs-hub-commercial` live | **pendente** (esqueleto em `docs/hub/n8n/`) |
| F1.3 n8n `avs-hub-billing` live | **pendente** |
| `HUB_DRY_RUN=false` | **proibido** até aceite financeiro |

---

## 4. Gaps / ressalvas

| ID | Severidade | Descrição | Roteamento |
|----|------------|-----------|------------|
| G1 | Baixa (doc) | `docs/hub/README.md` checklist aceite ainda com boxes P0/O1 desatualizados | `@mapper.mdc` |
| G2 | Baixa (doc) | `.estado_atual.md` marcava O1.5 PENDENTE; dialog `QuoteClientRegisterDialog` **já existe** no FE — alinhar estado | estado atualizado em P1.1 |
| G3 | Média (ops) | Checklist manual UI (M1–M10) pendente de smoke browser | ops / `@tester` follow-up |
| G4 | Esperado | n8n commercial/billing não live | O2.3 / F1.3 |
| G5 | Info | Portas Vite/API conflictadas em `dev:local` nesta sessão | ops local |

**Bugs de código bloqueantes dry-run:** nenhum encontrado nesta rodada. Correções triviais: N/A.

---

## 5. Critérios de aceite negócio (dry-run)

| Critério | Evidência | OK? |
|----------|-----------|-----|
| Orçamentos + Faturamento na UI (nav/pages) | FE routes + gates no código; tsc OK | ✓ (UI smoke ops) |
| CRUD orçamento `hub.db` | pytest quotes + hub_db | ✓ |
| Submit dry-run → outbox, sem POST externo | pytest hub_outbox | ✓ |
| Fila faturamento + approve/prefeitura dry-run | pytest billing | ✓ |
| Perms gates (403 / FE) | pytest auth + code gates | ✓ (UI smoke ops) |
| Sem O3 | confirmado | ✓ |

---

## Handoff

- **GO dry-run** → ops pode fumaçar M1–M10 e seguir O2.3 / F1.3.
- Live fiscal/comercial: **NO-GO** até n8n + aceite financeiro.
- `@mapper.mdc`: sincronizar README checklist aceite com evidência P1.1.
