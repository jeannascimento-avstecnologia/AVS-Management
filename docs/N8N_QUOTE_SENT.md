# quote.sent — aplicado no backend

**Status:** o workflow n8n não aplica mais este evento. `POST /orcamentos/{id}/mark-sent` marca o orçamento `sent` e chama o TiFlux direto (`src/quotes/sent_tiflux.py` + `TifluxClient`). Não há `insert_pending` nem `dispatch_outbox` para `quote.sent`. A auditoria é `log_action` `quote.sent`.

`quote.submit` e o faturamento continuam no outbox (ADR-0003). O JSON `docs/hub/n8n/avs-hub-commercial.workflow.json` ainda tem um stub de `quote.sent`; não ligar esse nó — senão o chamado é atualizado duas vezes.

## Dry-run e credencial

- `HUB_DRY_RUN=true`: não chama o TiFlux. A resposta 202 traz `tiflux.dry_run=true` e o resumo simulado.
- Sem dry-run e com `TIFLUX_API_TOKEN` vazio: 503 `Credenciais TiFlux não configuradas` antes de mudar o status.
- Falha em um passo TiFlux não desfaz o `sent`. O 202 inclui o resumo.

## Resposta 202

`QuoteRead` mais:

```json
{
  "dry_run": false,
  "tiflux": {
    "dry_run": false,
    "stage_ok": true,
    "status_ok": true,
    "responsible_ok": true,
    "answer_ok": true,
    "attachment_ok": true,
    "followers_ok": true,
    "errors": []
  }
}
```

`followers_ok` fica `false` se a lista veio preenchida: o client não tem método de seguidores. O restante segue.

## O que o backend faz

1. Exige `tiflux_ticket_number`. Vazio: erro no resumo, sem inventar chamado.
2. `GET /tickets/{number}`. Estágio e status saem do ticket ou de `GET /desks/{id}` (mesa do ticket, senão `TIFLUX_DESK_COMERCIAL_ID`), pelo nome:
   - estágio `Orçamento enviado`
   - status `Aguardando o cliente`
   Ids resolvidos ficam em cache do processo. Não há id fixo no repo.
3. Responsável: `TIFLUX_QUOTE_SENT_RESPONSIBLE_ID` se > 0; senão `GET /users?name=André` (um match). Se não achar, o PUT segue sem responsável e o resumo avisa.
4. `PUT /tickets/{id}` com `stage_name` `Orçamento enviado`, `stage_id` quando resolvido, `status_id` e `responsible_id` no extra.
5. Lê o PDF (nome UUID sob `HUB_PDF_DIR`, até 25 MB), base64, e `POST /tickets/{number}/answers` com HTML (`<br>`) e `files_base64` `[{filename, base64}]`. Sem arquivo em disco: a mensagem sai sem anexo.
6. Seguidores: só log. Não bloqueia.

Texto da answer: saudação `America/Sao_Paulo` (`Bom dia` antes das 12:00, senão `Boa tarde`) + nome (`contact_name`, senão `client_name`) + `Segue orçamento solicitado.` + mensagem livre do body, se houver.
