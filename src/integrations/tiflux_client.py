import httpx



from src.config import Settings

from src.mapping.canonical import CompanyPayload

from src.mapping.tiflux_mapper import to_tiflux_payload





class TifluxApiError(Exception):

    def __init__(self, message: str, status_code: int | None = None, body: str = ""):

        super().__init__(message)

        self.status_code = status_code

        self.body = body





def is_duplicate_client_error(exc: TifluxApiError) -> bool:

    text = f"{exc} {exc.body}".lower()

    return "already" in text or "document number" in text or "42202" in text





class TifluxClient:

    PAGE_LIMIT = 200



    def __init__(self, settings: Settings):

        self._settings = settings

        self._base = settings.tiflux_base_url.rstrip("/")



    def _auth_headers(self) -> dict[str, str]:

        return {

            "Authorization": f"Bearer {self._settings.tiflux_api_token}",

            "Accept": "application/json",

        }



    def _json_headers(self) -> dict[str, str]:

        return {**self._auth_headers(), "Content-Type": "application/json"}



    async def list_desks(self) -> list[dict]:

        async with httpx.AsyncClient(timeout=30.0) as client:

            response = await client.get(

                f"{self._base}/desks",

                headers=self._auth_headers(),

            )

        self._ensure_ok(response, "listar mesas TiFlux")

        return _normalize_option_list(response.json(), ("name", "display_name", "active"))



    async def list_technical_groups(self) -> list[dict]:

        async with httpx.AsyncClient(timeout=30.0) as client:

            response = await client.get(

                f"{self._base}/technical-groups",

                headers=self._auth_headers(),

            )

        self._ensure_ok(response, "listar grupos TiFlux")

        return _normalize_option_list(response.json(), ("name",))



    async def find_by_cnpj(self, cnpj_digits: str) -> dict | None:

        match = await self._find_by_filter(cnpj_digits)

        if match:

            return match

        return await self._find_by_pagination(cnpj_digits)



    async def get_by_id(self, client_id: int) -> dict | None:

        async with httpx.AsyncClient(timeout=30.0) as client:

            response = await client.get(

                f"{self._base}/clients/{client_id}",

                headers=self._auth_headers(),

            )

        if response.status_code in (403, 404):

            return None

        self._ensure_ok(response, "exibir cliente TiFlux")

        data = response.json()

        return data if isinstance(data, dict) else None



    async def create_client(

        self,

        company: CompanyPayload,

        *,

        desk_ids: list[int],

        technical_group_ids: list[int],

    ) -> dict:

        if not desk_ids:

            raise TifluxApiError(

                "Selecione ao menos uma mesa de serviço no TiFlux.",

                422,

            )

        if not technical_group_ids:

            raise TifluxApiError(

                "Selecione ao menos um grupo de atendentes no TiFlux.",

                422,

            )



        payload = to_tiflux_payload(

            company,

            desk_ids=desk_ids,

            technical_group_ids=technical_group_ids,

        )



        async with httpx.AsyncClient(timeout=30.0) as client:

            response = await client.post(

                f"{self._base}/clients",

                headers=self._json_headers(),

                json=payload,

            )



        if response.status_code >= 400:

            raise TifluxApiError(

                f"Erro ao criar cliente TiFlux: {response.status_code}. {response.text}",

                response.status_code,

                response.text,

            )



        created = response.json()

        client_id = created.get("id")

        verified = await self.find_by_cnpj(company.cnpj_digits)

        if verified:

            return verified



        if client_id:

            detail = await self.get_by_id(int(client_id))

            if detail:

                return detail



        raise TifluxApiError(

            "TiFlux aceitou o cadastro, mas o cliente não ficou visível na API. "

            "Revise mesas e grupos selecionados.",

            502,

            str(created),

        )



    async def _find_by_filter(self, cnpj_digits: str) -> dict | None:

        async with httpx.AsyncClient(timeout=30.0) as client:

            for params in (

                {"social_revenue": cnpj_digits},

                {"social_revenue": cnpj_digits, "offset": 1, "limit": self.PAGE_LIMIT},

                {"social_revenue": cnpj_digits, "status": False},

            ):

                response = await client.get(

                    f"{self._base}/clients",

                    headers=self._auth_headers(),

                    params=params,

                )

                self._ensure_ok(response, "buscar cliente TiFlux")

                match = _first_match(response.json(), cnpj_digits)

                if match:

                    return match

        return None



    async def _find_by_pagination(self, cnpj_digits: str) -> dict | None:

        async with httpx.AsyncClient(timeout=60.0) as client:

            for status_filter in (None, False):

                offset = 1

                while offset <= 100:

                    params: dict = {"offset": offset, "limit": self.PAGE_LIMIT}

                    if status_filter is False:

                        params["status"] = False

                    response = await client.get(

                        f"{self._base}/clients",

                        headers=self._auth_headers(),

                        params=params,

                    )

                    self._ensure_ok(response, "listar clientes TiFlux")

                    items = _extract_client_list(response.json())

                    if not items:

                        break

                    match = _first_match(items, cnpj_digits)

                    if match:

                        return match

                    if len(items) < self.PAGE_LIMIT:

                        break

                    offset += 1

        return None



    def _ensure_ok(self, response: httpx.Response, action: str) -> None:

        if response.status_code == 401:

            raise TifluxApiError("Token TiFlux inválido ou sem permissão.", 401)

        if response.status_code >= 400:

            raise TifluxApiError(

                f"Erro ao {action}: {response.status_code}.",

                response.status_code,

                response.text,

            )





def _normalize_option_list(data: object, extra_fields: tuple[str, ...]) -> list[dict]:

    items = data if isinstance(data, list) else _extract_client_list(data)

    result: list[dict] = []

    for item in items:

        if not isinstance(item, dict) or item.get("id") is None:

            continue

        row: dict = {"id": int(item["id"]), "name": item.get("name") or item.get("display_name") or ""}

        for key in extra_fields:

            if key in item:

                row[key] = item[key]

        result.append(row)

    return result





def _normalize_revenue(value: str | int | None) -> str:

    if value is None:

        return ""

    return "".join(c for c in str(value) if c.isdigit())





def _first_match(data: object, cnpj_digits: str) -> dict | None:

    for item in _extract_client_list(data):

        if _normalize_revenue(item.get("social_revenue")) == cnpj_digits:

            return item

    return None





def _extract_client_list(data: object) -> list[dict]:

    if isinstance(data, list):

        return [x for x in data if isinstance(x, dict)]

    if isinstance(data, dict):

        for key in ("clients", "data", "items", "results"):

            chunk = data.get(key)

            if isinstance(chunk, list):

                return [x for x in chunk if isinstance(x, dict)]

    return []


