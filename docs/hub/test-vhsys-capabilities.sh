#!/usr/bin/env bash
# Testa tokens VHSYS API v2 para o hub AVS (orçamento/OS + faturamento).
# Uso:
#   1. Edite .vhsys_credentials (ACCESS_TOKEN e SECRET_ACCESS_TOKEN)
#   2. ./test-vhsys-capabilities.sh
#   ou: VHSYS_ACCESS_TOKEN=... VHSYS_SECRET_ACCESS_TOKEN=... ./test-vhsys-capabilities.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BASE="${VHSYS_BASE_URL:-https://api.vhsys.com/v2}"
CREDS="${VHSYS_CREDS_FILE:-$ROOT/.vhsys_credentials}"
UA="${VHSYS_USER_AGENT:-AVS-Management-CapabilityCheck/1.0}"

load_creds() {
  if [[ -n "${VHSYS_ACCESS_TOKEN:-}" && -n "${VHSYS_SECRET_ACCESS_TOKEN:-}" ]]; then
    ACCESS="$VHSYS_ACCESS_TOKEN"
    SECRET="$VHSYS_SECRET_ACCESS_TOKEN"
    return
  fi
  if [[ ! -f "$CREDS" ]]; then
    echo "ERRO: crie $CREDS ou exporte VHSYS_ACCESS_TOKEN e VHSYS_SECRET_ACCESS_TOKEN"
    exit 1
  fi
  ACCESS="$(grep -E '^ACCESS_TOKEN=' "$CREDS" | head -1 | cut -d= -f2- | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//;s/^["'\'']//;s/["'\'']$//')"
  SECRET="$(grep -E '^SECRET_ACCESS_TOKEN=' "$CREDS" | head -1 | cut -d= -f2- | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//;s/^["'\'']//;s/["'\'']$//')"
}

load_creds

if [[ -z "${ACCESS:-}" || -z "${SECRET:-}" || "$ACCESS" == "COLE_ACCESS_TOKEN_AQUI" || "$SECRET" == "COLE_SECRET_AQUI" ]]; then
  echo "ERRO: preencha ACCESS_TOKEN e SECRET_ACCESS_TOKEN em $CREDS"
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass=0
fail=0
warn=0

check() {
  local name="$1"
  local path="$2"
  local critical="${3:-1}"
  local body="$TMP/body.json"
  local code

  code="$(
    curl -sS -o "$body" -w "%{http_code}" \
      --connect-timeout 15 --max-time 45 \
      -H "access-token: $ACCESS" \
      -H "secret-access-token: $SECRET" \
      -H "User-Agent: $UA" \
      -H "Accept: application/json" \
      "$BASE$path" || echo "000"
  )"

  local snippet
  snippet="$(python3 - "$body" <<'PY' 2>/dev/null || true
import json,sys
raw=open(sys.argv[1],encoding="utf-8").read()
try:
    d=json.loads(raw)
except Exception:
    print((raw or "")[:100].replace("\n"," ")); raise SystemExit
if isinstance(d, dict):
    code=d.get("code")
    msg=d.get("message") or d.get("data")
    keys=", ".join(list(d.keys())[:10])
    print(f"keys: {keys}")
    if code is not None: print(f"code={code}")
    if msg is not None: print(f"msg={str(msg)[:100]}")
    data=d.get("data")
    if isinstance(data, list):
        print(f"data_array[{len(data)}]")
    elif isinstance(data, dict):
        print("data_object keys:", ", ".join(list(data.keys())[:8]))
elif isinstance(d, list):
    print(f"array[{len(d)}]")
else:
    print(type(d).__name__)
PY
)"

  # VHSYS often returns HTTP 200 with code>=400 in JSON
  local api_code=""
  api_code="$(python3 -c "import json; d=json.load(open('$body')); print(d.get('code','') if isinstance(d,dict) else '')" 2>/dev/null || true)"

  local ok=0
  if [[ "$code" == "200" || "$code" == "201" ]]; then
    if [[ -z "$api_code" || "$api_code" == "200" || "$api_code" == "0" ]]; then
      ok=1
    elif [[ "$api_code" =~ ^[0-9]+$ && "$api_code" -lt 400 ]]; then
      ok=1
    fi
  fi
  # empty list / 403 "nenhum encontrado" still means auth+route ok for list endpoints
  if [[ "$code" == "403" ]] && grep -qi "nenhum\|não encontrado\|nao encontrado" "$body" 2>/dev/null; then
    ok=1
  fi

  local icon
  if [[ "$ok" == "1" ]]; then
    icon="OK"; pass=$((pass+1))
  elif [[ "$critical" == "1" ]]; then
    icon="FAIL"; fail=$((fail+1))
  else
    icon="WARN"; warn=$((warn+1))
  fi

  printf '%-5s HTTP %-3s  %-42s  %s\n' "$icon" "$code" "$name" "$path"
  [[ -n "$snippet" ]] && echo "$snippet" | sed 's/^/      → /' | head -n 4
  echo
}

echo "VHSYS API capability check"
echo "Base: $BASE"
echo "Access: ${ACCESS:0:4}…${ACCESS: -4} (${#ACCESS} chars)"
echo "Secret: ${SECRET:0:4}…${SECRET: -4} (${#SECRET} chars)"
echo

echo "── Obrigatórios (cadastro / hub) ──"
check "Listar clientes"              "/clientes?limit=3&lixeira=Nao"           1

echo "── Orçamento / OS ──"
check "Listar ordens de serviço"     "/ordens-servico?limit=3"                1
# Catálogo de serviços da OS — path varia; probe não-crítico
check "Listar serviços (probe)"      "/servicos?limit=3"                      0

echo "── Faturamento ──"
check "Listar notas de serviço"      "/notas-servico?limit=3"                 1
# Doc oficial: GET /contas-receber (não /receitas)
check "Listar contas a receber"      "/contas-receber?limit=3"                1
check "Listar pedidos"               "/pedidos?limit=3"                       0

echo "── Outros úteis ──"
check "Listar produtos"              "/produtos?limit=3"                      0
check "Listar usuários"              "/usuarios?limit=3"                      0

echo "════════════════════════════════════════"
echo "Resumo: OK=$pass  FAIL=$fail  WARN=$warn"
echo

if [[ "$fail" -eq 0 ]]; then
  echo "VHSYS: GO técnico (clientes / OS / notas-servico / contas-receber)."
else
  echo "VHSYS: NO-GO — falha em rota crítica (auth ou path)."
  echo "Doc: https://developers.vhsys.com.br/api"
fi
echo
echo "WARN = path opcional inexistente; não bloqueia o hub."
echo "Dica: apague .vhsys_credentials depois do teste."
