# Spec — PDF de Orçamento (MVP)

> Status: aprovada para implementação · 2026-09-04  
> SoT relacionado: `MODULO_ORCAMENTO_CONTRATO.md`  
> Layout: proposta comercial convencional (mockup `artifacts/orcamento-M25-v4.pdf`).

## Título e identificação

- Título impresso: `Orçamento : M{id}` (ex.: `Orçamento : M2353`).
- `{id}` = `quotes.id` (inteiro). Prefixo **sempre** `M`.
- Versão ativa: `vX` ao lado do título, **fonte menor** (~75–80%).
- Data do orçamento no cabeçalho.
- `quotes.title` **nunca** é impresso.
- Não usar “Ordem de serviço” / “OS” no título.

## Layout

1. **Cabeçalho (emitente fixo AVS)** — logo à esquerda (aspect 1965×746 ≈ 2.63:1, ~44.7×17 mm); título 16 pt **centralizado verticalmente com a logo**; mesma linha: `Orçamento : M{id}` à esquerda da área de texto e **data do orçamento na extrema direita**. Abaixo, só identificação fiscal:

```
AVS TECNOLOGIA - CNPJ: 08.354.533/0001-83 | Insc Estadual: 795.275.950.117
```

   Abaixo do CNPJ/IE, no mesmo banner: endereço + telefone/e-mail/site (ícones). Cabeçalho **não** segue o tenant/parte de Faturado por.

```
Rua Manuel Maria Barbosa Du Bocage, 70 Parque Taquaral - Campinas - SP CEP: 13.087-240
(ícone tel) (19) 3243-9559 | (ícone e-mail) comercial@avstecnologia.cloud | (ícone site) https://avstecnologia.cloud/
```

   **Rodapé (todas as páginas):** paginação `Pagina X/{nb}` + logo VEIVO Sistemas (`pdf_icons/veivo-powered-by.png`) no canto inferior direito, opacidade 40%.

2. **Primeiro bloco: DADOS DO CLIENTE** — Nome (`legal_name` / `client_name`), CNPJ, Vendedor (`quotes.created_by` → nome do usuário; fallback usuário logado). Contato do cliente (nome/e-mail/telefone) **opcional à direita**, quando disponível.

3. **Módulos (N seções)** — ordem `sort_order` de `quotes.modules_json`:
   - Título = `module.title` (negrito na cor `_BLUE` + barra vertical azul 1.2 mm à esquerda + regra cinza). **Sem** diferenciação de cor por módulo.
   - Tabela **sempre** com cabeçalho `ITEM` / `QTDE` / `V. UNIT.` / `V. TOTAL`. Coluna `ITEM` mais larga, com quebra de linha (não truncar). Números alinhados ao header.
   - Se `module.simplified`: uma linha de dados com `display_name` (fallback `title`); qtde `1`; v. unit. = v. total = soma das linhas. **Não** imprimir nomes das linhas originais.
   - Senão: uma linha por item (`quote_items.section = module.id`).
   - Mão de obra só se `module.show_labor` e horas×taxa > 0.
   - Por módulo: desconto **somente se o aplicado for > 0**; forma de pagamento; total líquido.
   - Opcionais: `module.notes`; `module.billed_by_name` + `module.billed_by_cnpj` (Faturado por). **Não** imprimir Faturado por global.
   - Create inicia canvas **vazio**; PDF só lista módulos presentes.

4. Divisórias cinza entre módulos quando houver mais de um.

5. **Dados de pagamento / resumo**:
   - Uma linha de resumo **por módulo presente** (apenas label + valor líquido; **sem** coluna QTDE), rótulo = título do módulo (`TOTAL {título}`).
   - Se o módulo tiver linhas marcadas como mensalidade: abaixo do total do grupo, em **fonte menor** (itálico muted), o valor mensal daquele grupo (fornecedor | intermediador).
   - Se ainda existirem módulos com `legacy_kind` `implantacao` / `mensalidade`, manter os rótulos OS VHSYS de **valor** (sem QTDE):
     - `VALOR TOTAL DOS SERVICOS` ← `implantacao`
     - `VALOR TOTAL DOS PRODUTOS` ← `mensalidade`
   - `VALOR TOTAL DO ORCAMENTO` = soma dos líquidos de **todos** os módulos presentes **menos** o total das linhas marcadas como mensalidades (se houver). Destaque: box navy, texto branco.
   - Seção **`MENSALIDADES`** (cobranças) **depois** do valor total: fora do `VALOR TOTAL DO ORCAMENTO`. Linhas selecionadas continuam nos módulos originais (duplicate-include). Total da seção: box com outline azul.

6. **OBSERVACOES** — imprime **somente** `quotes.notes`. Sem disclaimer/ticket hardcoded. Bloco mesmo se vazio (`-`). Pré-fill do wizard (aviso + `Ticket no.:`) entra só se o usuário salvou isso em `notes`. **`quotes.internal_notes` nunca é impresso** (campo 100% interno).

7. **Assinaturas** — **não** imprimir (removidas).

## Fundo

- Página A4 branca. **Sem** barras de marca no topo/lateral. Hierarquia de seção: barra vertical `_BLUE` 1.2 mm (todas as seções).
- Tabelas: header cinza claro, bordas cinza. Sem padrão PCB.

## Formatação / paginação

- Meta: **1 página A4** para orçamento típico.
- Respiro entre linhas: `_ROW_H` ≥ 5.8, `_GAP` ≥ 1.4, `line_h` ≥ 4.2 (não grudar rótulo/valor).
- Quebras **somente entre blocos lógicos** (`_ensure_space` keep-together por módulo/resumo).

## Dados da empresa (emitente)

Cabeçalho comercial usa **defaults Settings/env** (AVS). TiFlux issuer continua disponível como enriquecimento de endereço se o lookup funcionar, mas CNPJ/IE/e-mail/site/telefone impressos seguem a tabela abaixo quando o campo TiFlux divergir ou faltar.

| Campo | Env | Default |
|-------|-----|---------|
| Nome | `QUOTE_ISSUER_NAME` | `AVS TECNOLOGIA` |
| CNPJ | `QUOTE_ISSUER_CNPJ` | `08354533000183` |
| Insc. Estadual | `QUOTE_ISSUER_IE` | `795.275.950.117` |
| Endereço | `QUOTE_ISSUER_ADDRESS` | Rua Manuel Maria Barbosa Du Bocage, 70 Parque Taquaral - Campinas - SP CEP: 13.087-240 |
| Telefone | `QUOTE_ISSUER_PHONE` | `(19) 3243-9559` |
| E-mail | `QUOTE_ISSUER_EMAIL` | `comercial@avstecnologia.cloud` |
| Site | `QUOTE_ISSUER_SITE` | `https://avstecnologia.cloud/` |

Celular (`QUOTE_ISSUER_MOBILE`) **não** entra no cabeçalho.

Ícones de telefone/e-mail/site: PNGs pequenos (fpdf2 + Helvetica não renderiza emoji).

## Mão de obra

Inalterada: Implantação seed sem MO; Mensalidade se `show_labor`; custom sem MO no MVP.

## Fora de escopo (fast-follow)

- Copiar NCM / unidade VHSYS no PDF.
- Upload logo via TiFlux URL.
- Bloco “técnico / atendimento” editável.
- Mão de obra em módulos custom.

## Adendo — Mensalidades, versões e PDF (fast-follow)

- Cabeçalho:
  - Manter `Orçamento : M{id}` e exibir `vX` ao lado com **fonte menor**.
- Observações (bloco `OBSERVACOES`):
  - PDF imprime somente `quotes.notes` (pré-fill do wizard continua no formulário).
  - Sem bloco fixo de “Aviso + Ticket” no PDF.
- Desconto:
  - Exibir o trecho de desconto **somente** quando o usuário preencher `discount_pct` e/ou `discount_value` (e o desconto aplicado for > 0).
- Mensalidades:
  - Adicionar uma seção exclusiva `MENSALIDADES` no PDF.
  - Essa seção fica **fora do** `VALOR TOTAL DO ORCAMENTO` (separação implementação vs mensalidade).
- Tabela:
  - Aumentar espaço do texto em `ITEM`, melhorar alinhamento e quebrar em linhas quando o texto exceder a caixa.
