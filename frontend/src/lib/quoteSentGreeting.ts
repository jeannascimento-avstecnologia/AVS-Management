/** Espelho de src/quotes/sent_message.py — preview. O servidor recalcula no mark-sent. */

const SAO_PAULO = 'America/Sao_Paulo'
const STANDARD_LINE = 'Segue orçamento solicitado.'

export function quoteSentGreeting(recipientName: string, now: Date = new Date()): string {
  const hour = Number(
    new Intl.DateTimeFormat('en-US', {
      timeZone: SAO_PAULO,
      hour: 'numeric',
      hourCycle: 'h23',
    }).format(now),
  )
  const salute = hour < 12 ? 'Bom dia' : 'Boa tarde'
  const name = recipientName.trim() || 'cliente'
  return `${salute}, ${name}.\n${STANDARD_LINE}`
}
