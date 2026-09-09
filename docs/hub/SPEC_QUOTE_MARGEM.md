# Spec — Custo vs lucro (passo 3 do wizard)

> Status: aprovada para implementação (fast-follow) · 2026-09-09  
> SoT: `MODULO_ORCAMENTO_CONTRATO.md`, `SPEC_MENSALIDADES_VERSOES_PDF.md`  
> Declaração: `Guia+Plano lidos | spec: docs/hub/SPEC_QUOTE_MARGEM.md | escopo: fast-follow`

## 1) Objetivo

Passo 3 interno: **receita vs custos por módulo** (COGS VHSYS + horas de analista em implantação).  
Recorrente = módulos com `is_mensalidade` efetivo.  
**Nunca** entra no PDF, e-mail ou TiFlux.

## 2) Wizard

| Passo | Label | Cliente vê? |
|-------|--------|-------------|
| 1 | Orçamento | canvas |
| 2 | Revisão | totais (implementação vs mensalidades), PDF, envio |
| 3 | Custo vs lucro | só interno |

Enviar / PDF / versões permanecem no passo 2. Passo 3 não bloqueia submit.

## 3) Classificação do item (`margin_kind`)

`implantacao | licenca | produto | null`.

Inferência (só se `margin_kind` ainda null) a partir do catálogo VHSYS:

1. `tipo_produto = Servico` → `implantacao`
2. `Produto` + nome casefold contém `licen`, `m365`, `microsoft 365` ou `backup` → `licenca`
3. `Produto` sem heurística → `produto`
4. Sem cadastro / sem tipo → `null` → UI: 3 botões Implantação | Licença | Produto

Override manual sempre permitido.

## 4) Campos

- `quote_items.unit_cost` — snapshot VHSYS; `null` = desconhecido; `0` = custo zero
- `quote_items.margin_kind`
- `QuoteModule.internal_labor_hours` + `internal_hourly_cost` — custo interno; **não** reusar `labor_*` de venda/PDF
- Fallback: se internals vazios no módulo de implantação, copiar uma vez `quotes.implementation_hours` / `analyst_hourly_cost` (globais deprecados na UI)
- `QUOTE_ANALYST_HOURLY_COST` = default de R$/h; `null` no módulo usa default; **`0` persistido é override**
- Versões: `snapshot_margin_json` (PDF ignora)

## 5) Cálculo por módulo

- Receita = líquido da seção (itens + MO venda se `show_labor`)
- COGS = `unit_cost * qty` dos itens de módulos **sem** `is_mensalidade`
- Custo horas = se `legacy_kind=implantacao` **ou** algum item `implantacao`: `hours * effective_rate`
- Lucro = receita − COGS − custo horas

KPI do orçamento (soma dos módulos, sem rótulo one-shot): Receita | Custo (COGS+horas) | Lucro | Horas.

Recorrente: líquido dos módulos com `is_mensalidade` (não `monthly_draft_json`). Fallback: draft legado se nenhum módulo traz o campo.

## 6) API / UI

- `GET /orcamentos/{id}/margem` — `modules[]` + totais + `recurring`
- `POST .../margem/refresh-costs` — `unit_cost` + `margin_kind` se null
- UI: KPI 4 blocos; um Card por módulo com itens; produto/licença = Custo + Venda editáveis; implantação = horas/R$/h no módulo; kind null = 3 botões

## 7) Fora de escopo

PDF, valor-hora por usuário, dashboard da lista, MO de implantação no PDF.
