# ADR-0002 — Modelo de dados `hub.db`

**Status:** Aceito  
**Data:** 2026-07-20  
**Decisores:** Tech Lead (`@programador.mdc`)  
**Depende de:** ADR-0001  
**Próximo implementador:** `@SQL.mdc` (P0.3) — DDL apenas; sem rotas/UI

---

## Contexto

Management é SoT de orçamentos e fila de faturamento. TiFlux/VHSYS são projeções.  
Specs: `MODULO_ORCAMENTO_CONTRATO.md` §5, plano §Modelo de dados, `ANALISE_PROJETO_AUTOMACAO.md` (regras retenção/Pix).

Path: `HUB_DB_PATH` (default `data/hub.db`). Bootstrap no startup espelhando `AuthDatabase._init_schema` (P0.4).

---

## Decisão — tabelas MVP

### Convenções

- Tipos SQLite: `INTEGER` PK autoincrement, `TEXT` ISO-8601 UTC, `REAL` dinheiro, `INTEGER` 0/1 boolean.
- `PRAGMA foreign_keys = ON`.
- Sem `org_id`. Soft-delete: **não** no MVP (delete físico só draft vazio, se necessário).
- Índices mínimos: status, competence, client refs, outbox status.
- Status **canônicos** = plano (não aliases `os_created`/`ticket_open` do MODULO — mapear só se UI legado precisar).

---

### 1. `quotes`

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | INTEGER PK | |
| `cnpj` | TEXT NOT NULL | 14 dígitos |
| `client_name` | TEXT | display |
| `tiflux_client_id` | INTEGER NULL | |
| `vhsys_client_id` | INTEGER NULL | |
| `status` | TEXT NOT NULL | ver enum |
| `lead_temperature` | TEXT NULL | coluna OK no MVP; **filtro UI = O3** |
| `billed_by_type` | TEXT NULL | `distribuidor` \| `fornecedor` |
| `billed_by_name` | TEXT NULL | |
| `active_quote_version_id` | INTEGER NULL | FK lógica → `quote_versions.id` |
| `current_version_number` | INTEGER NULL | último `vX` criado |
| `monthly_draft_json` | TEXT NULL | rascunho mensalidades antes do snapshot |
| `implant_payment_plan` | TEXT NULL | ex. `3x_sem_juros` |
| `implant_discount_pct` | REAL NULL | |
| `implant_discount_value` | REAL NULL | |
| `monthly_payment_plan` | TEXT NULL | |
| `monthly_discount_pct` | REAL NULL | |
| `monthly_discount_value` | REAL NULL | |
| `modules_json` | TEXT NULL | JSON array `QuoteModule` (SoT passo 2); flat `implant_*`/`monthly_*` = espelho legado |
| `tiflux_ticket_number` | TEXT NULL | preenchido via callback |
| `vhsys_os_id` | TEXT NULL | |
| `pdf_path` | TEXT NULL | UUID filename; fora web root |
| `created_by` | INTEGER NULL | user id auth (lógico) |
| `created_at` | TEXT NOT NULL | |
| `updated_at` | TEXT NOT NULL | |
| `submitted_at` | TEXT NULL | |
| `sent_at` | TEXT NULL | |
| `approved_at` | TEXT NULL | |

**`status`:** `draft` \| `submitted` \| `sent` \| `approved` \| `rejected` \| `contracted`

- `submitted` = OS+ticket disparados (ou dry-run aceito)
- `contracted` = O3; coluna/enum reservados no MVP

---

### 2. `quote_items`

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | INTEGER PK | |
| `quote_id` | INTEGER NOT NULL FK → quotes ON DELETE CASCADE | |
| `section` | TEXT NOT NULL | `module.id` (livre; seed + custom) |
| `name` | TEXT NOT NULL | |
| `qty` | REAL NOT NULL DEFAULT 1 | |
| `unit_value` | REAL NOT NULL DEFAULT 0 | |
| `total_value` | REAL NOT NULL | qty * unit (app calcula; DB armazena) |
| `template_key` | TEXT NULL | |
| `sort_order` | INTEGER NOT NULL DEFAULT 0 | |

Índice: `(quote_id, section, sort_order)`.

---

### 2b. `quote_versions`

Snapshot imutável por clique em **Salvar orçamento**. Spec: `SPEC_MENSALIDADES_VERSOES_PDF.md`.

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | INTEGER PK | |
| `quote_id` | INTEGER NOT NULL FK → quotes ON DELETE CASCADE | |
| `version_number` | INTEGER NOT NULL | `v1`, `v2`… UNIQUE `(quote_id, version_number)` |
| `snapshot_modules_json` | TEXT NOT NULL | canvas |
| `snapshot_items_json` | TEXT NOT NULL | itens com `id` |
| `snapshot_notes` | TEXT NULL | |
| `snapshot_monthly_json` | TEXT NULL | charges + `license_item_ids` |
| `pdf_path` | TEXT NULL | UUID filename desta versão |
| `created_at` / `updated_at` | TEXT NOT NULL | |

Índice: `quote_id`.

---

### 3. `quote_templates`

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | INTEGER PK | |
| `key` | TEXT NOT NULL UNIQUE | |
| `name` | TEXT NOT NULL | |
| `section` | TEXT NOT NULL | `module.id` (livre) |
| `lines_json` | TEXT NOT NULL | JSON array de linhas default |
| `created_at` | TEXT NOT NULL | |

**Contrato `lines_json` (elemento):**

```json
{
  "name": "string",
  "qty": 1.0,
  "unit_value": 0.0,
  "sort_order": 0
}
```

Modelos de **itens** dentro de um módulo já presente no orçamento.

---

### 3b. `quote_module_templates`

Catálogo de **módulos** reutilizáveis (blocos custom). Implantação/Mensalidade continuam como presets de sistema no wizard (restore), sem seed obrigatório nesta tabela.

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | INTEGER PK | |
| `key` | TEXT NOT NULL UNIQUE | |
| `name` | TEXT NOT NULL | rótulo no catálogo |
| `title` | TEXT NOT NULL | título default ao importar |
| `show_labor` | INTEGER NOT NULL DEFAULT 0 | 0/1 |
| `lines_json` | TEXT NOT NULL | mesmas linhas de `quote_templates` (pode `[]`) |
| `created_at` | TEXT NOT NULL | |

**Import:** novo módulo `id=custom_<uuid>`, `legacy_kind=null`, itens com `section=module.id`.

**API:** `GET/POST /orcamentos/module-templates`, `PATCH/DELETE /orcamentos/module-templates/{id}` (perm `orcamentos`).

---

### 4. `billing_runs`

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | INTEGER PK | |
| `cnpj` | TEXT NOT NULL | |
| `client_name` | TEXT | |
| `tiflux_client_id` | INTEGER NULL | |
| `vhsys_client_id` | INTEGER NULL | |
| `competence` | TEXT NOT NULL | `YYYY-MM` |
| `due_date` | TEXT NULL | ISO date |
| `status` | TEXT NOT NULL | ver enum |
| `has_retencao` | INTEGER NOT NULL DEFAULT 0 | |
| `payment_method` | TEXT NULL | `boleto` \| `pix` |
| `gross_total` | REAL NULL | |
| `discount_pct` | REAL NULL | % sobre bruto |
| `discount_value` | REAL NULL | R$ fixo após % |
| `net_total` | REAL NULL | líquido (após desconto; retenção sobrescreve) |
| `nf_prefeitura_number` | TEXT NULL | branch humana |
| `tiflux_ticket_number` | TEXT NULL | cobrança |
| `vhsys_nf_id` | TEXT NULL | |
| `vhsys_cr_id` | TEXT NULL | |
| `error_message` | TEXT NULL | |
| `approved_by` | INTEGER NULL | user id auth |
| `created_by` | INTEGER NULL | |
| `created_at` | TEXT NOT NULL | |
| `updated_at` | TEXT NOT NULL | |
| `approved_at` | TEXT NULL | |
| `sent_at` | TEXT NULL | |

**`status`:** `draft` \| `approved` \| `awaiting_prefeitura` \| `emitting` \| `sent` \| `error`

Índice único sugerido: `(tiflux_client_id, competence)` WHERE client NOT NULL — evitar duplicar fila do mês (SQL decide UNIQUE parcial vs app check).

---

### 5. `billing_items`

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | INTEGER PK | |
| `run_id` | INTEGER NOT NULL FK → billing_runs ON DELETE CASCADE | |
| `source` | TEXT NOT NULL | `contract` \| `ticket` |
| `external_ref` | TEXT NULL | id contrato/ticket TiFlux |
| `description` | TEXT NOT NULL | |
| `amount` | REAL NOT NULL | |
| `sort_order` | INTEGER NOT NULL DEFAULT 0 | |

---

### 6. `billing_artifacts`

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | INTEGER PK | |
| `run_id` | INTEGER NOT NULL FK → billing_runs ON DELETE CASCADE | |
| `kind` | TEXT NOT NULL | `report` \| `nf` \| `boleto` |
| `path_or_url` | TEXT NOT NULL | |
| `created_at` | TEXT NOT NULL | |

---

### 7. `webhook_outbox`

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | INTEGER PK | |
| `event` | TEXT NOT NULL | ver ADR-0003 |
| `payload_json` | TEXT NOT NULL | |
| `status` | TEXT NOT NULL | `pending` \| `sent` \| `acked` \| `error` |
| `attempts` | INTEGER NOT NULL DEFAULT 0 | |
| `last_error` | TEXT NULL | |
| `idempotency_key` | TEXT NULL UNIQUE | ex. `quote.submit:42` |
| `created_at` | TEXT NOT NULL | |
| `updated_at` | TEXT NOT NULL | |
| `acked_at` | TEXT NULL | |

Índice: `(status, created_at)` para worker/retry.

---

### Fora do MVP (não criar agora)

- `contracts_from_quotes` — O3
- Tabela de timers / follow-up — fast-follow
- Multi-tenant / `org_id`

---

## Contratos de dados (payloads) — interfaces para Python

Tipos lógicos (Pydantic em O1+/F1; SQL só garante colunas).

### QuoteWrite (create/update draft)

```json
{
  "cnpj": "00000000000000",
  "client_name": "string?",
  "tiflux_client_id": 0,
  "vhsys_client_id": 0,
  "lead_temperature": "quente|morno|frio|null",
  "billed_by_type": "distribuidor|fornecedor|null",
  "billed_by_name": "string?",
  "implant_payment_plan": "string?",
  "implant_discount_pct": 0.0,
  "implant_discount_value": 0.0,
  "monthly_payment_plan": "string?",
  "monthly_discount_pct": 0.0,
  "monthly_discount_value": 0.0,
  "items": [
    {
      "section": "implantacao|mensalidade",
      "name": "string",
      "qty": 1.0,
      "unit_value": 0.0,
      "template_key": "string?",
      "sort_order": 0
    }
  ]
}
```

### QuoteRead

`QuoteWrite` + `id`, `status`, `pdf_path`, ids externos, timestamps, `created_by`.

### BillingRunWrite (montar fila)

```json
{
  "cnpj": "string",
  "client_name": "string?",
  "tiflux_client_id": 0,
  "vhsys_client_id": 0,
  "competence": "YYYY-MM",
  "due_date": "YYYY-MM-DD?",
  "has_retencao": false,
  "payment_method": "boleto|pix",
  "gross_total": 0.0,
  "items": [
    {
      "source": "contract|ticket",
      "external_ref": "string?",
      "description": "string",
      "amount": 0.0,
      "sort_order": 0
    }
  ]
}
```

### BillingPrefeituraInput

```json
{
  "nf_prefeitura_number": "string",
  "net_total": 0.0
}
```

### OutboxEvent (envelope — detalhe em ADR-0003)

```json
{
  "event": "quote.submit|quote.sent|quote.approved|billing.approved|billing.nf_prefeitura",
  "resource_type": "quote|billing_run",
  "resource_id": 0,
  "dry_run": true,
  "payload": {}
}
```

---

## Critérios de aceite (P0.3 SQL)

- [ ] Arquivo SQL versionado (ex. `docs/hub/schema/hub_v1.sql` **ou** `src/hub/schema.sql` — SQL escolhe path; documentar no PR)
- [ ] 7 tabelas acima + FKs + índices mínimos
- [ ] Enums documentados como CHECK ou comentário no SQL
- [ ] Sem código FastAPI/React/n8n neste PR
- [ ] Rodável em SQLite 3 local (smoke: `.read` / pytest mínimo opcional)

---

## Referências

- Plano §Modelo de dados
- `MODULO_ORCAMENTO_CONTRATO.md` §5
- ADR-0001, ADR-0003
