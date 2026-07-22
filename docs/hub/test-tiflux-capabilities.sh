#!/usr/bin/env bash
# Testa se a chave TiFlux API v2 tem as capacidades necessárias para a Fase 1.
# Uso:
#   1. Edite .tiflux_token e cole o token (só a chave)
#   2. ./test-tiflux-capabilities.sh
#      ou: TIFLUX_TOKEN='xxx' ./test-tiflux-capabilities.sh
#
# Arquivo temporário — pode apagar depois do teste.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BASE="${TIFLUX_BASE_URL:-https://api.tiflux.com/api/v2}"
TOKEN_FILE="${TIFLUX_TOKEN_FILE:-$ROOT/.tiflux_token}"

# --- carregar token ---
if [[ -n "${TIFLUX_TOKEN:-}" ]]; then
  TOKEN="$TIFLUX_TOKEN"
elif [[ -f "$TOKEN_FILE" ]]; then
  TOKEN="$(
    grep -v '^[[:space:]]*#' "$TOKEN_FILE" \
      | grep -v '^[[:space:]]*$' \
      | head -n 1 \
      | tr -d '\r' \
      | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' \
      | sed 's/^Bearer[[:space:]]*//I'
  )"
else
  echo "ERRO: defina TIFLUX_TOKEN ou crie $TOKEN_FILE"
  exit 1
fi

if [[ -z "$TOKEN" || "$TOKEN" == "COLE_SEU_TOKEN_AQUI" ]]; then
  echo "ERRO: cole o token real em $TOKEN_FILE (substitua COLE_SEU_TOKEN_AQUI)"
  exit 1
fi

# Remove aspas acidentais
TOKEN="${TOKEN%\"}"
TOKEN="${TOKEN#\"}"
TOKEN="${TOKEN%\'}"
TOKEN="${TOKEN#\'}"

AUTH_MODE="${TIFLUX_AUTH_MODE:-auto}" # auto | bearer | raw | x-api-key

auth_headers() {
  case "$AUTH_MODE" in
    bearer)   echo -H "Authorization: Bearer $TOKEN" ;;
    raw)      echo -H "Authorization: $TOKEN" ;;
    x-api-key) echo -H "x-tiflux-api-key: $TOKEN" ;;
    auto)     echo -H "Authorization: Bearer $TOKEN" ;;
    *)
      echo "ERRO: TIFLUX_AUTH_MODE inválido: $AUTH_MODE" >&2
      exit 1
      ;;
  esac
}

# --- helpers ---
TMPDIR_RUN="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_RUN"' EXIT

pass=0
fail=0
warn=0
results=()

diagnose_auth() {
  echo "── Diagnóstico de autenticação ──"
  echo "Token length: ${#TOKEN}"
  if [[ ${#TOKEN} -lt 20 ]]; then
    echo "AVISO: token muito curto (<20). Provavelmente incompleto."
  fi
  echo "Auth mode: $AUTH_MODE"
  echo

  local modes=(bearer raw x-api-key)
  local mode code body
  for mode in "${modes[@]}"; do
    body="$TMPDIR_RUN/auth_$mode.json"
    case "$mode" in
      bearer)
        code="$(curl -sS -o "$body" -w "%{http_code}" --connect-timeout 15 --max-time 30 \
          -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" \
          "$BASE/clients?limit=1" || echo "000")"
        ;;
      raw)
        code="$(curl -sS -o "$body" -w "%{http_code}" --connect-timeout 15 --max-time 30 \
          -H "Authorization: $TOKEN" -H "Accept: application/json" \
          "$BASE/clients?limit=1" || echo "000")"
        ;;
      x-api-key)
        code="$(curl -sS -o "$body" -w "%{http_code}" --connect-timeout 15 --max-time 30 \
          -H "x-tiflux-api-key: $TOKEN" -H "Accept: application/json" \
          "$BASE/clients?limit=1" || echo "000")"
        ;;
    esac
    local msg
    msg="$(python3 -c "import json; d=json.load(open('$body')); print(d.get('message') or d.get('detail') or d.get('error_code') or '')" 2>/dev/null || true)"
    printf '  %-10s HTTP %-3s  %s\n' "$mode" "$code" "$msg"
    if [[ "$code" == "200" && "$AUTH_MODE" == "auto" ]]; then
      AUTH_MODE="$mode"
      echo
      echo "→ Modo que funcionou: $AUTH_MODE (usado nos próximos testes)"
      echo
      return 0
    fi
  done
  echo
  if [[ "$AUTH_MODE" == "auto" ]]; then
    AUTH_MODE="bearer"
  fi
  echo "Nenhum modo de auth retornou 200."
  echo "Gere um novo token em: TiFlux → foto do perfil → Minha conta → Sessões → Sessões API → Gerar sessão"
  echo "Confirme que o usuário tem licença de API ativa."
  echo "Cole SÓ o token (sem Bearer, sem aspas) em .tiflux_token"
  echo
}

check() {
  local name="$1"
  local path="$2"
  local critical="${3:-1}" # 1=obrigatório Fase1 leitura, 0=opcional/informativo
  local url="$BASE$path"
  local body="$TMPDIR_RUN/body.json"
  local code
  local -a hdrs=()

  case "$AUTH_MODE" in
    bearer)    hdrs=(-H "Authorization: Bearer $TOKEN") ;;
    raw)       hdrs=(-H "Authorization: $TOKEN") ;;
    x-api-key) hdrs=(-H "x-tiflux-api-key: $TOKEN") ;;
  esac

  code="$(
    curl -sS -o "$body" -w "%{http_code}" \
      --connect-timeout 15 --max-time 45 \
      "${hdrs[@]}" \
      -H "Accept: application/json" \
      "$url" || echo "000"
  )"

  local size
  size="$(wc -c <"$body" | tr -d ' ')"
  local snippet
  snippet="$(python3 - "$body" <<'PY' 2>/dev/null || true
import json,sys
p=sys.argv[1]
try:
    with open(p,"r",encoding="utf-8") as f:
        raw=f.read()
    if not raw.strip():
        print("(vazio)")
        raise SystemExit
    data=json.loads(raw)
    if isinstance(data,list):
        print(f"array[{len(data)}]")
        if data and isinstance(data[0],dict):
            keys=", ".join(list(data[0].keys())[:8])
            print(f"keys0: {keys}")
            # hint valores
            for k in ("total_value","value","monthly_value","name","status","id"):
                if k in data[0]:
                    print(f"{k}={data[0].get(k)!r}")
    elif isinstance(data,dict):
        keys=", ".join(list(data.keys())[:12])
        print(f"object keys: {keys}")
        if "error" in data or "message" in data:
            print(str(data.get("error") or data.get("message"))[:120])
    else:
        print(type(data).__name__)
except Exception as e:
    print(raw[:100].replace("\n"," ") if "raw" in dir() else str(e)[:80])
PY
)"

  local status_icon
  if [[ "$code" == "200" ]]; then
    status_icon="OK"
    pass=$((pass + 1))
  elif [[ "$critical" == "1" ]]; then
    status_icon="FAIL"
    fail=$((fail + 1))
  else
    status_icon="WARN"
    warn=$((warn + 1))
  fi

  printf '%-5s HTTP %-3s  %-40s  %s\n' "$status_icon" "$code" "$name" "$path"
  if [[ -n "$snippet" ]]; then
    echo "      → $snippet" | head -n 4
  fi
  echo "      bytes=$size"
  results+=("$status_icon|$code|$name|$path")
  echo
}

probe_pending() {
  # Rotas candidatas a faturamentos pendentes (podem não existir na v2 pública)
  local candidates=(
    "/reports/billings/pending"
    "/reports/billings/pending/list"
    "/billings/pending"
  )
  echo "── Probing rotas de faturamentos pendentes (não documentadas) ──"
  for path in "${candidates[@]}"; do
    local code
    code="$(
      curl -sS -o "$TMPDIR_RUN/probe.json" -w "%{http_code}" \
        --connect-timeout 10 --max-time 20 \
        -H "Authorization: Bearer $TOKEN" \
        -H "Accept: application/json" \
        "$BASE$path" || echo "000"
    )"
    printf '      HTTP %-3s  %s\n' "$code" "$path"
  done
  echo
}

echo "TiFlux API capability check"
echo "Base: $BASE"
echo "Token: ${TOKEN:0:6}…${TOKEN: -4} (${#TOKEN} chars)"
echo

diagnose_auth

echo "── Obrigatórios (leitura Fase 1) ──"
check "Clientes (lista)"           "/clients?limit=3"                          1
check "Contratos (lista)"          "/contracts?limit=5"                        1
# OpenAPI: enum = actives | readjust | expired (não "active")
check "Contratos ativos"           "/contracts?limit=5&status=actives"         1
check "Tickets (lista)"            "/tickets?limit=3"                          1
check "Histórico faturamentos"     "/reports/billings/history?limit=3"         1

echo "── Mesas de serviço ──"
check "Mesas ativas"               "/desks?limit=10&active=true"               0

# Se listou desks, pega o primeiro id e testa catálogo
DESK_ID="$(
  python3 - <<'PY' 2>/dev/null || true
import json,os,urllib.request
# read from last desks body if present - skip, fetch again via env
print("")
PY
)"

# fetch first desk id with a dedicated call
DESK_ID="$(
  curl -sS -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" \
    "$BASE/desks?limit=1&active=true" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d,list) and d else '')" 2>/dev/null || true
)"

if [[ -n "${DESK_ID:-}" ]]; then
  check "Mesa detalhe #$DESK_ID"           "/desks/$DESK_ID"                              0
  check "Catálogos da mesa #$DESK_ID"      "/desks/$DESK_ID/services-catalogs?limit=5"    0
  check "Itens catálogo mesa #$DESK_ID"    "/desks/$DESK_ID/services-catalogs-items?limit=5" 0
else
  echo "WARN  (sem desk_id) — pulando detalhe/catálogo de mesa"
  warn=$((warn + 1))
  echo
fi

# cliente + contratos filtrados
CLIENT_ID="$(
  curl -sS -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" \
    "$BASE/clients?limit=1" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d,list) and d else '')" 2>/dev/null || true
)"

if [[ -n "${CLIENT_ID:-}" ]]; then
  echo "── Recorte por cliente #$CLIENT_ID ──"
  check "Cliente detalhe"          "/clients/$CLIENT_ID"                       1
  check "Contratos do cliente"     "/contracts?limit=20&client_ids=$CLIENT_ID" 1
  check "Tickets do cliente"       "/tickets?limit=5&client_ids=$CLIENT_ID"    0
  check "Mesas do cliente"         "/clients/$CLIENT_ID/desks"                 0
fi

probe_pending

echo "════════════════════════════════════════"
echo "Resumo: OK=$pass  FAIL=$fail  WARN=$warn"
echo

if [[ "$fail" -eq 0 ]]; then
  echo "Leitura básica: GO técnico (clients / contracts / tickets / billing history / desks)."
else
  echo "Leitura básica: NO-GO — há falhas críticas (HTTP != 200 nos obrigatórios)."
fi

echo
echo "Pendentes/faturar: 404 nas rotas probe = API v2 pública NÃO expõe"
echo "'faturamentos pendentes' / faturar. Para a Fase 1 completa, confirme com"
echo "o suporte TiFlux se existe endpoint privado OU planeje workaround (UI/RPA)."
echo
echo "Dica: apague .tiflux_token depois do teste (arquivo temporário)."
echo "Relatório só no terminal — a chave fica apenas em .tiflux_token (gitignored)."
