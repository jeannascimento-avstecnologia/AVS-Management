import httpx

from src.config import Settings


class BrasilApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


async def fetch_cnpj(cnpj_digits: str, settings: Settings) -> dict:
    url = f"{settings.brasilapi_base_url.rstrip('/')}/{cnpj_digits}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)

    if response.status_code == 404:
        raise BrasilApiError("CNPJ não encontrado na BrasilAPI.", 404)
    if response.status_code >= 400:
        raise BrasilApiError(
            f"BrasilAPI retornou erro {response.status_code}.",
            response.status_code,
        )

    return response.json()
