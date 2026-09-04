# Spec — Busca, título interno e mensalidades VHSYS

> Status: aprovada para implementação · 2026-09-03  
> SoT: `MODULO_ORCAMENTO_CONTRATO.md`, `SPEC_PDF_ORCAMENTO.md`, `SPEC_MENSALIDADES_VERSOES_PDF.md`

## 1) Lista `/orcamentos` — pesquisa e filtros

Além de status/lead:

| Param | Efeito |
|-------|--------|
| `client` | `client_name` LIKE ou `cnpj` LIKE (só dígitos) |
| `number` | `M123` ou `123` → `quotes.id` |
| `date_from` / `date_to` | ISO `YYYY-MM-DD` em `created_at` (prefixo data) |
| `q` | texto livre: nome, CNPJ, `title`, `M{id}`, nome de item, **valor** (parse `1.866,60` / `1866.60` → total da linha ou soma do orçamento) |

UI: seção Pesquisa na home (cliente, número, datas, caixa livre). Debounce ~300ms.
Ao abrir **Novo** (rascunho), Pesquisa + filtros lead/status compactam numa barra; o usuário pode expandir de novo sem fechar o formulário.

## 2) Título interno (`quotes.title`)

- Campo opcional (máx. 120). Editável no wizard ao lado de `Orçamento M{id}`.
- **Não** entra no PDF.

## 3) Mensalidades via VHSYS

- Linha inteira (não quantidade parcial).
- Ao selecionar no dialog: `POST /orcamentos/{id}/mensalidades/sugerir` `{item_ids}`.
- Lookup: `quote_items.vhsys_product_id` → `GET /produtos/{id}`; fallback busca exata por nome.
- `fornecedor_amount` = `round(valor_custo_produto * qty, 2)`; nome = `fornecedor_produto` ou `Fornecedor`.
- `intermediador_amount` = `max(0, total_linha − fornecedor)`; nome = emitente AVS.
- Custo ausente / custo×qty > total → warning; fallback 0 + total (ou cap no total).
- Dialog: campos readonly + badge VHSYS; “Editar manualmente” libera override. Validação soma = total da linha permanece.
- Persistência: `PUT …/mensalidades` (allocations com `source`, `vhsys_product_id` opcionais).

## 4) `quote_items.vhsys_product_id`

Preenchido ao selecionar item no `VhsysItemSearch`. Edição manual do nome zera o id.
