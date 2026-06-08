import { formatCnpj, formatDate } from './format'

const TF_LABELS: Record<string, string> = {
  id: 'Código TiFlux', name: 'Nome fantasia', social: 'Razão social', social_revenue: 'CNPJ',
  status: 'Situação', form_of_payment: 'Forma de pagamento', billing_report_type: 'Tipo de faturamento',
  equipment_counter: 'Equipamentos vinculados', group_counter: 'Grupos vinculados', max_agents: 'Máx. agentes',
  email_financial: 'E-mail financeiro', estadual_registration: 'Inscrição estadual',
  municipal_registration: 'Inscrição municipal', authorization_flow: 'Fluxo de autorização',
}

const VH_LABELS: Record<string, string> = {
  id_cliente: 'Código VHSYS', razao_cliente: 'Razão social', fantasia_cliente: 'Nome fantasia',
  cnpj_cliente: 'CNPJ', tipo_pessoa: 'Tipo de pessoa', tipo_cadastro: 'Tipo de cadastro',
  situacao_cliente: 'Situação', endereco_cliente: 'Endereço', numero_cliente: 'Número',
  complemento_cliente: 'Complemento', bairro_cliente: 'Bairro', cep_cliente: 'CEP',
  cidade_cliente: 'Cidade', uf_cliente: 'UF', referencia_cliente: 'Referência',
  tel_destinatario_cliente: 'Telefone', email_cliente: 'E-mail', doc_destinatario_cliente: 'Documento destinatário',
  limite_credito: 'Limite de crédito', data_cad_cliente: 'Data de cadastro',
  consumidor_final: 'Consumidor final', modalidade_frete: 'Modalidade de frete',
  ultrapassar_limite_credito: 'Ultrapassar limite de crédito', multiempresa: 'Multiempresa',
  negativado: 'Negativado', negativado_serasa: 'Negativado Serasa',
}

const TF_SECTIONS = [
  { title: 'Identificação', keys: ['id', 'name', 'social', 'social_revenue', 'status'] },
  { title: 'Financeiro', keys: ['form_of_payment', 'billing_report_type', 'email_financial'] },
  { title: 'Cadastro fiscal', keys: ['estadual_registration', 'municipal_registration', 'authorization_flow'] },
  { title: 'Resumo de vínculos', keys: ['equipment_counter', 'group_counter', 'max_agents'] },
]

const VH_SECTIONS = [
  { title: 'Identificação', keys: ['id_cliente', 'razao_cliente', 'fantasia_cliente', 'cnpj_cliente', 'tipo_pessoa', 'tipo_cadastro', 'situacao_cliente'] },
  { title: 'Endereço', keys: ['endereco_cliente', 'numero_cliente', 'complemento_cliente', 'bairro_cliente', 'cep_cliente', 'cidade_cliente', 'uf_cliente', 'referencia_cliente'] },
  { title: 'Contato', keys: ['tel_destinatario_cliente', 'email_cliente', 'doc_destinatario_cliente'] },
  { title: 'Financeiro', keys: ['limite_credito', 'ultrapassar_limite_credito', 'consumidor_final', 'modalidade_frete', 'multiempresa'] },
  { title: 'Datas', keys: ['data_cad_cliente'] },
  { title: 'Restrições', keys: ['negativado', 'negativado_serasa'] },
]

const TF_HIDDEN = new Set(['desk_ids', 'technical_group_ids', 'address_ids', 'contact_ids', 'logo', 'anotations'])
const VH_HIDDEN = new Set(['lixeira', 'categoria', 'cidade_cliente_cod', 'id_registro'])

const TF_VALUE_MAPS: Record<string, Record<string, string>> = {
  form_of_payment: { BOLETO: 'Boleto', CREDIT_CARD: 'Cartão de crédito', PIX: 'PIX' },
  billing_report_type: { detailed_with_appointment: 'Detalhado com apontamentos', simplified: 'Simplificado' },
}

function humanizeKey(key: string): string {
  return key.replace(/_cliente$/, '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function formatQueryDisplay(query: string): string {
  const digits = String(query || '').replace(/\D/g, '')
  if (digits.length === 14) return formatCnpj(digits)
  return query || ''
}

function formatDisplayValue(key: string, val: unknown, system: 'tiflux' | 'vhsys'): string {
  if (val === null || val === undefined || val === '') return '—'
  if (typeof val === 'boolean') {
    if (key === 'status') return val ? 'Ativo' : 'Inativo'
    return val ? 'Sim' : 'Não'
  }
  if (key === 'social_revenue' || key === 'cnpj_cliente') return formatCnpj(String(val))
  if (key.startsWith('data_') || key.endsWith('_at')) return formatDate(String(val))
  if (system === 'tiflux' && TF_VALUE_MAPS[key]?.[String(val)]) return TF_VALUE_MAPS[key][String(val)]
  if (key === 'consumidor_final') return val === '1' || val === 1 ? 'Sim' : 'Não'
  if (key === 'ultrapassar_limite_credito') return val === 1 || val === true ? 'Permitido' : 'Não permitido'
  if (key === 'tipo_pessoa') return val === 'PJ' ? 'Pessoa jurídica' : val === 'PF' ? 'Pessoa física' : String(val)
  if (Array.isArray(val)) {
    if (!val.length) return '—'
    if (val.every((x) => typeof x !== 'object')) return val.join(', ')
    return `${val.length} registro(s)`
  }
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

export type ReportRow = { label: string; value: string }
export type ReportSection = { title: string; rows: ReportRow[] }
export type ReportList = { title: string; items: string[] }

function buildSections(
  obj: Record<string, unknown>,
  sections: { title: string; keys: string[] }[],
  labelMap: Record<string, string>,
  hidden: Set<string>,
  system: 'tiflux' | 'vhsys',
): ReportSection[] {
  const used = new Set(hidden)
  const result: ReportSection[] = []

  for (const sec of sections) {
    const rows = sec.keys
      .filter((k) => Object.prototype.hasOwnProperty.call(obj, k))
      .map((k) => {
        used.add(k)
        return { label: labelMap[k] || humanizeKey(k), value: formatDisplayValue(k, obj[k], system) }
      })
    if (rows.length) result.push({ title: sec.title, rows })
  }

  const rest = Object.keys(obj)
    .filter((k) => !used.has(k) && obj[k] !== null && obj[k] !== '' && !(Array.isArray(obj[k]) && !(obj[k] as unknown[]).length))
    .filter((k) => typeof obj[k] !== 'object' || Array.isArray(obj[k]))
    .sort()

  if (rest.length) {
    result.push({
      title: 'Outros dados',
      rows: rest.map((k) => ({
        label: labelMap[k] || humanizeKey(k),
        value: formatDisplayValue(k, obj[k], system),
      })),
    })
  }

  return result
}

export type ConsultReportData = {
  query: string
  tiflux: {
    skipped?: boolean
    success?: boolean
    error?: string
    data?: {
      client?: Record<string, unknown>
      entities?: Array<Record<string, unknown>>
      desks?: Array<Record<string, unknown>>
      technical_groups?: Array<Record<string, unknown>>
    }
  }
  vhsys: {
    skipped?: boolean
    success?: boolean
    error?: string
    data?: Record<string, unknown>
  }
}

export type ParsedConsultReport = {
  query: string
  tiflux: {
    status: 'skipped' | 'error' | 'ok'
    message?: string
    lists: ReportList[]
    sections: ReportSection[]
    entities: { name: string; description?: string; fields: ReportRow[] }[]
  }
  vhsys: {
    status: 'skipped' | 'error' | 'ok'
    message?: string
    category?: string
    lists: ReportList[]
    sections: ReportSection[]
  }
}

export function parseConsultReport(data: Record<string, unknown>): ParsedConsultReport {
  const tf = (data.tiflux || {}) as ConsultReportData['tiflux']
  const vh = (data.vhsys || {}) as ConsultReportData['vhsys']

  const tiflux: ParsedConsultReport['tiflux'] = {
    status: 'ok',
    lists: [],
    sections: [],
    entities: [],
  }
  const vhsys: ParsedConsultReport['vhsys'] = {
    status: 'ok',
    lists: [],
    sections: [],
  }

  if (tf.skipped) {
    Object.assign(tiflux, { status: 'skipped' as const, message: 'Não consultado.' })
  } else if (!tf.success) {
    Object.assign(tiflux, { status: 'error' as const, message: tf.error || 'Falha ao carregar' })
  } else {
    const profile = tf.data || {}
    const client = (profile.client || {}) as Record<string, unknown>
    const entities = (profile.entities || []) as Array<Record<string, unknown>>

    if (profile.desks?.length) {
      tiflux.lists.push({
        title: 'Mesas de serviço',
        items: profile.desks.map((d) => `${d.display_name || d.name || 'Mesa'}${d.active === false ? ' (inativa)' : ''}`),
      })
    }
    if (profile.technical_groups?.length) {
      tiflux.lists.push({
        title: 'Grupos de atendentes',
        items: profile.technical_groups.map((g) => String(g.name || 'Grupo')),
      })
    }
    tiflux.sections = buildSections(client, TF_SECTIONS, TF_LABELS, TF_HIDDEN, 'tiflux')
    tiflux.entities = entities.map((ent) => ({
      name: String(ent.name || 'Entidade'),
      description: ent.description ? String(ent.description) : undefined,
      fields: ((ent.entity_fields || []) as Array<Record<string, unknown>>)
        .filter((f) => f.value !== null && f.value !== undefined && f.value !== '')
        .map((f) => ({ label: String(f.name || 'Campo'), value: formatDisplayValue('entity', f.value, 'tiflux') })),
    }))
  }

  if (vh.skipped) {
    Object.assign(vhsys, { status: 'skipped' as const, message: 'Não consultado.' })
  } else if (!vh.success) {
    Object.assign(vhsys, { status: 'error' as const, message: vh.error || 'Falha ao carregar' })
  } else {
    const client = (vh.data || {}) as Record<string, unknown>
    const cat = client.categoria || client.nome_categoria
    if (cat) {
      vhsys.category = Array.isArray(cat) ? (cat.length ? cat.join(', ') : '—') : String(cat)
    }
    vhsys.sections = buildSections(client, VH_SECTIONS, VH_LABELS, VH_HIDDEN, 'vhsys')
  }

  return { query: formatQueryDisplay(String(data.query || '')), tiflux, vhsys }
}

export function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function buildReportHtml(parsed: ParsedConsultReport, raw: Record<string, unknown>): string {
  const sectionHtml = (sections: ReportSection[]) =>
    sections.map((s) => `
      <section class="report-section"><h4>${s.title}</h4>
      <dl>${s.rows.map((r) => `<dt>${r.label}</dt><dd>${r.value}</dd>`).join('')}</dl></section>`).join('')

  const listsHtml = (lists: ReportList[]) =>
    lists.map((l) => `<section><h4>${l.title}</h4><ul>${l.items.map((i) => `<li>${i}</li>`).join('')}</ul></section>`).join('')

  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><title>Consulta ${parsed.query}</title>
<style>
body{font-family:Inter,system-ui,sans-serif;color:#0c1e3a;padding:2rem;background:#eef2f7}
h1{font-size:1.5rem;color:#1a4f8c} h3{color:#1a4f8c;margin-top:1.5rem}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
@media(max-width:800px){.grid{grid-template-columns:1fr}}
.col{background:#fff;border:1px solid #d8e0ea;border-radius:12px;padding:1rem}
.report-section{margin-bottom:1rem} h4{color:#2b8fd9;font-size:.9rem;margin-bottom:.5rem}
dl{display:grid;grid-template-columns:minmax(140px,40%) 1fr;gap:.3rem .75rem;font-size:.85rem}
dt{color:#64748b;font-weight:600} dd{margin:0} ul{margin:0;padding-left:1.2rem}
.actions{margin-bottom:1rem} button{padding:.5rem 1rem;margin-right:.5rem}
@media print{.actions{display:none}}
</style></head><body>
<h1>AVS Management — Relatório de consulta</h1>
<p><strong>Consulta:</strong> ${parsed.query}</p>
<div class="actions"><button onclick="window.print()">Imprimir</button></div>
<div class="grid">
<div class="col"><h3>TiFlux</h3>
${parsed.tiflux.status === 'skipped' ? `<p>${parsed.tiflux.message}</p>` : ''}
${parsed.tiflux.status === 'error' ? `<p style="color:#b91c1c">${parsed.tiflux.message}</p>` : ''}
${listsHtml(parsed.tiflux.lists)}${sectionHtml(parsed.tiflux.sections)}
${parsed.tiflux.entities.map((e) => `<section><h4>${e.name}</h4>${e.description ? `<p>${e.description}</p>` : ''}<dl>${e.fields.map((f) => `<dt>${f.label}</dt><dd>${f.value}</dd>`).join('')}</dl></section>`).join('')}
</div>
<div class="col"><h3>VHSYS</h3>
${parsed.vhsys.status === 'skipped' ? `<p>${parsed.vhsys.message}</p>` : ''}
${parsed.vhsys.status === 'error' ? `<p style="color:#b91c1c">${parsed.vhsys.message}</p>` : ''}
${parsed.vhsys.category ? `<p><strong>Categoria:</strong> ${parsed.vhsys.category}</p>` : ''}
${sectionHtml(parsed.vhsys.sections)}
</div></div>
<script>/* backup JSON */ console.log(${JSON.stringify(raw)});</script>
</body></html>`
}
