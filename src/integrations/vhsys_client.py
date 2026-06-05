import httpx

from src.config import Settings
from src.mapping.canonical import CompanyPayload
from src.mapping.vhsys_mapper import to_vhsys_payload


class VhsysApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _is_not_found_response(response: httpx.Response) -> bool:
    if response.status_code == 404:
        return True
    if response.status_code != 403:
        return False
    text = response.text.lower()
    return "nenhum cliente encontrado" in text


class VhsysClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._base = settings.vhsys_base_url.rstrip("/")

    def _auth_headers(self) -> dict[str, str]:
        return {
            "access-token": self._settings.vhsys_access_token,
            "secret-access-token": self._settings.vhsys_secret_access_token,
            "User-Agent": self._settings.user_agent,
            "Accept": "application/json",
        }

    def _json_headers(self) -> dict[str, str]:
        return {**self._auth_headers(), "Content-Type": "application/json"}

    def _parse_response(self, response: httpx.Response) -> dict:
        if response.status_code == 401:
            raise VhsysApiError("Tokens VHSYS inválidos.", 401, response.text)
        if response.status_code >= 400:
            raise VhsysApiError(
                f"Erro HTTP VHSYS: {response.status_code}.",
                response.status_code,
                response.text,
            )

        data = response.json()
        if not isinstance(data, dict):
            return {"data": data}

        code = data.get("code")
        if code is not None and int(code) >= 400:
            message = data.get("message") or data.get("data") or "Erro VHSYS."
            raise VhsysApiError(str(message), int(code), response.text)

        return data

    async def find_by_cnpj(self, cnpj_formatted: str) -> dict | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/clientes",
                headers=self._auth_headers(),
                params={"cnpj_cliente": cnpj_formatted, "lixeira": "Nao", "limit": 5},
            )

        if response.status_code == 401:
            raise VhsysApiError("Tokens VHSYS inválidos.", 401)
        if _is_not_found_response(response):
            return None
        if response.status_code >= 400:
            raise VhsysApiError(
                f"Erro ao listar clientes VHSYS: {response.status_code}.",
                response.status_code,
                response.text,
            )

        data = response.json()
        if isinstance(data, dict) and int(data.get("code", 200)) == 403:
            return None

        if isinstance(data, dict):
            code = data.get("code")
            if code is not None and int(code) >= 400:
                message = data.get("message") or data.get("data") or "Erro VHSYS."
                raise VhsysApiError(str(message), int(code), response.text)

        clients = _extract_vhsys_clients(data)
        return clients[0] if clients else None

    async def create_client(self, company: CompanyPayload) -> dict:
        payload = to_vhsys_payload(company)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base}/clientes",
                headers=self._json_headers(),
                json=payload,
            )

        return self._parse_response(response)


def _extract_vhsys_clients(data: object) -> list[dict]:
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
        if isinstance(inner, dict):
            return [inner]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []

