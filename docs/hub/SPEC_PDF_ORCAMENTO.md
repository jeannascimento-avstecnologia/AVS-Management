# Spec — PDF de Orçamento (MVP)

> Status: aprovada para implementação · 2026-09-02  
> SoT relacionado: `MODULO_ORCAMENTO_CONTRATO.md`  
> Layout: proposta comercial convencional (sem estética OS/VHSYS colorida).

## Título e identificação

- Título impresso: `Orçamento : M{id}` (ex.: `Orçamento : M2353`).
- `{id}` = `quotes.id` (inteiro). Prefixo **sempre** `M`.
- Versão ativa: `vX` ao lado do título, **fonte menor** (~75–80%).
- Data do orçamento no cabeçalho (não há bloco Dados do Cliente).
- Não usar “Ordem de serviço” / “OS” no título.

## Layout

1. **Cabeçalho (emitente fixo AVS)** — logo à esquerda; mesma linha: título `Orçamento : M{id}` à esquerda da área de texto e **data do orçamento na extrema direita** (alinhada à margem útil). Abaixo, só identificação fiscal:

```
AVS TECNOLOGIA - CNPJ: 08.354.533/0001-83 | Insc Estadual: 795.275.950.117
```

   **Rodapé (todas as páginas):** endereço + telefone/e-mail/site (ícones). Cabeçalho/rodapé **não** seguem o tenant/parte de Faturado por.

```
Rua Manuel Maria Barbosa Du Bocage, 70 Parque Taquaral - Campinas - SP CEP: 13.087-240
(ícone tel) (19) 3243-9559 | (ícone e-mail) comercial@avstecnologia.cloud | (ícone site) https://avstecnologia.cloud/
```

2. **Sem bloco DADOS DO CLIENTE.** Cliente permanece só no wizard (passos 1 e 3).

3. **Módulos (N seções)** — ordem `sort_order` de `quotes.modules_json`:
   - Título = `module.title` (tipografia negrito + regra cinza; **sem** banda vermelha/azul).
   - Tabela **sempre** com cabeçalho `ITEM` / `QTDE` / `V. UNIT.` / `V. TOTAL`. Coluna `ITEM` mais larga, com quebra de linha (não truncar). Números alinhados ao header.
   - Se `module.simplified`: uma linha de dados com `display_name` (fallback `title`); qtde `1`; v. unit. = v. total = soma das linhas. **Não** imprimir nomes das linhas originais.
   - Senão: uma linha por item (`quote_items.section = module.id`).
   - Mão de obra só se `module.show_labor` e horas×taxa > 0.
   - Por módulo: desconto **somente se o aplicado for > 0**; forma de pagamento; total líquido.
   - Opcionais: `module.notes`; `module.billed_by_name` + `module.billed_by_cnpj` (Faturado por). **Não** imprimir Faturado por global.
   - Create inicia canvas **vazio**; PDF só lista módulos presentes.

4. Divisórias cinza entre módulos quando houver mais de um.

5. **Dados de pagamento / resumo**:
   - Uma linha (ou par) de resumo **por módulo presente** (qtde itens + total líquido), rótulo = título do módulo.
   - Se ainda existirem módulos com `legacy_kind` `implantacao` / `mensalidade`, manter também os rótulos OS VHSYS:
     - `TOTAL DE HORAS/QTDE DE SERVICOS` / `VALOR TOTAL DOS SERVICOS` ← `implantacao`
     - `TOTAL DE PRODUTOS` / `VALOR TOTAL DOS PRODUTOS` ← `mensalidade`
   - `VALOR TOTAL DO ORCAMENTO` = soma dos líquidos de **todos** os módulos presentes **menos** o total das linhas marcadas como mensalidades (se houver).
   - Seção **`MENSALIDADES`** (cobranças) **depois** do valor total: fora do `VALOR TOTAL DO ORCAMENTO`. Linhas selecionadas continuam nos módulos originais (duplicate-include).

6. **OBSERVACOES** — `quotes.notes` (pré-fill no wizard: aviso + `Ticket no.:`). Imprime o bloco mesmo se vazio (`-`). Se `notes` não trouxer o aviso/ticket, o render injeta essas linhas **dentro** de OBSERVACOES (não no rodapé).

7. **Assinaturas** (3 colunas): data do aceite · Assinatura do Prestador · Assinatura do Sacado. **Sem** bloco fixo de aviso+ticket acima das assinaturas.

## Fundo

- Página A4 branca. **Sem** barras de marca no topo/lateral, **sem** bandas coloridas de seção.
- Tabelas: header cinza claro, bordas cinza. Sem padrão PCB.

## Formatação / paginação

- Meta: **1 página A4** para orçamento típico.
- Quebras **somente entre blocos lógicos**. Assinaturas no keep-together (aviso+ticket vão nas Observações).

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
  - Deve conter o trecho:
    - `Os valores podem sofrer alteracao sem previo aviso.`
    - `Ticket no.:` (editável no passo 3).
  - O PDF não deve ter um bloco fixo separado de “Aviso + Ticket” fora das Observações.
- Desconto:
  - Exibir o trecho de desconto **somente** quando o usuário preencher `discount_pct` e/ou `discount_value` (e o desconto aplicado for > 0).
- Mensalidades:
  - Adicionar uma seção exclusiva `MENSALIDADES` no PDF.
  - Essa seção fica **fora do** `VALOR TOTAL DO ORCAMENTO` (separação implementação vs mensalidade).
- Tabela:
  - Aumentar espaço do texto em `ITEM`, melhorar alinhamento e quebrar em linhas quando o texto exceder a caixa.
