/**
 * Micro-benchmark local (sem rede/DB) — espelho de frontend/src/lib/quoteLead.ts
 * Uso: node scripts/bench_quote_lead.mjs
 */
const OPEN = new Set(['draft', 'submitted', 'sent'])

function isOpen(status) {
  return OPEN.has(status)
}

function countByLead(quotes) {
  const counts = { frio: 0, morno: 0, quente: 0 }
  for (const quote of quotes) {
    if (!isOpen(quote.status)) continue
    const temp = quote.lead_temperature
    if (temp === null) continue
    counts[temp] += 1
  }
  return counts
}

function sumByLead(quotes) {
  const sums = { frio: 0, morno: 0, quente: 0 }
  for (const quote of quotes) {
    if (!isOpen(quote.status)) continue
    const temp = quote.lead_temperature
    if (temp === null) continue
    const total = quote.items.reduce((acc, item) => acc + item.total_value, 0)
    sums[temp] += total
  }
  return sums
}

function hotPendingQuotes(quotes, limit = 5) {
  return quotes
    .filter((q) => isOpen(q.status) && q.lead_temperature === 'quente')
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, limit)
}

/** Uma passagem: count + sum (mitigação candidata). */
function statsByLead(quotes) {
  const counts = { frio: 0, morno: 0, quente: 0 }
  const sums = { frio: 0, morno: 0, quente: 0 }
  for (const quote of quotes) {
    if (!isOpen(quote.status)) continue
    const temp = quote.lead_temperature
    if (temp === null) continue
    counts[temp] += 1
    let total = 0
    for (const item of quote.items) total += item.total_value
    sums[temp] += total
  }
  return { counts, sums }
}

const TEMPS = ['frio', 'morno', 'quente', null]
const STATUSES = ['draft', 'submitted', 'sent', 'approved', 'rejected', 'contracted']

function makeQuotes(n, itemsPerQuote) {
  const now = Date.now()
  const quotes = []
  for (let i = 0; i < n; i++) {
    const items = []
    for (let j = 0; j < itemsPerQuote; j++) {
      items.push({ total_value: 100 + j * 10 + (i % 7) })
    }
    quotes.push({
      id: i + 1,
      status: STATUSES[i % STATUSES.length],
      lead_temperature: TEMPS[i % TEMPS.length],
      updated_at: new Date(now - i * 60_000).toISOString(),
      items,
    })
  }
  return quotes
}

function bench(label, fn, iterations) {
  // warmup
  for (let i = 0; i < 5; i++) fn()
  const t0 = performance.now()
  for (let i = 0; i < iterations; i++) fn()
  const ms = performance.now() - t0
  return { label, iterations, totalMs: ms, perCallMs: ms / iterations }
}

function main() {
  const scenarios = [
    { n: 100, items: 5, iters: 2000 },
    { n: 1000, items: 10, iters: 500 },
    { n: 10_000, items: 20, iters: 50 },
  ]

  const rows = []
  for (const { n, items, iters } of scenarios) {
    const quotes = makeQuotes(n, items)
    const a = bench(`countByLead n=${n} items=${items}`, () => countByLead(quotes), iters)
    const b = bench(`sumByLead n=${n} items=${items}`, () => sumByLead(quotes), iters)
    const c = bench(`hotPendingQuotes n=${n}`, () => hotPendingQuotes(quotes, 5), iters)
    const d = bench(`count+sum (2 passes) n=${n}`, () => {
      countByLead(quotes)
      sumByLead(quotes)
    }, iters)
    const e = bench(`statsByLead (1 pass) n=${n}`, () => statsByLead(quotes), iters)
    rows.push(a, b, c, d, e)

    // sanity
    const counts = countByLead(quotes)
    const sums = sumByLead(quotes)
    const stats = statsByLead(quotes)
    if (JSON.stringify(counts) !== JSON.stringify(stats.counts)) {
      throw new Error('statsByLead counts diverge from countByLead')
    }
    for (const k of ['frio', 'morno', 'quente']) {
      if (Math.abs(sums[k] - stats.sums[k]) > 1e-6) {
        throw new Error(`statsByLead sums diverge on ${k}`)
      }
    }
  }

  console.log('=== bench_quote_lead (synthetic, local) ===')
  for (const r of rows) {
    console.log(
      `${r.label.padEnd(42)} iters=${String(r.iterations).padStart(5)}  ` +
        `total=${r.totalMs.toFixed(2)}ms  per=${r.perCallMs.toFixed(4)}ms`,
    )
  }
}

main()
