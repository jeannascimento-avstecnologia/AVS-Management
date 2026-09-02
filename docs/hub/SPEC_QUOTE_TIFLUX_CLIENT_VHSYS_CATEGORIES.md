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
| `GET` | `/orcamentos/vhsys/categories` | Proxy `list_categories` + `GET /subcategorias` — só `status=Ativo` e `lixeira≠Sim`. Cada categoria inclui `subcategories: [{ id, name }]`. |
| `GET` | `/orcamentos/vhsys/catalog?q=&limit=&category_id=&subcategory_id=` | Extensão: `category_id` filtra `id_categoria`; `subcategory_id` filtra `subcategoria` / `id_subcategoria` do produto (pós-fetch). |

Catálogo normalizado inclui `category_id: number | null`.

### UI
- Em cada bloco do wizard (e nos formulários de biblioteca): `Select` de categorias VHSYS + `Select` de subcategorias da categoria escolhida.
- Estado local por bloco (não persiste no quote). Trocar a categoria zera a subcategoria.
- `VhsysItemSearch` recebe `categoryId` e `subcategoryId` e restringe a busca (ou todos se “Todas”).
- Via-dupla (criar produto): envia `id_categoria` / `id_subcategoria` quando selecionados.

### Limitações
- Sem parâmetro oficial de filtro em `/produtos` → filtro pós-fetch (já carregamos catálogo completo no FE).
- Categorias/subcategorias inativas/lixeira omitidas.
- Produto sem `id_subcategoria`/`subcategoria` some da lista se uma subcategoria estiver selecionada.

## Critérios de aceite
1. Buscar cliente TiFlux por CNPJ no passo 1 → `tiflux_client_id` salvo no PUT do orçamento.
2. Gerar PDF com esse id → `resolve_client` enriquece endereço/contato (mock).
3. Dropdown categorias + subcategorias por bloco; busca de item restrita à categoria/subcategoria.
4. Tokens TiFlux/VHSYS só server-side.
5. pytest cobre novos endpoints + filtro categoria/subcategoria; tipagem FE sem `any`.

---

## 3) Biblioteca de blocos — defaults e dialogs

- Dialogs/listas (Biblioteca, Inserir bloco, cadastros): altura limitada à viewport (`max-h-[90vh]`) com **scroll vertical**.
- Template persiste `notes` e `billed_by_name` (opcionais). Ao inserir no orçamento, copiar para o módulo; o wizard continua editável.
- Sem card **Faturado por** geral no passo 2.
