# Spec — Mensalidades, versões e PDF

> Status: spec para implementação (fast-follow) · 2026-09-03
> SoT relacionado: `MODULO_ORCAMENTO_CONTRATO.md` (fluxo) e `SPEC_PDF_ORCAMENTO.md` (render)

## 1) Objetivo
Adicionar ao fluxo de **Orçamento → PDF**:

1. **Versões** (histórico consultável) criadas ao clicar em **"Salvar orçamento"**.
2. Um botão de **Mensalidades** no **passo 3 (Revisão)** para selecionar linhas (de quaisquer blocos) que viram cobrança mensal, e dividir o valor em múltiplas mensalidades.
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
- `mensalidades_config`:
  - lista de linhas/licenças selecionadas (origem)
  - lista de mensalidades criadas (fornecedor/intermediador/...) e valores

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

## 5) Layout da tabela (ITEM/QTDADE/V. UNIT./V. TOTAL)

### 5.1 Mudanças de layout
- Aumentar espaço do texto do campo `ITEM`:
  - reduzir um pouco as partes de `QTDADE`, `V. UNIT.` e `V. TOTAL`.
- Organizar alinhamento para melhorar legibilidade:
  - `QTDADE` deve ficar melhor posicionado visualmente (preferência: número centralizado/abaixo do label).
  - Aplicar alinhamento coerente em todos os campos numéricos.

### 5.2 Quebra de linha
- Se o texto em `ITEM` exceder o tamanho da caixa, **quebrar em linhas** ao invés de truncar.

## 6) Mensalidades (passo 3) e separação no PDF

### 6.1 UI — botão de mensalidades
- No passo 3, adicionar um botão **"Mensalidades"**.
- A modal deve permitir:
  - selecionar linhas de itens de **quaisquer blocos** (não limitar à section `mensalidade`)
  - criar **N mensalidades** (ex.: fornecedor + intermediador)
  - mudar o valor cobrado em cada mensalidade

### 6.2 Regra dinâmica de valor
- A soma dos valores das mensalidades criadas deve respeitar o total da(s) licença(s) selecionada(s).
- Regra definida para este ciclo:
  - `soma(mensalidades) == soma(total_licenca_selecionada)`

### 6.3 Validação
- Se o usuário alterar um valor e a regra for quebrada, o UI deve impedir salvar/criar mensalidades ou ajustar automaticamente o último campo (com mensagem visível).

### 6.4 PDF — seção exclusiva
- O PDF deve renderizar uma seção **somente de MENSALIDADES**.
- Essa seção fica **fora do `VALOR TOTAL DO ORCAMENTO`**.
- A implementação (Implantação + outros módulos de implementação) continua compondo o `VALOR TOTAL DO ORCAMENTO`.

## 7) Contratos

Este spec cobre as **versões de Orçamento** e deixa o desenho pronto para que, quando o fluxo de contrato TiFlux existir, também seja possível criar **versões de contratos** vinculadas a uma versão de orçamento.

