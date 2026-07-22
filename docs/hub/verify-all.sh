#!/usr/bin/env bash
# Roda verificações automatizadas do hub AVS (TiFlux + VHSYS).
# Uso (na pasta NFE):
#   ./verify-all.sh
#
# Pré: .tiflux_token e .vhsys_credentials preenchidos
#      (ou variáveis de ambiente equivalentes)

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "╔══════════════════════════════════════════╗"
echo "║  AVS Hub — verificação de pré-requisitos ║"
echo "╚══════════════════════════════════════════╝"
echo

echo "======= 1/2 TiFlux ======="
if [[ -x ./test-tiflux-capabilities.sh ]]; then
  ./test-tiflux-capabilities.sh || true
else
  echo "ERRO: test-tiflux-capabilities.sh não encontrado"
fi

echo
echo "======= 2/2 VHSYS ======="
if [[ -x ./test-vhsys-capabilities.sh ]]; then
  ./test-vhsys-capabilities.sh || true
else
  echo "ERRO: test-vhsys-capabilities.sh não encontrado"
fi

echo
echo "======= Manual (não automatizável só com API) ======="
cat <<'EOF'
[ ] Mesa TiFlux "Comercial" / "Vendas" existe e IDs anotados
[ ] Campo personalizado financeiro (ticket) — ID da entity
[ ] Campo temperatura de lead — ID
[ ] Solicitante customizado no ticket — comportamento OK na UI
[ ] Kanban: estágio "enviado ao cliente" mapeado
[ ] n8n alcançável pelo Management (URL webhook HTTPS)
[ ] Lista clientes com retenção ISS Campinas
[ ] Templates de orçamento (implantação/mensalidade) definidos com financeiro
[ ] Financeiro aceita fila no Management (não só Excel/TiFlux pendentes)
[ ] Conta de serviço Management + permissões RBAC novas
EOF

echo
echo "Docs: PRE_REQUISITOS.md · CHECKLIST_PRE_AUTOMACAO.md · MODULO_ORCAMENTO_CONTRATO.md"
