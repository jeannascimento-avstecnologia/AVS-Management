# SPEC — Debug Report (“Reportar problema”)

Status: **aprovada para implementação** (paridade AVS Career, destino e-mail).  
Escopo: **MVP**. Sem tabela de tickets.

## Objetivo

Qualquer usuário autenticado envia um relatório de bug com captura de tela, log da sessão e texto livre. O backend dispara e-mail SMTP para destinatários de ambiente. Identidade do reporter vem da sessão, nunca do body.

## UX

- Botão no **rodapé da sidebar**, acima de Sair: ícone Lucide `Bug`, texto **“Reportar problema”**. Sidebar recolhida: só ícone + `sr-only` + tooltip.
- Enquanto captura: **“Capturando...”**, botão desabilitado.
- Atalho: **Ctrl+Shift+D** (Windows/Linux) ou **Cmd+Shift+D** (Mac).
- Modal **“Reportar problema”**: título, descrição, observações (opcional), preview da captura, accordion **“Registro: N eventos”**, Cancelar / **Enviar relatório** (envio exige screenshot).
- Toasts: sucesso **“Relatório enviado. Obrigado!”**; falha de captura **“Não foi possível capturar a tela. Tente novamente.”**; erros de envio em português (mensagem da API).

## Contrato `POST /debug-reports`

Auth: cookie de sessão + `X-CSRF-Token` (não isentar CSRF). `201 { "success": true }`.

Body (espelho Zod/Pydantic):

- `title` 1–200
- `description` 1–5000
- `notes` opcional ≤2000
- `screenshotBase64` 1…4 144 576 chars (data URL PNG permitido)
- `sessionLog` ≤500 eventos (`ts`, `type`, `message` ≤2000, `meta` opcional)
- `clientMeta`: `url`, `userAgent`, `viewport {width,height}`, `app` = `"avs-management"`

Tipos de evento: `navigation` | `click` | `console.error` | `console.warn` | `error` | `unhandledrejection` | `api.error`.

Cliente: buffer FIFO de **200** eventos. Servidor aceita até 500.

## Coletor (aba)

Instala uma vez no layout autenticado: `console.error/warn`, cliques (exceto password/campos sensíveis), `error`, `unhandledrejection`, navegação, erros de `fetch` same-origin (exceto `/debug-reports`). Redação de Bearer e padrões `password|secret|api_key` no cliente e de novo no servidor.

## Regras de backend

1. `userId`/e-mail da sessão (`require_user`).
2. Rate limit: **5 envios / usuário / hora** (mapa em memória do processo).
3. Screenshot > 4MB chars → 400.
4. `DEBUG_REPORT_RECIPIENTS` vazio → 400.
5. SMTP ausente → erro claro (503).
6. HTML do e-mail (banner, descrição, notas, URL, viewport, UA, screenshot inline, logs coloridos) + anexos `screenshot.png` e `session-log.json`. `Reply-To` = e-mail do reporter.
7. Audit: `log_action(action="debug_report", resource="debug-report")`. Sem persistir o screenshot no banco.

## Env

| Variável | Onde | Uso |
|----------|------|------|
| `DEBUG_REPORT_RECIPIENTS` | API | CSV de e-mails (obrigatório para enviar) |
| `SMTP_*` | API | Mesmo transporte da recuperação de senha |

## Fora de escopo

Tickets no banco, Resend, workspace/empresa, log de dispatch por tenant.
