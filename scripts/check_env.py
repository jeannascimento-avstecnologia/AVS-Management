"""Valida formato do .env e testa APIs (sem imprimir tokens completos)."""
import json
import time
from pathlib import Path

import httpx

from src.config import Settings

LOG = Path(__file__).resolve().parent.parent / "debug-d84fb3.log"


def dbg(hypothesis_id: str, message: str, data: dict) -> None:
    entry = {
        "sessionId": "d84fb3",
        "hypothesisId": hypothesis_id,
        "location": "scripts/check_env.py",
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def audit(name: str, val: str) -> dict:
    v = val or ""
    inner = v[1:-1] if v.startswith("[") and v.endswith("]") else v
    return {
        "name": name,
        "len": len(v),
        "has_brackets": v.startswith("[") and v.endswith("]"),
        "is_placeholder": "SEU_" in v.upper() or v.upper().startswith("[SEU"),
        "jwt_dots_outer": v.count("."),
        "jwt_dots_inner": inner.count("."),
        "looks_like_jwt": inner.count(".") == 2 and len(inner) > 50,
    }


def test_tiflux(token: str, base: str) -> tuple[int, str]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    url = f"{base.rstrip('/')}/clients"
    r = httpx.get(url, headers=headers, params={"page": 1, "per_page": 1}, timeout=30)
    return r.status_code, r.text[:180]


def main() -> None:
    s = Settings()
    audits = [
        audit("TIFLUX_API_TOKEN", s.tiflux_api_token),
        audit("VHSYS_ACCESS_TOKEN", s.vhsys_access_token),
        audit("VHSYS_SECRET_ACCESS_TOKEN", s.vhsys_secret_access_token),
    ]
    for a in audits:
        print(a)
        dbg("H5", "env_audit", a)

    tf = s.tiflux_api_token
    status, snippet = test_tiflux(tf, s.tiflux_base_url)
    print(f"TIFLUX_with_env_value: HTTP {status}")
    dbg("H5", "tiflux_test_raw", {"http": status, "snippet": snippet})

    if tf.startswith("[") and tf.endswith("]"):
        clean = tf[1:-1]
        status2, snippet2 = test_tiflux(clean, s.tiflux_base_url)
        print(f"TIFLUX_without_brackets: HTTP {status2}")
        dbg("H6", "tiflux_test_clean", {"http": status2, "snippet": snippet2})


if __name__ == "__main__":
    main()
