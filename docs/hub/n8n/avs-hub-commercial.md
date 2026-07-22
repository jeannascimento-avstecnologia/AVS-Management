# O2.3 — Workflow n8n `avs-hub-commercial`

**Status:** Spec pronta — import manual (JSON mínimo em `avs-hub-commercial.workflow.json`)  
**Data:** 2026-07-20  
**Depende de:** ADR-0003, O2.0, O2.1 (clients Go), O2.2 (outbox + callback)  
**Escopo:** MVP comercial (`quote.submit`, `quote.sent`). `quote.approved` → stub No-Go (O3).

---

## 1. Objetivo

Receber webhook assinado do Management → (opcional) criar OS VHSYS + ticket/anexo/stage TiFlux → callback HMAC em `POST {APP_BASE_URL}/webhooks/n8n/callback`.

n8n **não** é SoT. IDs externos voltam no callback; Management grava em `quotes` + outbox `acked`.

---

## 2. Diagrama

```
Management submit/mark-sent
  → insert outbox pending
  → dispatch_outbox:
       HUB_DRY_RUN && !HUB_DRY_RUN_NOTIFY_N8N  →  sent (simulado, SEM HTTP)
       senão                                   →  POST N8N_COMMERCIAL_WEBHOOK_URL + X-AVS-Signature
            ↓
[Webhook] → [Verify HMAC raw] → [IF dry_run]
                                    ├─ true  → monta callback dry (sem TiFlux/VHSYS)
                                    └─ false → Switch(event)
                                         ├─ quote.submit → VHSYS OS → TiFlux ticket → anexo PDF → callback ok|error
                                         ├─ quote.sent   → TiFlux update stage → callback
                                         └─ quote.approved → Error (O3 No-Go) → callback error
            ↓
HTTP POST callback_url + X-AVS-Signature (mesmo N8N_WEBHOOK_SECRET)
```

---

## 3. HMAC (obrigatório)

| Direção | Header | Algoritmo |
|---------|--------|-----------|
| Management → n8n | `X-AVS-Signature` | `HMAC-SHA256(secret, raw_body_bytes).hexdigest()` |
| n8n → Management | `X-AVS-Signature` | idem |

- Segredo: env `N8N_WEBHOOK_SECRET` (Settings Management **e** Credentials/env n8n). **Nunca** no FE / no JSON do workflow.
- Fail closed: secret ausente → Management não envia; n8n deve rejeitar (401/erro).
- Verificar **antes** de parse/Switch. Usar **bytes crus** do request (não `JSON.stringify` re-serializado — ordem de chaves quebra a assinatura).
- Webhook n8n: habilitar **Raw Body**; Code node compara header vs HMAC do binary/raw.

Referência código: `src/hub/hmac.py`, `src/hub/outbox.py` (`dispatch_outbox`), `src/hub/webhooks.py`.

---

## 4. Envelope JSON — Management → n8n (submit)

Fonte: `build_envelope` + `insert_pending` (`src/hub/outbox.py`); payload de `QuotesService.submit` / `mark_sent`.

```json
{
  "event": "quote.submit",
  "resource_type": "quote",
  "resource_id": 42,
  "outbox_id": 7,
  "idempotency_key": "quote.submit:quote:42",
  "dry_run": true,
  "callback_url": "http://127.0.0.1:8000/webhooks/n8n/callback",
  "payload": {
    "quote": {
      "id": 42,
      "cnpj": "00000000000000",
      "client_name": "Cliente Exemplo",
      "tiflux_client_id": null,
      "vhsys_client_id": null,
      "status": "submitted",
      "lead_temperature": null,
      "billed_by_type": null,
      "billed_by_name": null,
      "implant_payment_plan": null,
      "implant_discount_pct": null,
      "implant_discount_value": null,
      "monthly_payment_plan": null,
      "monthly_discount_pct": null,
      "monthly_discount_value": null,
      "tiflux_ticket_number": null,
      "vhsys_os_id": null,
      "pdf_path": "data/hub_pdfs/<uuid>.pdf",
      "created_by": 1,
      "created_at": "2026-07-20T18:00:00+00:00",
      "updated_at": "2026-07-20T18:00:00+00:00",
      "submitted_at": "2026-07-20T18:00:00+00:00",
      "sent_at": null,
      "approved_at": null,
      "items": []
    },
    "pdf_path": "data/hub_pdfs/<uuid>.pdf"
  }
}
```

`quote.sent`: mesmo envelope; `event`/`idempotency_key` = `quote.sent`; `quote.status` = `sent`; `sent_at` preenchido.

`callback_url` = `{APP_BASE_URL}/webhooks/n8n/callback` (sem barra final em `APP_BASE_URL`).

---

## 5. Envelope JSON — n8n → Management (callback)

Fonte: `CallbackPayload` (`src/hub/callback_schemas.py`).

### Sucesso (`quote.submit`)

```json
{
  "event": "quote.submit",
  "resource_type": "quote",
  "resource_id": 42,
  "status": "ok",
  "outbox_id": 7,
  "external": {
    "tiflux_ticket_number": "12345",
    "vhsys_os_id": "98765"
  },
  "error_message": null,
  "dry_run": false
}
```

### Sucesso dry-run (sem IDs reais)

```json
{
  "event": "quote.submit",
  "resource_type": "quote",
  "resource_id": 42,
  "status": "ok",
  "outbox_id": 7,
  "external": {
    "tiflux_ticket_number": null,
    "vhsys_os_id": null
  },
  "error_message": null,
  "dry_run": true
}
```

### Erro

```json
{
  "event": "quote.submit",
  "resource_type": "quote",
  "resource_id": 42,
  "status": "error",
  "outbox_id": 7,
  "external": null,
  "error_message": "VHSYS OS failed: HTTP 422",
  "dry_run": false
}
```

### `quote.sent` ok

```json
{
  "event": "quote.sent",
  "resource_type": "quote",
  "resource_id": 42,
  "status": "ok",
  "outbox_id": 8,
  "external": {
    "tiflux_ticket_number": "12345"
  },
  "error_message": null,
  "dry_run": false
}
```

Efeito no Management (`src/hub/webhooks.py`):

| `status` | Outbox | Quote |
|----------|--------|-------|
| `ok` | `acked` | atualiza `tiflux_ticket_number` / `vhsys_os_id` se presentes |
| `error` | `error` + `last_error` | sem update external |

Respostas HTTP callback: `200` ack; `401` HMAC inválido; `400` payload inválido; `404` outbox inexistente; `413` body > 1 MiB.

---

## 6. Passos por `event`

### `quote.submit` (live, `dry_run=false`)

1. **VHSYS** `POST /ordens-servico` — mapear cliente (`vhsys_client_id` / CNPJ) + itens do `payload.quote`. Guardar `vhsys_os_id`.
2. **TiFlux** `POST /tickets` — mesa `TIFLUX_DESK_COMERCIAL_ID` (default observado: `36089`). Título/corpo a partir de cliente + quote id.
3. **TiFlux** `POST /tickets/{n}/files` — anexar PDF se `pdf_path` disponível (n8n precisa ler arquivo via share/HTTP interno; path local do Management só funciona se n8n no mesmo host ou URL assinada — **ops define** `HUB_PDF_PUBLIC_BASE` / mount; MVP: path relativo + volume compartilhado ou skip anexo se inacessível + callback ok só com OS+ticket).
4. Callback `ok` com `external.vhsys_os_id` + `external.tiflux_ticket_number`.

### `quote.sent` (live)

1. Resolver `tiflux_ticket_number` do quote (já no envelope ou callback anterior).
2. **TiFlux** `PUT /tickets/{id}` com `stage_id` / `stage_name` (ID de estágio = **env n8n** `TIFLUX_STAGE_SENT_ID` — preencher após mapeamento manual; não inventar ID no repo).
3. Callback `ok`.

### `quote.approved`

**No-Go O3** (`docs/hub/O2.0-api-go-nogo.md`): sem `POST` contrato TiFlux.  
Workflow: ramo Switch → callback `status=error`, `error_message="quote.approved blocked (O3 No-Go: no create contract API)"`. Não chamar TiFlux/VHSYS.

### `dry_run=true` (qualquer event)

- **Não** POST TiFlux/VHSYS.
- Callback imediato `status=ok`, `dry_run=true`, `external` nulos (ou eco dos campos já existentes no quote).

---

## 7. Variáveis env (sem secrets inventados)

### Management (`.env` / Settings) — nomes reais em `.env.example`

| Variável | Uso |
|----------|-----|
| `HUB_DRY_RUN` | default `true` — sem POSTs externos |
| `HUB_DRY_RUN_NOTIFY_N8N` | default `false` — se `true` + dry-run, ainda POST n8n com `dry_run:true` |
| `N8N_COMMERCIAL_WEBHOOK_URL` | URL do Webhook deste workflow (vazia até import) |
| `N8N_BILLING_WEBHOOK_URL` | (outro fluxo; não usado aqui) |
| `N8N_WEBHOOK_SECRET` | HMAC bidirecional — **ops gera**; nunca commit |
| `APP_BASE_URL` | base do `callback_url` |
| `HUB_OUTBOX_MAX_ATTEMPTS` | default `5` |
| `HUB_PDF_DIR` | path PDF local |
| `TIFLUX_DESK_COMERCIAL_ID` | default `36089` (observado) |

### n8n (Credentials / env do runtime)

| Variável | Uso |
|----------|-----|
| `N8N_WEBHOOK_SECRET` | **mesmo valor** do Management |
| `TIFLUX_API_TOKEN` | credential TiFlux (já usada no Management; não duplicar no git) |
| `VHSYS_ACCESS_TOKEN` / `VHSYS_SECRET_ACCESS_TOKEN` | credential VHSYS |
| `TIFLUX_DESK_COMERCIAL_ID` | alinhar com Management (`36089` se mesa Comercial) |
| `TIFLUX_STAGE_SENT_ID` | estágio kanban pós mark-sent — **preencher após discovery** |
| `TIFLUX_API_BASE` | default `https://api.tiflux.com/api/v2` |
| `VHSYS_API_BASE` | default `https://api.vhsys.com/v2` |

Valores vazios no `.env.example` permanecem vazios neste doc. Não há secret de exemplo.

---

## 8. Nota dry-run (Management)

Travado ADR-0003 + `dispatch_outbox`:

```
if (HUB_DRY_RUN || envelope.dry_run) and not HUB_DRY_RUN_NOTIFY_N8N:
    outbox → sent  # simulado
    # SEM HTTP ao n8n
```

| Cenário | n8n recebe webhook? |
|---------|---------------------|
| `HUB_DRY_RUN=true`, `HUB_DRY_RUN_NOTIFY_N8N=false` (default) | **Não** |
| `HUB_DRY_RUN=true`, `HUB_DRY_RUN_NOTIFY_N8N=true` + URL + secret | **Sim** (`dry_run:true`); n8n **não** POST externos |
| `HUB_DRY_RUN=false` + aceite ops | **Sim**; POSTs reais |

---

## 9. Import / ativação (ops)

1. Importar `avs-hub-commercial.workflow.json` no n8n.
2. Ativar webhook → copiar Production URL → `N8N_COMMERCIAL_WEBHOOK_URL`.
3. Definir `N8N_WEBHOOK_SECRET` idêntico nos dois lados.
4. Smoke: `HUB_DRY_RUN=true` + `HUB_DRY_RUN_NOTIFY_N8N=true` → submit orçamento teste → n8n log + callback `acked`.
5. Live: só após smoke TiFlux/VHSYS + aceite; `HUB_DRY_RUN=false`.

JSON exportável = **esqueleto** (Webhook → HMAC Code → IF dry_run → Switch → Callback Code/HTTP). Nós HTTP TiFlux/VHSYS são placeholders: ops liga Credentials e mapeia body após smoke.

---

## 10. Aceite O2.3

- [ ] Workflow importado; URL em `N8N_COMMERCIAL_WEBHOOK_URL`
- [ ] HMAC inválido rejeitado no n8n
- [ ] Com notify dry-run: callback `ok` + outbox `acked`
- [ ] Sem notify: Management **não** chama n8n
- [ ] `quote.approved` → callback error (No-Go O3), sem POST contrato

---

## Referências

- `docs/hub/ADR-0003-hmac-outbox-dry-run.md`
- `docs/hub/O2.0-api-go-nogo.md`
- `src/hub/outbox.py`, `src/hub/webhooks.py`, `src/hub/callback_schemas.py`, `src/hub/hmac.py`
- Plano: `.cursor/plans/hub_avs_management_guide_8941781e.plan.md` §`avs-hub-commercial`
