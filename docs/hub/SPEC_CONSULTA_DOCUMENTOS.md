# SPEC — Consulta de documentos (orçamentos / PDFs / faturamentos)

**Status:** aprovada MVP · **Data:** 2026-07-21  
**Plano:** `.cursor/plans/hub_avs_management_guide_8941781e.plan.md`  
**Não conflitar com:** `/consultar` (status cadastro TiFlux/VHSYS — perm `consultar`).

---

## Objetivo

Tela independente de **busca/consulta de documentos do hub** (SoT local `hub.db`), permitindo achar orçamentos, PDFs derivados e faturamentos **pela empresa (CNPJ/nome) ou pela ordem** (id orçamento `M{id}`, `vhsys_os_id`, ticket TiFlux, id de billing run).

Ao abrir a tela: listagem automática dos documentos **mais recentes** (sem digitar busca).  
Ao selecionar um orçamento: detalhe rico, download do PDF (se existir), e navegação para o wizard `/orcamentos/:id`.  
Ao selecionar faturamento: detalhe rico + link `/faturamento/:id`.

---

## Fora de escopo (fast-follow)

- Full-text em conteúdo do PDF.
- Indexação cross-tenant / multi-org.
- Nova permissão dedicada (reutiliza `orcamentos` + `faturar`).
- Busca live de NF/boleto VHSYS além do que já está em `billing_runs` / artifacts locais.
- Histórico de buscas / favoritos.
- Campo de validade/vencimento em `quotes` (não existe no schema — não inventar coluna; billing usa `due_date`).

---

## Rota UI

| Item | Valor |
|------|-------|
| Path | `/documentos` |
| Label | Documentos |
| Nav | Sidebar + Dashboard card + Command palette + Breadcrumb |
| Acesso | `orcamentos` **OU** `faturar` (qualquer uma) |

Resultados filtrados por perm: sem `orcamentos` → não retorna quotes/pdfs; sem `faturar` → não retorna billing.

---

## API

### `GET /documentos/recent?limit={n}`

- Auth obrigatória; exige `orcamentos` **ou** `faturar`.
- Lista orçamentos e faturamentos do hub **mais recentes → mais antigos** (`updated_at DESC`, fallback `created_at` / `id`).
- `limit` default 50, max 100.
- Sem enriquecimento externo (`enrichment` = skipped).
- Mesmo shape de resposta que a busca (`query` = `""`).
- PDFs derivados: subset dos orçamentos retornados com `pdf_path` preenchido.

### `GET /documentos?q={term}&limit={n}`

- Auth obrigatória; exige `orcamentos` **ou** `faturar`.
- `q` min 1 char após trim (**vazio → 422**; listagem recente é `/documentos/recent`).
- `limit` default 50, max 100.
- Segredos TiFlux/VHSYS **só** server-side; falha externa → degrada (resultado local + flag `enrichment`).

**Parsing de `q` (ordem de prioridade):**

1. `M{id}` / `m{id}` → quote id exato.
2. Prefixo `OS` / `VHSYS` + número → `quotes.vhsys_os_id`.
3. CNPJ 14 dígitos → match `cnpj` em quotes e billing_runs.
4. Inteiro puro → match id quote **e** id billing_run **e** `vhsys_os_id` / tickets (texto).
5. Texto livre → `LIKE` em `client_name` (+ enriquecimento TiFlux opcional).

**Resposta (shape — hits enriquecidos para sheet):**

```json
{
  "query": "string",
  "quotes": [
    {
      "id": 1,
      "display_id": "M1",
      "doc_type": "orcamento",
      "cnpj": "...",
      "client_name": "...",
      "status": "draft",
      "lead_temperature": "quente|morno|frio|null",
      "billed_by_type": "distribuidor|fornecedor|null",
      "billed_by_name": "...|null",
      "vhsys_os_id": null,
      "tiflux_ticket_number": null,
      "tiflux_client_id": null,
      "has_pdf": true,
      "implant_net": 100.0,
      "monthly_net": 50.0,
      "value_total": 150.0,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "pdfs": [
    {
      "quote_id": 1,
      "display_id": "M1",
      "doc_type": "pdf",
      "client_name": "...",
      "cnpj": "...",
      "status": "draft",
      "lead_temperature": null,
      "billed_by_type": null,
      "billed_by_name": null,
      "vhsys_os_id": null,
      "tiflux_ticket_number": null,
      "has_pdf": true,
      "value_total": 150.0,
      "pdf_path": "uuid.pdf",
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "billing_runs": [
    {
      "id": 1,
      "doc_type": "faturamento",
      "cnpj": "...",
      "client_name": "...",
      "competence": "2026-07",
      "status": "draft",
      "net_total": 100.0,
      "gross_total": 100.0,
      "due_date": "2026-07-15|null",
      "payment_method": "boleto|pix|null",
      "vhsys_nf_id": null,
      "vhsys_cr_id": null,
      "tiflux_ticket_number": null,
      "tiflux_client_id": null,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "enrichment": {
    "tiflux": "ok|skipped|error",
    "vhsys": "ok|skipped|error",
    "detail": null
  }
}
```

**Totais de orçamento:** `implant_net` e `monthly_net` calculados server-side reusando `src/quotes/totals.py` (itens + mão de obra mensal − desconto de seção, alinhado ao PDF). `value_total` = soma dos líquidos. PDF herda `value_total` do orçamento pai.

**Campos inexistentes no schema:** `quotes` não tem validade/vencimento — omitir na UI (não inventar coluna). Billing: `due_date` quando preenchido.

**Enriquecimento MVP (só busca):** se `q` for nome/CNPJ e credenciais TiFlux existirem, buscar clientes TiFlux e expandir busca local por `cnpj` / `tiflux_client_id`. VHSYS: se query parecer OS id e credenciais existirem, tentar match por id — falha = `error` sem bloquear resposta local.

Download PDF: reutilizar `GET /orcamentos/{id}/pdf` (perm `orcamentos`).

---

## UI (Aurora)

1. Campo de busca único (empresa **ou** ordem) + botão Buscar + limpar (volta ao recent).
2. Ao montar a página: `useQuery` → `GET /documentos/recent` popula tabs Orçamentos | Faturamentos | PDFs.
3. Busca substitui a listagem recent; limpar busca (ou campo vazio + limpar) restaura recent.
4. Tabs/grupos: Orçamentos | Faturamentos | PDFs.
5. Click item → Sheet/painel com campos ricos:
   - Tipo (Orçamento | Faturamento | PDF)
   - Valor (`value_total` / `net_total`; PDF = valor do orçamento pai)
   - lead_temperature / billed_by (se presentes)
   - Criado / Atualizado
   - Vencimento (`due_date` billing; quotes: omitir ou "—")
   - Status, CNPJ, cliente, OS VHSYS, ticket TiFlux, has_pdf, competência (billing)
6. Ações: Download PDF (se `has_pdf`), Abrir em Orçamentos → `/orcamentos/:id`, Abrir faturamento → `/faturamento/:id`.
7. Normalização defensiva de arrays em `onSuccess` / parse da resposta permanece.

---

## Testes

- pytest: parse `M{id}`, CNPJ, nome; auth 401/403; filtro por perm.
- pytest: `GET /documentos/recent` ordena recentes e respeita perms; hits incluem campos novos (`value_total` / `created_at` / `due_date` / `doc_type`).
- pytest: busca retorna campos de detalhe (ex.: `implant_net`, `lead_temperature`).
- `tsc --noEmit` no frontend se alterar TS.

---

## Critérios de aceite MVP

- [ ] Usuário com `orcamentos` acha orçamento por CNPJ, nome e `M{id}`.
- [ ] PDF listado quando `pdf_path` preenchido; download via API existente.
- [ ] Botão abre wizard `/orcamentos/:id`.
- [ ] Usuário com só `faturar` vê billing e não quotes.
- [ ] TiFlux/VHSYS offline não quebra a busca local.
- [ ] Ao abrir `/documentos` sem busca, tabs já mostram recentes (mais novo → mais antigo).
- [ ] Sheet exibe tipo, valor, datas e metadados úteis (não só cliente/status/OS).
