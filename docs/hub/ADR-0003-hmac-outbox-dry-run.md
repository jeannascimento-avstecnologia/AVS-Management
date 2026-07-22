# ADR-0003 — HMAC callbacks, outbox e gate `HUB_DRY_RUN`

**Status:** Aceito  
**Data:** 2026-07-20  
**Decisores:** Tech Lead (`@programador.mdc`)  
**Depende de:** ADR-0001, ADR-0002  
**Implementação:** O2.2 (`@python.mdc` + `@security.mdc`); n8n em O2.3 / F1.3

---

## Contexto

Management dispara trabalho assíncrono para n8n; n8n chama TiFlux/VHSYS e devolve IDs/status.  
Falhas de rede e retries exigem outbox. POSTs fiscais (NF/CR/boleto) são irreversíveis em produção.

---

## Decisão 1 — HMAC simétrico

### Header

`X-AVS-Signature: <hex HMAC-SHA256 do body raw>`

### Segredo

`N8N_WEBHOOK_SECRET` em Settings (nunca no FE). Mesmo segredo:

1. Management → n8n (assinatura na saída)
2. n8n → Management callback (verificação na entrada)

### Algoritmo

```
signature = HMAC_SHA256(key=secret, message=raw_body_bytes).hexdigest()
```

Comparação: `hmac.compare_digest` (timing-safe).  
Body parseado **depois** da verificação (usar bytes crus do request).

### Callback

- Path: `POST /webhooks/n8n/callback` (sem sessão usuário)
- Auth: HMAC obrigatório; IP allowlist opcional (`N8N_CALLBACK_ALLOWLIST`, fast-follow se não houver proxy estável)
- Resposta: `200` ack; `401` assinatura inválida; `400` payload inválido

### CallbackPayload (contrato)

```json
{
  "event": "quote.submit|quote.sent|quote.approved|billing.approved|billing.nf_prefeitura",
  "resource_type": "quote|billing_run",
  "resource_id": 1,
  "status": "ok|error",
  "outbox_id": 1,
  "external": {
    "tiflux_ticket_number": "string?",
    "vhsys_os_id": "string?",
    "vhsys_nf_id": "string?",
    "vhsys_cr_id": "string?",
    "tiflux_contract_ids": ["string?"]
  },
  "error_message": "string?",
  "dry_run": true
}
```

Callback `ok` → atualiza recurso + outbox `acked`.  
Callback `error` → outbox `error` + `error_message` no recurso (billing) / log.

---

## Decisão 2 — Outbox confiável

Tabela `webhook_outbox` (ADR-0002).

### Fluxo write-path (submit/approve)

1. Transação hub: muda status domínio **ou** marca intenção + insert outbox `pending` (mesmo commit lógico).
2. Após commit: HTTP POST webhook n8n com body = `payload_json` + header HMAC.
3. Se HTTP 2xx → outbox `sent`; se falha → permanece `pending`/`error`, `attempts++`, `last_error`.
4. Callback n8n → `acked` (+ campos externos).

### Eventos MVP

| event | Quando | Webhook URL Settings |
|-------|--------|----------------------|
| `quote.submit` | POST submit orçamento | `N8N_COMMERCIAL_WEBHOOK_URL` |
| `quote.sent` | mark-sent | commercial |
| `quote.approved` | approve (payload contrato = O3; MVP pode só status local) | commercial |
| `billing.approved` | approve fatura (sem retenção) | `N8N_BILLING_WEBHOOK_URL` |
| `billing.nf_prefeitura` | após input NF prefeitura | billing |

### Idempotency

`idempotency_key` UNIQUE, ex.: `{event}:{resource_type}:{resource_id}`.  
Re-submit do mesmo evento não cria segunda linha pending se já `sent`/`acked` (app decide replace vs reject).

### Retry

- Worker simples (cron/loop futuro) ou reenvio manual admin: só `pending`/`error` com `attempts < N` (N default 5 — Settings `HUB_OUTBOX_MAX_ATTEMPTS`).
- Não reenviar `acked`.

### Envelope outbound (Management → n8n)

```json
{
  "event": "quote.submit",
  "resource_type": "quote",
  "resource_id": 42,
  "outbox_id": 7,
  "idempotency_key": "quote.submit:quote:42",
  "dry_run": true,
  "callback_url": "https://management.../webhooks/n8n/callback",
  "payload": {
    "quote": { "...QuoteRead...": true },
    "pdf_path": "string?"
  }
}
```

Billing analogous: `payload.billing_run` + items + flags retenção/Pix.

---

## Decisão 3 — Gate `HUB_DRY_RUN`

### Default

`HUB_DRY_RUN=true` em `.env.example` e deploys iniciais.

### Comportamento quando `true`

| Ação | Permitido? |
|------|------------|
| CRUD local hub.db | Sim |
| Gerar PDF local | Sim |
| Insert outbox + log | Sim |
| HTTP POST n8n | **Opcional:** enviar com `dry_run:true` (n8n não POSTa externos) **ou** skip HTTP e só log — **escolher skip HTTP no MVP inicial** (mais seguro); flag `HUB_DRY_RUN_NOTIFY_N8N` se quiser eco |
| POST TiFlux/VHSYS a partir do Management | **Não** |
| POSTs fiscais (NF/CR/boleto) via n8n | **Não** (n8n respeita `dry_run` no payload) |

**Travado neste ADR:** com `HUB_DRY_RUN=true`, Management **não** chama POSTs externos TiFlux/VHSYS de domínio hub; outbox grava evento + `dry_run:true`; HTTP ao n8n **desligado** até ops habilitar notify (default off).

### Comportamento quando `false`

- Exige aceite financeiro explícito (checklist P1 / ops).
- POSTs reais via n8n; Management clients só se rota síncrona existir (preferir n8n).

### Settings novos (P0.4)

```
HUB_DB_PATH=data/hub.db
HUB_DRY_RUN=true
N8N_COMMERCIAL_WEBHOOK_URL=
N8N_BILLING_WEBHOOK_URL=
N8N_WEBHOOK_SECRET=
TIFLUX_DESK_COMERCIAL_ID=36089
HUB_OUTBOX_MAX_ATTEMPTS=5
HUB_PDF_DIR=data/hub_pdfs
```

---

## Auditoria

Usar `log_action` existente (`auth.db`):

| action | resource | quando |
|--------|----------|--------|
| `quote.submit` | `quote:{id}` | submit |
| `quote.approve` | `quote:{id}` | approve |
| `billing.approve` | `billing_run:{id}` | approve fatura |
| `billing.prefeitura` | `billing_run:{id}` | NF prefeitura |
| `webhook.callback` | `outbox:{id}` | callback (user pode ser sistema — se `log_action` exigir user, gravar email serviço ou estender depois) |

Sanitizar: nunca token/HMAC no `detail`.

---

## Critérios de aceite (impl. O2.2 — não P0.3)

- [ ] Assinar e verificar HMAC com body raw
- [ ] Outbox pending→sent→acked / error + idempotency
- [ ] `HUB_DRY_RUN=true` bloqueia POSTs externos
- [ ] Testes unitários signature + dry-run gate
- [ ] Segredo ausente → fail closed (não enviar unsigned)

---

## Referências

- Plano §Segurança, §n8n
- `PRE_REQUISITOS.md` (2 fluxos)
- ADR-0001, ADR-0002
