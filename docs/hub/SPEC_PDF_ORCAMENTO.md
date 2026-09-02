# Spec — PDF de Orçamento (MVP)

> Status: aprovada para implementação · 2026-09-02  
> SoT relacionado: `MODULO_ORCAMENTO_CONTRATO.md`  
> Layout: proposta comercial convencional (sem estética OS/VHSYS colorida).

## Título e identificação

- Título impresso: `Orçamento : M{id}` (ex.: `Orçamento : M2353`).
- `{id}` = `quotes.id` (inteiro). Prefixo **sempre** `M`.
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
   - Tabela **sempre** com cabeçalho `ITEM` / `QTDE.` / `V. UNIT.` / `V. TOTAL`.
   - Se `module.simplified`: uma linha de dados com `display_name` (fallback `title`); qtde `1`; v. unit. = v. total = soma das linhas. **Não** imprimir nomes das linhas originais.
   - Senão: uma linha por item (`quote_items.section = module.id`).
   - Mão de obra só se `module.show_labor` e horas×taxa > 0.
   - Por módulo: desconto, forma de pagamento, total líquido.
   - Opcionais: `module.notes`; `module.billed_by_name` + `module.billed_by_cnpj` (Faturado por). **Não** imprimir Faturado por global.
   - Create inicia canvas **vazio**; PDF só lista módulos presentes.

4. Divisórias cinza entre módulos quando houver mais de um.

5. **Dados de pagamento / resumo**:
   - Uma linha (ou par) de resumo **por módulo presente** (qtde itens + total líquido), rótulo = título do módulo.
   - Se ainda existirem módulos com `legacy_kind` `implantacao` / `mensalidade`, manter também os rótulos OS VHSYS:
     - `TOTAL DE HORAS/QTDE DE SERVICOS` / `VALOR TOTAL DOS SERVICOS` ← `implantacao`
     - `TOTAL DE PRODUTOS` / `VALOR TOTAL DOS PRODUTOS` ← `mensalidade`
   - `VALOR TOTAL DO ORCAMENTO` = soma dos líquidos de **todos** os módulos presentes.

6. **OBSERVACOES** — `quotes.notes`; imprime o bloco mesmo se vazio (`-`).

7. **Aviso + ticket** (fixo, imediatamente acima das assinaturas):

```
Os valores podem sofrer alteração sem prévio aviso.
Ticket no.:
```

   `Ticket no.:` em branco; se `quotes.tiflux_ticket_number` existir, imprime o número na mesma linha.

8. **Assinaturas** (3 colunas): data do aceite · Assinatura do Prestador · Assinatura do Sacado.

## Fundo

- Página A4 branca. **Sem** barras de marca no topo/lateral, **sem** bandas coloridas de seção.
- Tabelas: header cinza claro, bordas cinza. Sem padrão PCB.

## Formatação / paginação

- Meta: **1 página A4** para orçamento típico.
- Quebras **somente entre blocos lógicos**. Incluir no keep-together o par aviso+ticket+assinaturas.

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
