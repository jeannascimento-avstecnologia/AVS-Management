# n8n — Hub AVS Management

Workflows documentados para O2/F1. Segredos só em env/Credentials — **nunca** neste diretório.

| Workflow | Spec | JSON import | Status |
|----------|------|-------------|--------|
| `avs-hub-commercial` | [avs-hub-commercial.md](./avs-hub-commercial.md) | [avs-hub-commercial.workflow.json](./avs-hub-commercial.workflow.json) | O2.3 — esqueleto HMAC + dry-run + callback; live TiFlux/VHSYS = wiring ops |
| `avs-hub-billing` | [avs-hub-billing.md](./avs-hub-billing.md) | [avs-hub-billing.workflow.json](./avs-hub-billing.workflow.json) | F1.3 — spec pronta / import manual; live NF/CR/ticket = wiring ops |

Contrato de payloads / HMAC: [ADR-0003](../ADR-0003-hmac-outbox-dry-run.md).  
Go/No-Go APIs: [O2.0](../O2.0-api-go-nogo.md).  
Aceite MVP dry-run: [P1-aceitacao-mvp.md](../P1-aceitacao-mvp.md) · índice: [../README.md](../README.md).
