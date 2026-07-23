# Dossiê de Gargalos — Lead Pipeline / Orçamentos

**Red Team Performance / Chaos** · 2026-07-23  
**Escopo:** MVP · Zero-Breakage (sem mutação de regras de negócio / layout)  
**Alvo:** `quoteLead.ts` · `QuoteLeadPipelinePanel` · `QuotesPage` · `QuotesService.list`

---

## Declaração

`Guia+Plano lidos | spec: stress lead pipeline | escopo: MVP`

Mitigações de código **não aplicadas** neste passe: gargalos #1–#3 exigem mudança de contrato API/UI ou agregação server-side. Helpers puros no cliente **não** são o hot path sob o `limit=100` atual (ver números).

---

## Top 3 (resumo executivo)

| # | Local | Severidade | Sintoma |
|---|--------|------------|---------|
| 1 | `QuotesPage.tsx` — `listQuery` + `pipelineQuery` | **Alta** | 2× fetch HTTP do mesmo endpoint; sem dedupe RQ quando filtros = `all` |
| 2 | `QuotesService.list` → `_fetch_items` | **Alta** | N+1 SQL; tempo ~linear no nº de quotes |
| 3 | `pipelineQuery` `limit: 100` + payload `QuoteRead` completo | **Média–Alta** | Contagens/somas do painel silenciosamente truncadas; payload gordo só para agregados |

---

## Matriz de gargalos

### G1 — Dupla query React Query (lista + pipeline)

| Campo | Detalhe |
|--------|---------|
| **Local** | `frontend/src/pages/QuotesPage.tsx` · `listQuery` (L94–103) + `pipelineQuery` (L105–108) |
| **Sintoma** | Mount da página dispara **2** `GET /orcamentos?limit=100`. Com `statusFilter=all` + `leadFilter=all`, parâmetros idênticos, mas `queryKey` distintos (`['quotes', status, lead]` vs `['quotes', 'pipeline-summary']`) → **React Query não deduplica**. `invalidateQueries(['quotes'])` invalida ambos → 2× refetch após create/delete/submit/PDF. |
| **Severidade** | Alta (I/O + JSON parse + serialização backend ×2) |
| **Mitigação Gerente** | Epic: endpoint leve `GET /orcamentos/pipeline-summary` (counts/sums/hot ids) **ou** unificar cache quando filtros abertos. |
| **Mitigação Programador** | Opção A (MVP): se `status===all && lead===all`, alimentar o painel com `listQuery.data` e pular `pipelineQuery`. Opção B: `placeholderData` / `initialData` compartilhado. Opção C (melhor): aggregate SQL no backend. |
| **Mitigação Debugger** | Network tab: 2 requests paralelos no load; após mutate, 2× de novo. Comparar bytes. |
| **Risco UX** | Baixo se unificar só no caso filtros abertos; painel deve permanecer independente quando lista está filtrada. |

### G2 — N+1 em `quote_items` no `list`

| Campo | Detalhe |
|--------|---------|
| **Local** | `src/quotes/service.py` · `QuoteService.list` (L416–448) → `_fetch_items` (L300–311) por row |
| **Sintoma** | 1 SELECT quotes + **N** SELECTs `quote_items WHERE quote_id=?`. Stress: `list(200)/list(100) ≈ 1.99` → linearidade confirmada. |
| **Severidade** | Alta (escala com volume; piora com items/quote e `model_dump` no router) |
| **Mitigação Gerente** | Priorizar batch fetch / JOIN no backlog O1 listagem. |
| **Mitigação Programador** | `WHERE quote_id IN (...)` + `groupby` em memória; ou `JOIN` + hydrate. Manter ordem `section, sort_order, id`. |
| **Mitigação Debugger** | Monkeypatch `_fetch_items` (teste stress); `sqlite3` trace; ratio tempo vs N. |
| **Testado** | `tests/test_quotes_list_stress.py::test_list_n_plus_one_items_queries` — 40 quotes → 40 calls. |

### G3 — Cap 100 + payload completo no summary

| Campo | Detalhe |
|--------|---------|
| **Local** | `QuotesPage.tsx` `pipelineQuery` `limit: 100`; backend default/cap `list` (max 500) |
| **Sintoma** | Painel (`countByLead` / `sumByLead` / `hotPendingQuotes`) só vê os **100** `updated_at` mais recentes. Com >100 orçamentos, métricas do lead **subcontam** sem aviso. Payload inclui `items[]` + `modules` + colunas flat — desnecessário para contagem/soma. |
| **Severidade** | Média–Alta (correção de produto sob carga real; waste de banda) |
| **Mitigação Gerente** | Definir: summary global vs “top 100 recentes”; se global → endpoint aggregate obrigatório. |
| **Mitigação Programador** | SQL: `GROUP BY lead_temperature` + `SUM(total)` (subquery items) + top-5 quentes; UI consome DTO fino. |
| **Mitigação Debugger** | Seed >100 drafts no hub temp; comparar painel vs `COUNT(*)` SQL. |
| **Testado** | `test_pipeline_cap_silently_truncates` — 120 seed → list(100)=100, list(500)=120. |

### G4 — `hotPendingQuotes` sort O(n log n)

| Campo | Detalhe |
|--------|---------|
| **Local** | `frontend/src/lib/quoteLead.ts` · `hotPendingQuotes` (L84–93) |
| **Sintoma** | `filter` + `sort` completo + `slice(5)`. Em 10k: ~0.64 ms/call (aceitável). No cap UI 100: ~0.006 ms. |
| **Severidade** | Baixa (hoje) |
| **Mitigação** | Top-k parcial (heap) só se N crescer sem cap; preferir ordenação no SQL do summary. |

### G5 — Recompute no render do painel + `quoteTotal` repetido

| Campo | Detalhe |
|--------|---------|
| **Local** | `QuoteLeadPipelinePanel.tsx` L53–55 (3 passes/render); `quoteTotal` L38–40 e lista em `QuotesPage` L63–65 / L439 |
| **Sintoma** | Clique no círculo seta `pressedLead` → re-render → `countByLead`+`sumByLead`+`hotPendingQuotes` de novo. Em n=100: ≪1 ms — **não engasga UI**. |
| **Severidade** | Baixa |
| **Mitigação** | `useMemo(..., [quotes])` + unificar count/sum numa passagem (`statsByLead`). Bench: 1-pass ≈ 2-pass em n≤1k (ganho irrelevante no MVP). **Não aplicado** (benefício não claro sob cap 100). |

### G6 — Serialização HTTP no router

| Campo | Detalhe |
|--------|---------|
| **Local** | `src/quotes/router.py` · `list_quotes` → `[q.model_dump() for q in quotes]` |
| **Sintoma** | Após N+1, ainda serializa Pydantic completo ×N. Dupla query (G1) duplica custo. |
| **Severidade** | Média (acoplada a G1/G2) |
| **Mitigação** | DTO listagem enxuto (`items_count`, `total_value` pré-agregado) para lista/pipeline. |

---

## O que foi testado

### A) Micro-bench JS (sintético, local)

```bash
node scripts/bench_quote_lead.mjs
```

| Cenário | countByLead /call | sumByLead /call | hotPending /call | count+sum 2-pass | stats 1-pass |
|---------|-------------------|-----------------|------------------|------------------|--------------|
| n=100, 5 items | 0.0021 ms | 0.0020 ms | 0.0059 ms | 0.0028 ms | 0.0030 ms |
| n=1 000, 10 items | 0.012 ms | 0.018 ms | 0.055 ms | 0.028 ms | 0.027 ms |
| n=10 000, 20 items | 0.125 ms | 0.259 ms | 0.640 ms | 0.328 ms | 0.324 ms |

**Conclusão:** helpers client-side **não** são gargalo sob `limit=100`. O hot path é rede + SQL N+1 + JSON.

### B) Stress SQLite temp (pytest)

```bash
.venv/bin/python -m pytest tests/test_quotes_list_stress.py -s -q
```

| Métrica | Valor (máquina local 2026-07-23) |
|---------|----------------------------------|
| `_fetch_items` calls / list(N) | = N (N+1 confirmado) |
| `list(100)` · 8 items/quote | **4.77 ms** |
| `list(200)` · 8 items/quote | **9.50 ms** |
| ratio 200/100 | **1.99** (linear) |
| Cap silent | 120 rows → list(100) retorna 100 |

*Nota:* tempos locais SQLite são baixos; em disco OneDrive/rede/CI + payload modules/JSON + 2× HTTP o custo efetivo sobe. A forma (linear N+1 + duplo fetch) é o risco, não o 5 ms absolutos.

---

## Avaliação das 2 queries React Query

```
Mount QuotesPage
  ├─ listQuery     GET /orcamentos?limit=100[&status][&lead]
  └─ pipelineQuery GET /orcamentos?limit=100          ← sempre sem filtro
```

| Situação | Duplicação? | Correção sugerida |
|----------|-------------|-------------------|
| Filtros `all`/`all` | **Sim** — mesmo SQL efetivo, 2 keys | Reusar `listQuery` no painel **ou** key canônica compartilhada |
| Filtro status/lead ativo | Não — painel precisa universo aberto | Manter query dedicada **ou** summary endpoint |
| Pós-mutate | 2 invalidations | Summary estável + invalidate seletiva |

---

## Zero-Breakage — o que **não** fazer no MVP sem ADR

- Mudar regra “filtro lead exclui approved/contracted” (`service.list`).
- Alterar layout/cores dos círculos do painel.
- Remover `pipelineQuery` sem garantir que painel continue global sob filtro de lista.
- Expor segredos / bater em TiFlux/VHSYS reais.

---

## Artefatos deste passe

| Path | Papel |
|------|--------|
| `docs/hub/STRESS_LEAD_PIPELINE.md` | Este dossiê |
| `scripts/bench_quote_lead.mjs` | Micro-bench helpers (espelho puro) |
| `tests/test_quotes_list_stress.py` | Stress N+1 + timing + cap (DB temp) |

**Mitigação aplicada em produção:** nenhuma.

**Próximo handoff (Programador):** G1 (dedupe/unificar query) → G2 (batch items) → G3 (aggregate endpoint). Nessa ordem ROI/risco.
