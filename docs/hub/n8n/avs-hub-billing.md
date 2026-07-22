# F1.3 — Workflow n8n `avs-hub-billing`

**Status:** Spec pronta — import manual (JSON mínimo em `avs-hub-billing.workflow.json`)  
**Data:** 2026-07-20  
**Depende de:** ADR-0003, O2.1 (clients Go NF/CR), O2.2 (outbox + callback), F1.1 (API billing)  
**Escopo:** MVP faturamento (`billing.approved`, `billing.nf_prefeitura`). POSTs fiscais live só com `HUB_DRY_RUN=false` + aceite financeiro.

---

## 1. Objetivo

Receber webhook assinado do Management → emitir NF/CR/boleto VHSYS (ou CR líquido pós-prefeitura) → ticket TiFlux cobrança com 3 anexos → callback HMAC em `POST {APP_BASE_URL}/webhooks/n8n/callback`.

n8n **não** é SoT. IDs externos voltam no callback; Management grava em `billing_runs` + outbox `acked`.

**Branch retenção:** ocorre no Management, não no Switch n8n.

| Ação humana | Status local | Outbox |
|-------------|--------------|--------|
| `POST .../approve` sem `has_retencao` | `approved` | `billing.approved` → este workflow |
| `POST .../approve` com `has_retencao` | `awaiting_prefeitura` | **nenhum** (aguarda NF prefeitura) |
| `POST .../prefeitura` `{ nf_prefeitura_number, net_total }` | `approved` | `billing.nf_prefeitura` → este workflow |

---

## 2. Diagrama

```
Management approve / prefeitura
  → insert outbox pending (só se evento billing.*)
  → dispatch_outbox:
       HUB_DRY_RUN && !HUB_DRY_RUN_NOTIFY_N8N  →  sent (simulado, SEM HTTP)
       senão                                   →  POST N8N_BILLING_WEBHOOK_URL + X-AVS-Signature
            ↓
[Webhook] → [Verify HMAC raw] → [IF dry_run]
                                    ├─ true  → monta callback dry (sem VHSYS/TiFlux)
                                    └─ false → Switch(event)
                                         ├─ billing.approved
                                         │     → VHSYS NF + CR(+boleto|pix) → TiFlux ticket + 3 anexos → callback
                                         └─ billing.nf_prefeitura
                                               → VHSYS CR líquido (+boleto|pix) → ticket + anexos → callback
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
- Verificar **antes** de parse/Switch. Usar **bytes crus** do request (não `JSON.stringify` re-serializado).
- Webhook n8n: habilitar **Raw Body**; Code node compara header vs HMAC do binary/raw.

Referência código: `src/hub/hmac.py`, `src/hub/outbox.py` (`dispatch_outbox`, `_webhook_url_for_event` → billing), `src/hub/webhooks.py`.

---

## 4. Envelope JSON — Management → n8n

Fonte: `BillingService._outbox_payload` + `insert_pending` (`src/billing/service.py`, `src/hub/outbox.py`).

```json
{
  "event": "billing.approved",
  "resource_type": "billing_run",
  "resource_id": 15,
  "outbox_id": 22,
  "idempotency_key": "billing.approved:billing_run:15",
  "dry_run": true,
  "callback_url": "http://127.0.0.1:8000/webhooks/n8n/callback",
  "payload": {
    "billing_run": {
      "id": 15,
      "cnpj": "11222333000181",
      "client_name": "Cliente Exemplo",
      "tiflux_client_id": null,
      "vhsys_client_id": null,
      "competence": "2026-07",
      "due_date": "2026-07-25",
      "status": "approved",
      "has_retencao": false,
      "payment_method": "boleto",
      "gross_total": 1500.0,
      "net_total": 1500.0,
      "nf_prefeitura_number": null,
      "tiflux_ticket_number": null,
      "vhsys_nf_id": null,
      "vhsys_cr_id": null,
      "error_message": null,
      "approved_by": 1,
      "created_by": 1,
      "created_at": "2026-07-20T18:00:00+00:00",
      "updated_at": "2026-07-20T18:05:00+00:00",
      "approved_at": "2026-07-20T18:05:00+00:00",
      "sent_at": null,
      "items": [
        {
          "id": 1,
          "run_id": 15,
          "source": "contract",
          "external_ref": "C-100",
          "description": "Mensalidade monitoramento",
          "amount": 1500.0,
          "sort_order": 0
        }
      ],
      "artifacts": [
        {
          "id": 1,
          "run_id": 15,
          "kind": "report",
          "path_or_url": "data/hub_pdfs/report-15.pdf",
          "created_at": "2026-07-20T18:01:00+00:00"
        }
      ]
    },
    "has_retencao": false,
    "payment_method": "boleto"
  }
}
```

`billing.nf_prefeitura`: mesmo envelope; `event`/`idempotency_key` = `billing.nf_prefeitura`; `has_retencao` = `true`; `nf_prefeitura_number` e `net_total` preenchidos; **não** emitir NF VHSYS.

`callback_url` = `{APP_BASE_URL}/webhooks/n8n/callback` (sem barra final em `APP_BASE_URL`).

Flags espelhadas no topo de `payload` (`has_retencao`, `payment_method`) = atalho; fonte canônica = `payload.billing_run.*`.

---

## 5. Envelope JSON — n8n → Management (callback)

Fonte: `CallbackPayload` (`src/hub/callback_schemas.py`); efeito billing em `_apply_billing_external` (`src/hub/webhooks.py`).

### Sucesso (`billing.approved` live)

```json
{
  "event": "billing.approved",
  "resource_type": "billing_run",
  "resource_id": 15,
  "status": "ok",
  "outbox_id": 22,
  "external": {
    "tiflux_ticket_number": "99887",
    "vhsys_nf_id": "NF-4411",
    "vhsys_cr_id": "CR-2201"
  },
  "error_message": null,
  "dry_run": false
}
```

### Sucesso (`billing.nf_prefeitura` live)

```json
{
  "event": "billing.nf_prefeitura",
  "resource_type": "billing_run",
  "resource_id": 16,
  "status": "ok",
  "outbox_id": 23,
  "external": {
    "tiflux_ticket_number": "99888",
    "vhsys_nf_id": null,
    "vhsys_cr_id": "CR-2202"
  },
  "error_message": null,
  "dry_run": false
}
```

NF prefeitura **não** vira `vhsys_nf_id` — número humano já está em `billing_runs.nf_prefeitura_number`.

### Sucesso dry-run

```json
{
  "event": "billing.approved",
  "resource_type": "billing_run",
  "resource_id": 15,
  "status": "ok",
  "outbox_id": 22,
  "external": {
    "tiflux_ticket_number": null,
    "vhsys_nf_id": null,
    "vhsys_cr_id": null
  },
  "error_message": null,
  "dry_run": true
}
```

### Erro

```json
{
  "event": "billing.approved",
  "resource_type": "billing_run",
  "resource_id": 15,
  "status": "error",
  "outbox_id": 22,
  "external": null,
  "error_message": "VHSYS NF failed: HTTP 422",
  "dry_run": false
}
```

Efeito no Management:

| `status` | Outbox | `billing_runs` |
|----------|--------|----------------|
| `ok` | `acked` | `status=sent`, `sent_at`, grava `tiflux_ticket_number` / `vhsys_nf_id` / `vhsys_cr_id` se presentes |
| `error` | `error` + `last_error` | `status=error`, `error_message` (≤500) |

Respostas HTTP callback: `200` ack; `401` HMAC inválido; `400` payload inválido; `404` outbox inexistente; `413` body > 1 MiB.

---

## 6. Passos por `event`

### `billing.approved` (live, `dry_run=false`)

Caminho feliz **sem** retenção (`has_retencao=false` no envelope). Se `has_retencao=true` chegar aqui → callback `error` (Management não deveria enviar).

1. **VHSYS** `POST /notas-servico` — cliente (`vhsys_client_id` / CNPJ) + itens/`gross_total`. Guardar `vhsys_nf_id`.
2. **VHSYS** `POST /contas-receber` — valor = `net_total` ou `gross_total`; `tipo_conta` = `Boleto` se `payment_method=boleto` (Pix = flag excepcional — mapear enum VHSYS em ops). Guardar `vhsys_cr_id`; obter `link_boleto` se boleto.
3. Baixar/resolver PDFs: **relatório** (`artifacts` kind=`report`), **NF**, **boleto** (3 anexos obrigatórios — checklist).
4. **TiFlux** `POST /tickets` — mesa `TIFLUX_DESK_COBRANCA_ID` (**preencher após discovery**; não inventar no repo). Título/corpo: cliente + competência.
5. **TiFlux** `POST /tickets/{n}/files` ×3 — relatório + NF + boleto. Paths locais do Management só se volume compartilhado / URL assinada — **ops define**; se inacessível → callback `error` (não fingir sucesso sem anexos em live).
6. Opcional: `POST /tickets/{n}/answers` (template cobrança) — após template financeiro aprovado.
7. Callback `ok` com `external.vhsys_nf_id` + `vhsys_cr_id` + `tiflux_ticket_number`.

Paths Go (O2.0): NF/CR documentados; boleto via CR + `link_boleto`. Live = Unknown até smoke.

### `billing.nf_prefeitura` (live)

1. **Não** POST NF VHSYS. Usar `nf_prefeitura_number` + `net_total` do run.
2. **VHSYS** `POST /contas-receber` com valor **líquido** (`net_total`) + boleto/Pix conforme `payment_method`.
3. Anexos: relatório + PDF/cópia NF prefeitura (ops: artifact `nf` ou upload humano prévio) + boleto.
4. Ticket TiFlux cobrança + 3 anexos (idem acima).
5. Callback `ok` com `vhsys_cr_id` + `tiflux_ticket_number`; `vhsys_nf_id` = `null`.

### `dry_run=true` (qualquer event)

- **Não** POST VHSYS/TiFlux (zero POSTs fiscais).
- Callback imediato `status=ok`, `dry_run=true`, `external` nulos (ou eco de IDs já existentes no run).

---

## 7. Variáveis env (sem secrets inventados)

### Management (`.env` / Settings) — nomes reais em `.env.example`

| Variável | Uso |
|----------|-----|
| `HUB_DRY_RUN` | default `true` — sem POSTs externos |
| `HUB_DRY_RUN_NOTIFY_N8N` | default `false` — se `true` + dry-run, ainda POST n8n com `dry_run:true` |
| `N8N_BILLING_WEBHOOK_URL` | URL do Webhook deste workflow (vazia até import) |
| `N8N_COMMERCIAL_WEBHOOK_URL` | (outro fluxo; não usado aqui) |
| `N8N_WEBHOOK_SECRET` | HMAC bidirecional — **ops gera**; nunca commit |
| `APP_BASE_URL` | base do `callback_url` |
| `HUB_OUTBOX_MAX_ATTEMPTS` | default `5` |

### n8n (Credentials / env do runtime)

| Variável | Uso |
|----------|-----|
| `N8N_WEBHOOK_SECRET` | **mesmo valor** do Management |
| `TIFLUX_API_TOKEN` | credential TiFlux |
| `VHSYS_ACCESS_TOKEN` / `VHSYS_SECRET_ACCESS_TOKEN` | credential VHSYS |
| `TIFLUX_DESK_COBRANCA_ID` | mesa cobrança — **preencher após discovery** |
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
| `HUB_DRY_RUN=true`, `HUB_DRY_RUN_NOTIFY_N8N=true` + URL billing + secret | **Sim** (`dry_run:true`); n8n **não** POST externos |
| `HUB_DRY_RUN=false` + aceite financeiro | **Sim**; POSTs fiscais reais |

`HUB_DRY_RUN=false` sem aceite financeiro = **proibido** (NF/CR/boleto irreversíveis).

---

## 9. Import / ativação (ops)

1. Importar `avs-hub-billing.workflow.json` no n8n.
2. Ativar webhook → copiar Production URL → `N8N_BILLING_WEBHOOK_URL`.
3. Definir `N8N_WEBHOOK_SECRET` idêntico nos dois lados (mesmo do commercial).
4. Smoke: `HUB_DRY_RUN=true` + `HUB_DRY_RUN_NOTIFY_N8N=true` → approve run teste **sem** retenção → n8n log + callback `acked` + run `sent`.
5. Smoke retenção: approve c/ retenção → **sem** webhook; depois prefeitura → evento `billing.nf_prefeitura` + callback dry.
6. Live: só após smoke VHSYS NF/CR + TiFlux ticket/anexos + aceite financeiro; `HUB_DRY_RUN=false`.

JSON exportável = **esqueleto** (Webhook → HMAC Code → IF dry_run → Switch → Callback Code/HTTP). Nós HTTP VHSYS/TiFlux são placeholders: ops liga Credentials e mapeia body após smoke.

---

## 10. Aceite F1.3

- [ ] Workflow importado; URL em `N8N_BILLING_WEBHOOK_URL`
- [ ] HMAC inválido rejeitado no n8n
- [ ] Com notify dry-run (`billing.approved`): callback `ok` + outbox `acked` + run `sent`
- [ ] Sem notify: Management **não** chama n8n
- [ ] Approve com retenção **não** dispara webhook; prefeitura dispara `billing.nf_prefeitura`
- [ ] Live stubs: até wiring, callback `error` explícito (não POSTs silenciosos)

---

## Referências

- `docs/hub/ADR-0003-hmac-outbox-dry-run.md`
- `docs/hub/O2.0-api-go-nogo.md` (NF/CR/boleto)
- `docs/hub/ANALISE_PROJETO_AUTOMACAO.md`, `docs/hub/CHECKLIST_PRE_AUTOMACAO.md`
- `src/billing/service.py`, `src/hub/outbox.py`, `src/hub/webhooks.py`, `src/hub/callback_schemas.py`, `src/hub/hmac.py`
- Plano: `.cursor/plans/hub_avs_management_guide_8941781e.plan.md` §`avs-hub-billing`
