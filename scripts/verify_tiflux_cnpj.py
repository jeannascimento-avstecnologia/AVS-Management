"""Verifica se um CNPJ existe no TiFlux via API (filtro + paginação)."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import Settings, clear_settings_cache
from src.integrations.tiflux_client import TifluxClient

CNPJ = sys.argv[1] if len(sys.argv) > 1 else "71752794000198"


async def main() -> None:
    clear_settings_cache()
    settings = Settings()
    client = TifluxClient(settings)

    found = await client.find_by_cnpj(CNPJ)
    print(f"CNPJ: {CNPJ}")
    if found:
        print("RESULTADO: ENCONTRADO")
        print(json.dumps(found, ensure_ascii=False, indent=2))
    else:
        print("RESULTADO: NAO ENCONTRADO na API (varredura completa)")
        print("Se POST retorna 422 duplicata, trata-se de registro orfao no TiFlux.")


if __name__ == "__main__":
    asyncio.run(main())

