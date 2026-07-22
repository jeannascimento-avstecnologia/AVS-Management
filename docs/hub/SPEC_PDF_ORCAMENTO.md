# Spec — PDF de Orçamento (MVP)

> Status: aprovada para implementação · 2026-07-21  
> Referência visual: OS VHSYS (`ordem_* - PSI - M365.pdf`) — **estrutura/formatação**, não o texto “Ordem de serviço”.  
> SoT relacionado: `MODULO_ORCAMENTO_CONTRATO.md`

## Título e identificação

- Título impresso: `Orçamento : M{id}` (ex.: `Orçamento : M2353`).
- `{id}` = `quotes.id` (inteiro). Prefixo **sempre** `M`.
- Não usar “Ordem de serviço” / “OS” no título.

## Layout (adaptado da referência)

1. **Cabeçalho**
   - Logo AVS (`src/cropped-AVS-SemArco-Colorido_2024.png`) — canto **superior esquerdo**.
   - Título à direita do logo.
   - Bloco emitente (nome + CNPJ + endereço + telefone/celular/e-mail/site) abaixo do título.
2. **DADOS DO CLIENTE** — grid 2 colunas (razão, CNPJ, e-mail, telefone, endereço, nº, bairro, CEP, cidade, UF, etc.). Meta opcional: data (geração).
3. **Módulos (N seções dinâmicas)** — **não** há 2 seções fixas: bandas = módulos do canvas na ordem `sort_order` de `quotes.modules_json`:
   - Título da banda = `module.title` (não o `id`).
   - Tabela item / qtde / v. unit. / v. total filtrada por `quote_items.section = module.id`.
   - Mão de obra só se `module.show_labor` e horas×taxa > 0 (default: só Mensalidade seedada).
   - Por módulo: desconto (%↔R$ espelho), forma de pagamento, total líquido.
   - Seed no create: Implantação + Mensalidade; **removíveis/reordenáveis** — PDF segue a ordem do canvas; se ausentes, **não** imprimir banda.
4. Divisórias entre módulos quando houver mais de um.
5. **Dados de pagamento / resumo**:
   - Uma linha (ou par) de resumo **por módulo presente** (qtde itens + total líquido), rótulo = título do módulo.
   - Se ainda existirem módulos com `legacy_kind` `implantacao` / `mensalidade`, manter também os rótulos OS VHSYS:
     - `TOTAL DE HORAS/QTDE DE SERVICOS` / `VALOR TOTAL DOS SERVICOS` ← módulo `legacy_kind=implantacao`
     - `TOTAL DE PRODUTOS` / `VALOR TOTAL DOS PRODUTOS` ← módulo `legacy_kind=mensalidade`
   - Se um dos legados foi removido, omitir o par correspondente.
   - `VALOR TOTAL DO ORCAMENTO` = soma dos líquidos de **todos** os módulos presentes.
6. **OBSERVACOES** — texto livre (`quotes.notes`), editável no wizard **passo 3 (Revisão)**; opcional; PDF imprime o bloco mesmo se vazio (`-`).
7. **Assinaturas** (3 colunas): data do aceite · Assinatura do Prestador · Assinatura do Sacado.

## Formatação / paginação

- Meta: **1 página A4** para orçamento típico (≤ ~8 linhas por seção + mão de obra).
- Compactar vãos, bandas e células; não forçar 2ª página por padding.
- Se estourar (muitos itens), 2ª+ páginas — aceitável; não cortar conteúdo.

### Quebras de página (block-level keep-together)

Quebras **somente entre blocos lógicos** — nunca no meio de um bloco (ex.: cabeçalho `DADOS DE PAGAMENTO` na pág. 1 e linhas na pág. 2).

**Blocos** (unidades indivisíveis preferenciais):

1. Cada seção de módulo (`_write_section` — banda + tabela + MO + desconto/pagamento + totais).
2. `DADOS DE PAGAMENTO` (banda + pares/linhas + `VALOR TOTAL DO ORCAMENTO`).
3. `OBSERVACOES` (banda + caixa de texto).
4. Assinaturas (linha + 3 colunas).

**Regra:**

1. Antes de escrever um bloco, estimar a altura (banda + linhas + padding).
2. Se `y_atual + altura_estimada` ultrapassa o limiar de quebra (`page_break_trigger` / `b_margin`), chamar `add_page()` **antes** de iniciar o bloco.
3. Preferência: manter o bloco inteiro na mesma página.
4. **Último recurso:** se o bloco for mais alto que a área útil de **uma** página (`h − t_margin − b_margin`), permitir quebra interna via `auto_page_break` (não há como caber sem partir).

Aplicável a módulos seed **e** custom (`modules_json`).

## Dados da empresa (emitente)

**Preferência (server-side, token nunca no FE):**

1. Cliente TiFlux do emitente: `TIFLUX_ISSUER_CLIENT_ID` (default `37443` = AVS) **ou** lookup por `QUOTE_ISSUER_CNPJ` via `find_by_cnpj`.
2. Enriquecer com `GET /clients/{id}/addresses` e `GET /clients/{id}/contacts`.

**Não existe** endpoint TiFlux v2 de “organização/conta da API” (account/org). Inventar rota é proibido.

**Fallback MVP (Settings / env):** se TiFlux falhar ou campo ausente, usar:

| Campo | Env | Default de referência |
|-------|-----|------------------------|
| Nome | `QUOTE_ISSUER_NAME` | `AVS TECNOLOGIA` |
| CNPJ | `QUOTE_ISSUER_CNPJ` | `08354533000183` |
| Endereço | `QUOTE_ISSUER_ADDRESS` | Rua Manuel Maria Barbosa Du Bocage, 70 Parque Taquaral - Campinas - SP CEP: 13.087-240 |
| Telefone | `QUOTE_ISSUER_PHONE` | `(19) 3243-9559` |
| Celular | `QUOTE_ISSUER_MOBILE` | `(19) 99656-6524` |
| E-mail | `QUOTE_ISSUER_EMAIL` | `contato@avstecnologia.com.br` |
| Site | `QUOTE_ISSUER_SITE` | `www.avstecnologia.com.br` |

Cliente do orçamento: `quote.tiflux_client_id` → mesmo padrão addresses/contacts; senão `client_name` + `cnpj` (+ `client_email` local).

## Mão de obra

| Módulo | UI wizard | PDF | Persistência |
|--------|-----------|-----|--------------|
| Seed Implantação (`show_labor=false`) | Sem MO | Ignorada | `legacy_kind` → colunas `implant_*` labor sempre NULL |
| Seed Mensalidade (`show_labor=true`) | Mantida | Se > 0 | `monthly_labor_*` |
| Custom (ex. Licenças) | Sem MO no MVP | Sem MO | Só em `modules_json` |

## Fora de escopo (fast-follow)

- Copiar NCM / unidade VHSYS no PDF.
- Upload logo via TiFlux URL (usa PNG local).
- Bloco “técnico / atendimento” editável (meta mínima: data).
- Mão de obra em módulos custom.
