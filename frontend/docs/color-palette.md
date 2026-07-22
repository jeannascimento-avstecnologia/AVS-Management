# Aurora color palette — AVS Flow

Tokens definidos em [`src/index.css`](../src/index.css). Usar sempre classes `aurora-*` ou variáveis CSS `--aurora-*`; evitar hex hardcoded.

## Semantic tokens

| Token | Light | Dark | Uso |
|-------|-------|------|-----|
| `aurora-bg` | `#F4F6FB` | `#0B1020` | Fundo da app |
| `aurora-surface` | `#FFFFFF` | `#121A2E` | Cards, modais, inputs |
| `aurora-surface-2` | `#EEF2F9` | `#1A2438` | Hover / elevação |
| `aurora-fg` | `#1E293B` | `#E8EDF7` | Texto principal |
| `aurora-muted` | `#64748B` | `#94A3B8` | Texto secundário |
| `aurora-border` | `#E2E8F0` | `#2A3548` | Bordas |
| `aurora-accent` | `#1D4ED8` | `#3B82F6` | Primário (azul) |
| `aurora-accent-muted` | `#DBEAFE` | `#1E3A5F` | Focus / hover suave |
| `aurora-success` | `#10B981` | `#34D399` | Sucesso |
| `aurora-warning` | `#F59E0B` | `#FBBF24` | Alerta |
| `aurora-yellow` | `#FACC15` | `#EAB308` | Acento lead morno / glow |
| `aurora-yellow-deep` | `#A16207` | `#CA8A04` | Fill lead morno (texto branco) |
| `aurora-danger` | `#EF4444` | `#F87171` | Erro / destrutivo |
| `aurora-info` | `#0EA5E9` | `#38BDF8` | Info |
| `aurora-sidebar-bg` | `#0A1145` | `#060A2E` | Sidebar + auth |
| `aurora-sidebar-fg` | `#F8FAFC` | `#E8EDF7` | Texto sidebar |
| `aurora-sidebar-muted` | `#94A3B8` | `#7C8BA8` | Nav inativo |
| `aurora-sidebar-accent` | `#3B82F6` | `#60A5FA` | Nav ativo |
| `aurora-sidebar-border` | `rgba(255,255,255,0.08)` | `rgba(255,255,255,0.06)` | Borda sidebar |
| `aurora-brand-red` | `#DC2626` | `#DC2626` | CTA primário / logout |
| `aurora-purple` | `#7C3AED` | `#8B5CF6` | Usuários / admin |
| `aurora-purple-muted` | `#EDE9FE` | `#2E1065` | Badge / hover purple |
| `aurora-green` | `#059669` | `#34D399` | Orçamentos (hub) |
| `aurora-green-muted` | `#D1FAE5` | `#064E3B` | Badge / hover green |
| `aurora-teal` | `#0D9488` | `#2DD4BF` | Faturamento (hub, green variant) |
| `aurora-teal-muted` | `#CCFBF1` | `#134E4A` | Badge / hover teal |
| `aurora-amber` | `#D97706` | `#FBBF24` | Documentos (hub) |
| `aurora-amber-muted` | `#FEF3C7` | `#78350F` | Badge / hover amber |
| `aurora-orange` | `#EA580C` | `#FB923C` | Lead quente (pipeline) |
| `aurora-orange-muted` | `#FFEDD5` | `#7C2D12` | Hover / muted orange |
| `aurora-orange-deep` | `#C2410C` | `#EA580C` | Gradiente lead quente |
| `aurora-topbar-bg` | `#B91C1C` | `#991B1B` | Topbar vermelha |
| `aurora-overlay` | `rgba(6,10,46,0.55)` | `rgba(0,0,0,0.6)` | Backdrop mobile |

## Layout

- **Radius:** `--radius-aurora` = `0.75rem` (12px)
- **PWA theme-color:** `#0A1145`
- **Sidebar pattern:** classe `.aurora-sidebar-pattern`
- **Logo on light:** classe `.logo-box-navy`

## Priority badges

| Priority | Style |
|----------|-------|
| low | `bg-aurora-muted/15 text-aurora-muted` |
| medium | `bg-aurora-info/15 text-aurora-info` |
| high | `bg-aurora-warning/20 text-aurora-warning` |
| urgent | `bg-aurora-danger text-white` |

## Entity color presets

`#6366F1`, `#8B5CF6`, `#EC4899`, `#EF4444`, `#F59E0B`, `#10B981`, `#14B8A6`, `#0EA5E9`, `#3B82F6`, `#64748B`, `#F97316`, `#84CC16`
