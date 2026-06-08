import { UserPlus, UserX, Search, Clock } from 'lucide-react'
import { ActionCard } from '../components/ui/ActionCard'

const cards = [
  {
    to: '/cadastrar',
    title: 'Cadastrar cliente',
    desc: 'CNPJ, revisão e integração TiFlux + VHSYS',
    icon: UserPlus,
    color: 'from-sky-500 to-cyan-500',
    glow: 'rgba(14, 165, 233, 0.55)',
  },
  {
    to: '/inativar',
    title: 'Inativar cliente',
    desc: 'Inativação no TiFlux por CNPJ ou nome',
    icon: UserX,
    color: 'from-amber-500 to-orange-500',
    glow: 'rgba(245, 158, 11, 0.55)',
  },
  {
    to: '/consultar',
    title: 'Consultar status',
    desc: 'Relatório completo do cadastro nos sistemas',
    icon: Search,
    color: 'from-violet-500 to-purple-600',
    glow: 'rgba(139, 92, 246, 0.55)',
  },
  {
    to: '/empresas-inativas',
    title: 'Empresas sem atividade',
    desc: 'Sem ticket ou cobrança nos últimos 24 meses',
    icon: Clock,
    color: 'from-rose-500 to-pink-600',
    glow: 'rgba(244, 63, 94, 0.55)',
  },
]

export function Dashboard() {
  return (
    <div>
      <h1 className="font-display mb-2 text-2xl font-bold text-avs-navy">Central AVS Management</h1>
      <p className="mb-8 text-slate-600">Escolha uma operação para começar.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {cards.map((c, i) => (
          <ActionCard key={c.to} {...c} delay={i * 0.05} />
        ))}
      </div>
    </div>
  )
}
