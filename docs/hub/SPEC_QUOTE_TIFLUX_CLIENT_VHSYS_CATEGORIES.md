# Spec — Cliente TiFlux no wizard + categorias VHSYS (MVP)

> Status: aprovada para implementação · 2026-07-20  
> Plano: `.cursor/plans/hub_avs_management_guide_8941781e.plan.md` (O1)  
> Relacionado: `SPEC_PDF_ORCAMENTO.md`, `MODULO_ORCAMENTO_CONTRATO.md`

**Declaração:** `Guia+Plano lidos | spec: docs/hub/SPEC_QUOTE_TIFLUX_CLIENT_VHSYS_CATEGORIES.md | escopo: MVP`

## 1) Cliente TiFlux na 1ª tela → PDF

### Objetivo
No passo Cliente do wizard (`QuoteWizardPage`), pesquisar CNPJ/nome no **TiFlux** (proxy server-side), selecionar cliente e gravar no orçamento: `cnpj`, `client_name`, `tiflux_client_id`. PDF já resolve partes via `pdf_parties.resolve_client(quote.tiflux_client_id)`.

### API
| Método | Path | Permissão | Comportamento |
|--------|------|-----------|---------------|
| `GET` | `/orcamentos/tiflux/clients?q=&limit=` | `orcamentos` | Proxy `TifluxClient.find_matches_by_cnpj` (≥11 dígitos) ou `find_by_name`. Resposta: `{ clients: [{ id, name, cnpj }], query }`. Token **nunca** no FE. |

### UI
- Combobox de busca (padrão `TifluxBillingClientSearch`) no passo 1.
- Ao selecionar: preenche CNPJ, nome, `tiflux_client_id` (mantém `vhsys_client_id` se já houver).
- Dialog “Cadastrar cliente” permanece (criação/integração).
- Refs TiFlux/VHSYS continuam visíveis.

### PDF
- Sem mudança de contrato: `resolve_pdf_parties` já usa `quote.tiflux_client_id`.
- Gap: garantir wizard grava o id; teste unitário de `resolve_client` com mock TiFlux.

### Fora de escopo
- Criar cliente TiFlux inline (já coberto pelo dialog cadastrar).
- Autocomplete VHSYS no passo 1 (cadastro overlay cobre).

---

## 2) Categorias VHSYS sob Implantação / Mensalidade

### Evidência API (Go)
| Endpoint | Uso |
|----------|-----|
| `GET /categorias` | Lista categorias de **produtos** (`id_categoria`, `nome_categoria`, `status_categoria`, `lixeira`). Doc: [Listar categorias](https://developers.vhsys.com.br/api/listar-categorias-16170694e0). |
| `GET /produtos` | Cada item traz `id_categoria`. **Não** documenta filtro query `id_categoria` → filtrar no client VHSYS após listar/paginar. |
| `POST /produtos` | Aceita `id_categoria` (opcional na via-dupla se categoria selecionada). |

Não confundir com `GET /categorias-clientes` (categorias de **clientes**).

### API hub
| Método | Path | Comportamento |
|--------|------|---------------|
| `GET` | `/orcamentos/vhsys/categories` | Proxy `list_categories` — só `status=Ativo` e `lixeira≠Sim`. |
| `GET` | `/orcamentos/vhsys/catalog?q=&limit=&category_id=` | Extensão: se `category_id` → filtra itens cujo `category_id` bate. |

Catálogo normalizado inclui `category_id: number | null`.

### UI
- Logo abaixo do título da seção (Implantação / Mensalidade): `Select` de categorias VHSYS.
- Estado local por seção (não persiste no quote).
- `VhsysItemSearch` recebe `categoryId` e só lista itens da categoria (ou todos se “Todas”).
- Via-dupla (criar produto): envia `id_categoria` quando categoria selecionada.

### Limitações
- Sem parâmetro oficial de filtro em `/produtos` → filtro pós-fetch (já carregamos catálogo completo no FE).
- Categorias inativas/lixeira omitidas.
- Subcategorias: não usadas no MVP (campo existe na resposta; ignorar).

## Critérios de aceite
1. Buscar cliente TiFlux por CNPJ no passo 1 → `tiflux_client_id` salvo no PUT do orçamento.
2. Gerar PDF com esse id → `resolve_client` enriquece endereço/contato (mock).
3. Dropdown categorias nas duas seções; busca de item restrita à categoria.
4. Tokens TiFlux/VHSYS só server-side.
5. pytest cobre novos endpoints + filtro categoria; tipagem FE sem `any`.
