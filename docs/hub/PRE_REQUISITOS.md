# Pré-requisitos do hub AVS Management

> **Proveniência:** cópia versionada de `NFE/PRE_REQUISITOS.md` (2026-07-20).  
> Segredos **não** versionados — use env vars ou arquivos locais gitignored.

Verificação automatizada (preferencial):

```bash
cd docs/hub
# 1) Exporte TIFLUX_TOKEN e VHSYS_ACCESS_TOKEN / VHSYS_SECRET_ACCESS_TOKEN
#    (ou arquivos locais fora do git — NUNCA commit)
# 2) Rode:
./verify-all.sh
```

Scripts (nesta pasta):
| Script | O que testa |
|--------|-------------|
| `test-tiflux-capabilities.sh` | Auth JWT + clients/contracts/tickets/desks/billing history + probe pending |
| `test-vhsys-capabilities.sh` | Auth tokens + clientes/OS/notas/receitas (+ probes) |
| `verify-all.sh` | Roda os dois + checklist manual |

---

## 1. APIs — automatizado

### 1.1 TiFlux (já validado com JWT)
- [x] Bearer JWT funciona (`eyJ…`)
- [x] `GET /clients`, `/contracts`, `/tickets`, `/desks`
- [x] `GET /reports/billings/history`
- [ ] **Gap:** faturamentos pendentes / faturar → 404 (aceitar workaround: fila no Management)
- [ ] `POST /tickets` + anexos + resposta HTML *(validar com dry-run depois)*
- [ ] Criar/atualizar **contrato com itens** *(validar na doc/suporte — crítico p/ orçamento→contrato)*
- [ ] Alterar **estágio/kanban** via API

### 1.2 VHSYS
- [ ] Tokens access + secret válidos → `./test-vhsys-capabilities.sh`
- [ ] `GET /clientes` OK
- [ ] `GET /ordens-servico` OK (orçamento)
- [ ] `GET /notas-servico` OK (faturamento)
- [ ] `GET /receitas` OK (contas a receber)
- [ ] Confirmar na doc: **POST** OS, nota, receita, geração/download boleto
- [ ] User-Agent obrigatório configurado (scripts e Management)

### 1.3 Critério Go APIs
| Resultado | Decisão |
|-----------|---------|
| TiFlux leitura OK + VHSYS clientes/OS/notas/receitas OK | **Go** para desenvolvimento hub |
| Falha auth | Regenerar tokens / licença |
| OS ou notas 404 de path | Ajustar path com doc VHSYS; não bloquear auth |

---

## 2. TiFlux produto / cadastro — manual (IDs)

Anotar e guardar no Management (config/env):

- [ ] ID mesa **Comercial** e/ou **Vendas**
- [ ] ID status **Pendente** (e outros usados no kanban)
- [ ] ID prioridade **Baixa**
- [ ] ID estágio “enviado ao cliente” (kanban)
- [ ] Entity/field IDs: informações financeiras do ticket
- [ ] Entity/field IDs: temperatura do lead
- [ ] Comportamento **solicitante customizado** (testar 1 ticket manual)
- [ ] Usuário/API com permissão de **valores** em contratos (já ok no teste)

---

## 3. Negócio / operação — manual

- [ ] Templates de orçamento (implantação + mensalidade) definidos com comercial/financeiro
- [ ] Planos de pagamento pré: 3x sem juros, etc. (% e valor)
- [ ] Lista clientes com **retenção ISS Campinas**
- [ ] Forma de pagamento padrão mensalidade (boleto/Pix)
- [ ] Aceite: **Management = fila oficial** (Excel/TiFlux pendentes deixam de ser SoT)
- [ ] SLA follow-up orçamento (ex.: X dias sem resposta → e-mail)
- [ ] Textos template e-mail cobrança e follow-up comercial

---

## 4. Plataforma — semi-automatizado / ops

- [ ] n8n com URL HTTPS pública (ou VPN) alcançável pelo Management
- [ ] Segredos n8n: TiFlux JWT, VHSYS tokens, webhook secret
- [ ] Management deploy (mesmo host ou staging) com permissões RBAC novas:
  - `orcamentos`, `aprovar_orcamento`, `gerar_contrato`, `faturar`, `aprovar_fatura`
- [ ] Storage de PDFs (disco local / SharePoint / S3)
- [ ] Conta de serviço (não login pessoal da operação)

---

## 5. Dry-runs antes de produção

| # | Teste | Como |
|---|--------|------|
| D1 | Criar ticket teste mesa Comercial | Manual UI ou POST API |
| D2 | Anexar PDF + mudar estágio | Manual / API |
| D3 | Criar OS VHSYS em cliente teste | API/UI |
| D4 | Emitir NF/CR teste (sandbox ou estorno) | VHSYS |
| D5 | Webhook n8n eco (`ping` → 200) | `curl` do Management |
| D6 | Orçamento completo draft só no Management | UI O1 |

---

## Quantos fluxos n8n? (mínimo recomendado)

**Resposta: 2 fluxos principais (+ 1 opcional).**  
Menos que isso vira um monólito lento/difícil de debugar; mais que 4 aumenta manutenção sem ganho.

### Fluxo 1 — `avs-hub-commercial` (orçamento → contrato)
**Um único workflow** com webhook + `Switch` no campo `event`:

| `event` | Ação |
|---------|------|
| `quote.submit` | Cria OS VHSYS + ticket TiFlux + anexa PDF/HTML |
| `quote.sent` | Atualiza estágio/status kanban |
| `quote.approved` | Cria contrato TiFlux (itens do payload) |
| `quote.followup` | (chamado pelo Fluxo 3 ou sub-nó) e-mail |

**Por que 1 só:** mesmo domínio (comercial), mesmos credentials, payload do orçamento reutilizado; Switch mantém clareza.

### Fluxo 2 — `avs-hub-billing` (faturamento mensal)
Webhook `billing.approved` / `billing.nf_prefeitura`:

1. Branch retenção  
2. VHSYS NF+CR+boleto (ou CR líquido)  
3. Ticket cobrança TiFlux + 3 anexos  
4. Callback Management  

Separado do comercial para **não misturar** falhas de NF com falhas de OS/ticket de venda (velocidade de retry e permissões diferentes).

### Fluxo 3 (opcional) — `avs-hub-timers`
- Cron / Wait: orçamentos `sent` sem resposta há X dias → e-mail  
- Cron: retries de `billing` com status `erro`  

Pode ficar **dentro** do Fluxo 1/2 com nós Wait se o volume for baixo; extraia só se os waits poluírem o fluxo principal.

### O que **não** fazer
- 1 fluxo por cliente ou por etapa da UI (explode manutenção)
- n8n como fonte de verdade (dados ficam no Management)
- Misturar faturamento e orçamento no mesmo Switch sem necessidade (harder on-call)

### Diagrama mínimo

```
Management ──webhook──► [1 commercial] ──► TiFlux / VHSYS
         └──webhook──► [2 billing]     ──► VHSYS / TiFlux
                              ▲
         cron (opc) ──► [3 timers] ────┘
```

---

## Ordem sugerida de verificação (hoje)

1. `./verify-all.sh` (TiFlux + VHSYS)  
2. Anotar IDs de mesa/estágio/campos no TiFlux (manual, 30–60 min)  
3. Validar POST ticket + OS em ambiente real (1 cliente teste)  
4. Subir webhooks n8n vazios (só log) e pingar do Management  
5. Só então codar módulos O1 / F1A no Management  

Referências (repo): `docs/hub/sketch-fluxo-completo.html` · `docs/hub/MODULO_ORCAMENTO_CONTRATO.md` · `docs/hub/CHECKLIST_PRE_AUTOMACAO.md`
