# Spec — Mensalidades, versões e PDF

> Status: spec para implementação (fast-follow) · 2026-09-03
> SoT relacionado: `MODULO_ORCAMENTO_CONTRATO.md` (fluxo) e `SPEC_PDF_ORCAMENTO.md` (render)

## 1) Objetivo
Adicionar ao fluxo de **Orçamento → PDF**:

1. **Versões** (histórico consultável) criadas ao clicar em **"Salvar orçamento"**.
2. Check **Mensalidade** em cada bloco no **passo 1 (Orçamento)** — override manual (VHSYS não distingue). Blocos flagados saem do total de implementação e entram na seção PDF / bucket recorrente do passo 3.
3. Atualizações no **PDF**:
   - Exibir **"vX"** em fonte menor ao lado de `M{id}`.
   - Mostrar **"Ticket no.:"** dentro do campo **Observações** (passo 3) e permitir edição.
   - Mostrar **desconto apenas quando existir desconto** preenchido pelo usuário.
   - Melhorar layout/alinhamento e quebra de linha na tabela `ITEM`.
   - Renderizar **uma seção exclusiva de MENSALIDADES** que fica **fora do `VALOR TOTAL DO ORCAMENTO`**.

## 2) Versões (Orçamento)

### 2.1 Gatilho
- O usuário clica no botão **"Salvar orçamento"** no passo 3.
- Cada clique deve criar uma **nova versão** `v1, v2, v3...` com snapshot do estado necessário para renderizar:
  - canvas (modules + quote_items)
  - `notes` (Observações)
  - configuração/resultado de **Mensalidades**

### 2.2 Conteudo do snapshot
O snapshot deve ser suficiente para que o PDF renderize exatamente como estava no momento do clique:
- `modules_json` e `quote_items`
- `notes` (string)
- `mensalidades_config`: `modules[].is_mensalidade` no snapshot de `modules_json` (legado: `monthly_draft_json` se o campo não existia)

### 2.3 Exibição no PDF
- No cabeçalho, manter `Orçamento : M{id}` e exibir ao lado:
  - `vX` com fonte menor (ex.: 80% do tamanho do texto principal)

## 3) Observações e "Ticket no.:"

### 3.1 Onde deve aparecer
- O trecho:
  - `Os valores podem sofrer alteracao sem previo aviso.`
  - `Ticket no.:`
- deve aparecer **dentro do campo Observações** do passo 3 (textarea), e o usuário consegue editar esse conteúdo.

### 3.2 Como o ticket é preenchido
- Se existir `tiflux_ticket_number` na versão atual, o UI deve pré-preencher `Ticket no.: <numero>`.
- Se não existir, deve pré-preencher `Ticket no.:` em branco.
- A edição do usuário no textarea sempre prevalece para o PDF daquela versão.

### 3.3 Regras no PDF
- O PDF deve **imprimir somente** o conteúdo do campo `quotes.notes` no bloco **OBSERVACOES**.
- O PDF não deve ter um trecho fixo separado de "Aviso + Ticket" no rodapé. (Eliminação do bloco fixo para evitar duplicidade.)

## 4) Desconto condicional no PDF

### 4.1 Requisito
- Mostrar o trecho de desconto apenas se o usuário preencher desconto no passo 3:
  - `discount_pct` (ou `discount_value`)
- Se não houver desconto preenchido, **não exibir** o trecho de desconto naquele módulo.

### 4.2 Interpretação prática
- Considerar “há desconto” quando:
  - `discount_pct != null` OU `discount_value != null`
  - e o desconto aplicado (calculado) for > 0 (quando ambos existirem, usar o cálculo já existente de desconto)

## 5) Layout da tabela (ITEM/QTDE/V. UNIT./V. TOTAL)

### 5.1 Mudanças de layout
- Aumentar espaço do texto do campo `ITEM`:
  - reduzir um pouco as partes de `QTDE`, `V. UNIT.` e `V. TOTAL`.
- Organizar alinhamento para melhorar legibilidade:
  - `QTDE` deve ficar melhor posicionado visualmente (preferência: número centralizado/abaixo do label).
  - Aplicar alinhamento coerente em todos os campos numéricos.

### 5.2 Quebra de linha
- Se o texto em `ITEM` exceder o tamanho da caixa, **quebrar em linhas** ao invés de truncar.

## 6) Mensalidades (passo 1) e separação no PDF

### 6.1 UI — check no bloco
- No card de cada bloco (passo 1, ao lado de **Simplificar**): checkbox **Mensalidade**.
- Flag = `QuoteModule.is_mensalidade` (override). Sem inferência VHSYS.
- Default: `true` no preset Restaurar Mensalidade (`legacy_kind=mensalidade`); `false` em bloco em branco / biblioteca (salvo se o template gravar o flag).
- Campo ausente no JSON antigo + `legacy_kind=mensalidade` → `true`.
- **Não** há botão/dialog Mensalidades na Revisão. Endpoints `POST/PUT …/mensalidades` permanecem para snapshots antigos; a UI nova não grava `monthly_draft_json`.

### 6.2 Custo (passo 3)
- Split fornecedor/AVS **fora** deste fluxo. Passo 3 (Custo vs lucro) trata itens dos módulos flagados como `bucket=recurring`.

### 6.3 PDF — seção exclusiva
- O PDF deve renderizar uma seção **somente de MENSALIDADES** com os itens (ou linha simplificada) dos módulos flagados, agrupados por `billed_by_name`.
- Essa seção fica **fora do `VALOR TOTAL DO ORCAMENTO`**.
- A implementação (módulos **sem** o flag) continua compondo o `VALOR TOTAL DO ORCAMENTO`.

## 7) Contratos

Este spec cobre as **versões de Orçamento** e deixa o desenho pronto para que, quando o fluxo de contrato TiFlux existir, também seja possível criar **versões de contratos** vinculadas a uma versão de orçamento.

