# Checklist pré-automação — Faturamento mensal AVS

> **Proveniência:** cópia versionada de `NFE/CHECKLIST_PRE_AUTOMACAO.md` (2026-07-20). SoT no repo: `docs/hub/`.

Use este arquivo **antes** de desenvolver o fluxo TiFlux → VHSYS → ticket.  
Marque cada item só quando estiver **verificado com evidência** (print, doc, token de teste ou emissão dry-run).

**Escopo alvo (Fase 1):** integrar TiFlux → VHSYS + anexos no ticket (com aprovação humana).  
**Fora da Fase 1:** reformular Excel, Grafana → contrato, 100% NFS-e prefeitura sem humano.

---

## Status geral

| Campo | Valor |
|-------|--------|
| Responsável técnico | |
| Responsável financeiro/ops | |
| Data início do checklist | |
| Meta: dry-run aprovado até | |
| Go / No-go Fase 1 | ☐ Go · ☐ No-go · ☐ Parcial |

---

## 1. APIs e autenticação

### 1.1 TiFlux
- [ ] Existe API (ou integração oficial) para **listar faturamentos pendentes**
- [ ] Existe API para **faturar** (total / parcial)
- [ ] Existe API para **download do relatório detalhado**
- [ ] Existe API para **tickets** (localizar ticket de cobrança do cliente)
- [ ] Existe API para **anexar arquivos** no ticket (limite 25 MB ok)
- [ ] Existe API para **enviar mensagem / template** ao cliente
- [ ] Existe API para **comunicação interna** + fechar ticket
- [ ] Auth definida (token / OAuth / API key) — **conta de serviço**, não login pessoal
- [ ] Rate limit e ambiente de teste documentados
- [ ] Evidência anexada: swagger / Postman / captura de rede / e-mail do suporte TiFlux

**Notas / links:**

### 1.2 VHSYS
- [ ] Existe API para **criar NF / serviço**
- [ ] Existe API para **contas a receber (novo recebimento)**
- [ ] Existe API para **gerar e baixar boleto**
- [ ] Auth definida com conta de serviço
- [ ] Ambiente sandbox ou conta de teste disponível
- [ ] Comportamento com **retenção ISS** documentado (sucesso / erro / campos)
- [ ] Evidência anexada: doc oficial / suporte VHSYS / teste dry-run

**Notas / links:**

### 1.3 Integração já existente
- [ ] Validado o que o botão/fluxo TiFlux → ERP (ex.: “criar venda”) **já faz hoje**
- [ ] Está claro o que **ainda falta** digitar manualmente após esse botão
- [ ] Decisão: reutilizar integração nativa **ou** orquestrar via n8n/API própria

**Decisão registrada:**

---

## 2. Cadastro canônico (clientes e serviços)

- [ ] Lista mestra de clientes com: nome TiFlux, nome VHSYS, nome Excel, **CNPJ**
- [ ] Aliases / divergências de nome mapeados (ou plano para padronizar)
- [ ] Mapeamento contrato/serviço TiFlux → categoria/serviço VHSYS
- [ ] Flag por cliente: **tem retenção ISS** (sim/não)
- [ ] Flag por cliente: **boleto** (padrão) vs **Pix** (exceção)
- [ ] E-mail financeiro de cobrança por cliente validado
- [ ] Dia de vencimento e regras especiais (anual, IPCA, etc.) pelo menos nos clientes piloto

**Arquivo da lista mestra (caminho/link):**

---

## 3. Regras de negócio fechadas (por escrito)

- [ ] Data-base nos faturamentos pendentes: **sempre futura** (regra confirmada)
- [ ] Sempre incluir **contratos + valores avulsos**
- [ ] Linhas com valor zero → faturamento **parcial**
- [ ] Descrição padrão da NF (ex.: “mensalidade” / suporte técnico)
- [ ] Quantidade de parcelas padrão (ex.: 1)
- [ ] Forma de pagamento padrão = boleto; Pix só com flag
- [ ] Com retenção: NF na **prefeitura**; VHSYS só CR com **valor líquido**
- [ ] Gate humano **obrigatório** antes de emitir/enviar (Fase 1)
- [ ] Quem aprova (nome/papel) e SLA de aprovação definidos
- [ ] Ticket: anexos obrigatórios = **relatório + NF + boleto**
- [ ] Template de e-mail de cobrança aprovado pelo financeiro
- [ ] Texto da comunicação interna (“cobrança enviada…”) aprovado

**Documento de regras (caminho/link):**

---

## 4. Exceção Prefeitura Campinas (NFS-e)

- [ ] Lista oficial de clientes com retenção (fonte: financeiro)
- [ ] Fluxo assistido definido: humano emite NFS-e → informa nº da NF → automação segue
- [ ] Campos mínimos que o humano devolve à automação (nº NF, valor líquido, data)
- [ ] Acordo explícito: **não** automatizar 100% o portal da prefeitura na Fase 1
- [ ] Responsável operacional pela fila de retenção

**Responsável retenção:**

---

## 5. Segurança, LGPD e auditoria

- [ ] Contas de serviço criadas (TiFlux / VHSYS / n8n) — sem senha pessoal
- [ ] Permissões mínimas necessárias (princípio do menor privilégio)
- [ ] Segredos em cofre/env seguro (não em planilha nem no chat)
- [ ] Modo **dry-run** obrigatório antes do primeiro envio real
- [ ] Log auditável: cliente, competência, valores, IDs NF/boleto/ticket, aprovador, timestamp
- [ ] Política de retenção dos PDFs/anexos definida
- [ ] Tratamento de dados financeiros alinhado à LGPD interna

**Onde ficará o log:**

---

## 6. Operação e volume

- [ ] Volume médio e pico de faturamentos/dia estimados
- [ ] Janela operacional (ex.: “tudo do dia até __h”)
- [ ] Quem opera a fila de falhas / retries
- [ ] Canal de escalação (Teams/e-mail) definido
- [ ] Runbook de “o que fazer se a API cair”
- [ ] Critério de rollback (voltar 100% manual) documentado

**Volume estimado:** ____ / dia · **Pico:** ____

---

## 7. Escopo e alinhamento com o time

- [ ] Fase 1 confirmada com Alinne / Susana / Jean (ou stakeholders atuais)
- [ ] Excel **fora** da automação profunda na Fase 1 (só entrada/status se combinado)
- [ ] Grafana / adendos / cancelamento de contrato = **Fase 2**
- [ ] Critérios de sucesso da Fase 1 escritos (ex.: zero digitação no caminho feliz)
- [ ] Riscos aceitos registrados (RPA prefeitura, nomes divergentes, etc.)

**Critérios de sucesso:**

1.
2.
3.

---

## 8. Evidências mínimas (piloto técnico)

Executar **antes** de construir o fluxo completo.

### 8.1 Ambiente
- [ ] Credenciais de teste válidas (TiFlux + VHSYS)
- [ ] Cliente piloto **simples** escolhido (ex.: 1 serviço, sem retenção)
- [ ] Cliente piloto **com avulso** escolhido
- [ ] Cliente piloto **com retenção** escolhido (só para validar branch assistida)

### 8.2 Testes
- [ ] Dry-run: listar pendentes do piloto simples via API/integração
- [ ] Dry-run: obter relatório detalhado sem impacto no cliente
- [ ] Dry-run: criar recebimento/NF de teste no VHSYS (ou sandbox) e apagar/estornar se preciso
- [ ] Dry-run: anexar arquivos em ticket de teste (não enviar ao cliente)
- [ ] Simulação retenção: checklist assistido preenchido 1x com sucesso

### 8.3 Decisão Go / No-go
- [ ] APIs cobrem o caminho feliz sem RPA
- [ ] Cadastro canônico dos pilotos está ok
- [ ] Financeiro aprovou template + gate humano
- [ ] Riscos residuais aceitos por escrito

| Resultado | Data | Assinatura / responsável |
|-----------|------|---------------------------|
| ☐ Go Fase 1 | | |
| ☐ No-go (bloquear até ___) | | |
| ☐ Go parcial (só até VHSYS, ticket manual) | | |

---

## 9. Entregáveis que devem existir ao fechar o checklist

- [ ] Lista mestra clientes (planilha ou DB)
- [ ] Doc de regras de negócio (1–2 páginas)
- [ ] Matriz API TiFlux / VHSYS (endpoint × status: ok / falta / workaround)
- [ ] Design do fluxo Fase 1 (usar `sketch-fluxo-faturamento.html` + análise)
- [ ] Plano de piloto (datas, clientes, responsável)

---

## 10. Próximo passo após Go

1. Implementar orquestração (n8n ou serviço) só do **caminho feliz** do piloto simples  
2. Incluir gate de aprovação  
3. Incluir branch retenção assistida  
4. Só então ampliar para o restante da carteira  

Referências no repo:
- `docs/hub/ANALISE_PROJETO_AUTOMACAO.md`
- `docs/hub/sketch-fluxo-faturamento.html`
- Transcrição bruta: `NFE/transcricao.txt` (fora do git; reunião 08/06/2026)
