import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx

from src.cnpj.validator import format_cnpj
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


_TIFLUX_PUT_FIELDS = frozenset(
    {
        "name",
        "desk_ids",
        "technical_group_ids",
        "social",
        "social_revenue",
        "status",
        "max_agents",
        "email_financial",
        "sms_financial",
        "municipal_registration",
        "estadual_registration",
        "anotations",
        "visible_to_clients",
        "work_folder",
        "quarterly_billing",
        "quarterly_bill_client_id",
        "billing_report_type",
        "authorization_flow",
    }
)


def _build_inactivate_payload(detail: dict) -> dict:
    body = {key: detail[key] for key in _TIFLUX_PUT_FIELDS if key in detail}
    body["status"] = False
    return body


def _is_tiflux_50004(body_text: str) -> bool:
    return "50004" in (body_text or "") or "auth_flow" in (body_text or "")


def _inactivate_error_message(status_code: int, body_text: str) -> str:
    try:
        data = json.loads(body_text) if body_text else {}
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    code = data.get("error_code")
    detail = data.get("detail")
    if status_code == 500 and (code == 50004 or _is_tiflux_50004(body_text)):
        return (
            "TiFlux não aceitou inativar com mesas vinculadas. "
            "O sistema tenta desvincular automaticamente; atualize o deploy e tente de novo."
        )
    if status_code == 422 and isinstance(detail, dict):
        parts: list[str] = []
        for key, messages in detail.items():
            if isinstance(messages, list):
                parts.extend(str(m) for m in messages)
            elif messages:
                parts.append(str(messages))
        if parts:
            return "Não foi possível inativar no TiFlux: " + " ".join(parts)
    message = data.get("message")
    if message:
        return f"Não foi possível inativar no TiFlux: {message}"
    return f"Erro ao inativar cliente TiFlux: {status_code}."


class TifluxClient:

    PAGE_LIMIT = 200



    def __init__(self, settings: Settings):

        self._settings = settings

        self._base = settings.tiflux_base_url.rstrip("/")

        self._request_lock = asyncio.Lock()

        self._last_request_at = 0.0



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



    async def find_matches_by_cnpj(self, cnpj_digits: str, limit: int = 10) -> list[dict]:

        match = await self.find_by_cnpj(cnpj_digits)

        return [match] if match else []



    async def find_by_name(self, name: str, limit: int = 10) -> list[dict]:
        term = (name or "").strip()
        if not term:
            return []

        seen: dict[int, dict] = {}
        async with httpx.AsyncClient(timeout=30.0) as client:
            for active in (None, False):
                params: dict = {
                    "name": term,
                    "offset": 1,
                    "limit": min(limit, self.PAGE_LIMIT),
                }
                if active is not None:
                    params["active"] = active
                response = await client.get(
                    f"{self._base}/clients",
                    headers=self._auth_headers(),
                    params=params,
                )
                self._ensure_ok(response, "buscar cliente TiFlux por nome")
                for item in _extract_client_list(response.json()):
                    cid = item.get("id")
                    if cid is None:
                        continue
                    key = int(cid)
                    if key not in seen:
                        seen[key] = item
                    if len(seen) >= limit:
                        break
                if len(seen) >= limit:
                    break
        return list(seen.values())[:limit]



    async def _put_client(self, client_id: int, body: dict) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.put(
                f"{self._base}/clients/{client_id}",
                headers=self._json_headers(),
                json=body,
            )

    def _raise_inactivate_error(self, response: httpx.Response) -> None:
        if response.status_code == 404:
            raise TifluxApiError("Cliente não encontrado no TiFlux.", 404, response.text)
        if response.status_code in (422, 500):
            raise TifluxApiError(
                _inactivate_error_message(response.status_code, response.text),
                response.status_code,
                response.text,
            )
        self._ensure_ok(response, "inativar cliente TiFlux")

    def _minimal_prep_payload(self, detail: dict) -> dict:
        return {
            "name": detail.get("name") or detail.get("social") or "",
            "social": detail.get("social") or "",
            "social_revenue": detail.get("social_revenue") or "",
            "desk_ids": [],
            "technical_group_ids": [],
            "status": True,
            "authorization_flow": False,
        }

    async def _prepare_client_for_inactivate(self, client_id: int, detail: dict) -> None:
        """Desvincula mesas/grupos antes de status=false (evita bug 50004 do TiFlux)."""
        prep = _build_inactivate_payload(detail)
        prep["desk_ids"] = []
        prep["technical_group_ids"] = []
        prep["status"] = True
        prep["authorization_flow"] = False
        response = await self._put_client(client_id, prep)
        if response.status_code in (200, 204):
            return
        response = await self._put_client(client_id, self._minimal_prep_payload(detail))
        if response.status_code not in (200, 204):
            self._raise_inactivate_error(response)

    async def _put_inactivate(self, client_id: int, detail: dict) -> httpx.Response:
        body = _build_inactivate_payload(detail)
        body["desk_ids"] = []
        body["technical_group_ids"] = []
        return await self._put_client(client_id, body)

    async def delete_client(self, client_id: int) -> None:
        """Inativa o cliente. A API v2 não expõe DELETE em /clients/{id} (só GET/PUT)."""
        detail = await self.get_by_id(client_id)
        if not detail:
            raise TifluxApiError("Cliente não encontrado no TiFlux.", 404, "")

        if detail.get("status") is False:
            return

        prepared = False
        try:
            await self._prepare_client_for_inactivate(client_id, detail)
            prepared = True
            detail = await self.get_by_id(client_id) or detail
        except TifluxApiError:
            pass

        response = await self._put_inactivate(client_id, detail)

        if response.status_code in (200, 204):
            verified = await self.get_by_id(client_id)
            if verified and verified.get("status") is False:
                return
            return

        if response.status_code >= 500 or _is_tiflux_50004(response.text):
            if not prepared:
                await self._prepare_client_for_inactivate(client_id, detail)
                prepared = True
            detail = await self.get_by_id(client_id) or detail
            response = await self._put_inactivate(client_id, detail)
            if response.status_code in (200, 204):
                verified = await self.get_by_id(client_id)
                if verified and verified.get("status") is False:
                    return

        self._raise_inactivate_error(response)

    async def resolve_client_id(
        self,
        client_id: int,
        *,
        cnpj_digits: str | None = None,
    ) -> int:
        """Confirma o ID via GET; se falhar, tenta reencontrar pelo CNPJ."""
        if await self.get_by_id(client_id):
            return client_id
        if cnpj_digits:
            refound = await self.find_by_cnpj(cnpj_digits)
            if refound and refound.get("id") is not None:
                client_id = int(refound["id"])
                return client_id
        raise TifluxApiError("Cliente não encontrado no TiFlux.", 404, "")



    async def get_by_id(self, client_id: int, *, show_entities: bool = False) -> dict | None:
        params = {"show_entities": "true"} if show_entities else None
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/clients/{client_id}",
                headers=self._auth_headers(),
                params=params,
            )

        if response.status_code in (403, 404):
            return None

        self._ensure_ok(response, "exibir cliente TiFlux")
        data = response.json()
        return data if isinstance(data, dict) else None

    async def get_client_desks(self, client_id: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/clients/{client_id}/desks",
                headers=self._auth_headers(),
            )
        self._ensure_ok(response, "listar mesas do cliente TiFlux")
        return _extract_client_list(response.json())

    async def get_client_technical_groups(self, client_id: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/clients/{client_id}/technical-groups",
                headers=self._auth_headers(),
            )
        self._ensure_ok(response, "listar grupos do cliente TiFlux")
        return _extract_client_list(response.json())

    async def get_client_profile(self, client_id: int) -> dict:
        async def _entities() -> list:
            raw = await self.get_by_id(client_id, show_entities=True)
            if isinstance(raw, dict):
                return raw.get("entities") or []
            return []

        client, entities, desks, groups = await asyncio.gather(
            self.get_by_id(client_id, show_entities=False),
            _entities(),
            self.get_client_desks(client_id),
            self.get_client_technical_groups(client_id),
        )
        if not client:
            raise TifluxApiError("Cliente não encontrado no TiFlux.", 404, "")
        return {
            "client": client,
            "entities": entities,
            "desks": desks,
            "technical_groups": groups,
        }

    async def update_client_bindings(
        self,
        client_id: int,
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

        detail = await self.get_by_id(client_id)
        if not detail:
            raise TifluxApiError("Cliente não encontrado no TiFlux.", 404, "")

        body = {key: detail[key] for key in _TIFLUX_PUT_FIELDS if key in detail}
        body["desk_ids"] = desk_ids
        body["technical_group_ids"] = technical_group_ids
        if detail.get("status") is not False:
            body["status"] = detail.get("status", True)
        body["authorization_flow"] = False

        response = await self._put_client(client_id, body)
        self._ensure_ok(response, "atualizar mesas do cliente TiFlux")
        return await self.get_client_profile(client_id)

    async def iter_active_clients(
        self,
        *,
        max_clients: int = 1500,
        http: httpx.AsyncClient | None = None,
    ) -> AsyncIterator[dict]:
        count = 0
        offset = 1

        async def _iterate(client: httpx.AsyncClient) -> AsyncIterator[dict]:
            nonlocal count, offset
            unlimited = max_clients <= 0
            while unlimited or count < max_clients:
                response = await self._get_with_retry(
                    client,
                    f"{self._base}/clients",
                    headers=self._auth_headers(),
                    params={"offset": offset, "limit": self.PAGE_LIMIT, "active": True},
                    action="listar clientes TiFlux",
                )
                items = _extract_client_list(response.json())
                if not items:
                    break
                for item in items:
                    yield item
                    count += 1
                    if not unlimited and count >= max_clients:
                        return
                if len(items) < self.PAGE_LIMIT:
                    break
                offset += 1

        if http is not None:
            async for item in _iterate(http):
                yield item
            return

        async with httpx.AsyncClient(timeout=60.0) as client:
            async for item in _iterate(client):
                yield item

    async def get_last_ticket_datetime(
        self,
        client_id: int,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> datetime | None:
        async def _fetch(client: httpx.AsyncClient) -> datetime | None:
            response = await self._get_with_retry(
                client,
                f"{self._base}/tickets",
                headers=self._auth_headers(),
                params={"client_id": client_id, "offset": 1, "limit": 100},
                action="listar tickets TiFlux",
                allow_statuses=frozenset({404, 405}),
            )
            if response.status_code in (404, 405):
                return None
            return _latest_datetime_from_items(
                _extract_client_list(response.json()),
                ("updated_at", "created_at", "opened_at", "last_update", "date"),
            )

        if http is not None:
            return await _fetch(http)

        async with httpx.AsyncClient(timeout=30.0) as client:
            return await _fetch(client)

    async def get_last_billing_datetime(
        self,
        client_id: int,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> datetime | None:
        """Última cobrança via histórico de faturamentos (GET /reports/billings/history)."""

        async def _fetch(client: httpx.AsyncClient) -> datetime | None:
            response = await self._get_with_retry(
                client,
                f"{self._base}/reports/billings/history",
                headers=self._auth_headers(),
                params={"client_id": client_id, "offset": 1, "limit": 100},
                action="listar histórico de faturamentos TiFlux",
                allow_statuses=frozenset({404, 405}),
            )
            if response.status_code in (404, 405):
                return None
            items = _extract_client_list(response.json())
            if not items:
                return None
            return _latest_datetime_from_items(items, ("billing_date",))

        if http is not None:
            return await _fetch(http)

        async with httpx.AsyncClient(timeout=30.0) as client:
            return await _fetch(client)

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
        formatted = format_cnpj(cnpj_digits)
        revenues = [cnpj_digits]
        if formatted != cnpj_digits:
            revenues.append(formatted)

        async with httpx.AsyncClient(timeout=30.0) as client:
            for revenue in revenues:
                for active in (None, True, False):
                    params: dict = {
                        "social_revenue": revenue,
                        "offset": 1,
                        "limit": self.PAGE_LIMIT,
                    }
                    if active is not None:
                        params["active"] = active
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
            for active_filter in (None, True, False):
                offset = 1
                while offset <= 100:
                    params: dict = {"offset": offset, "limit": self.PAGE_LIMIT}
                    if active_filter is not None:
                        params["active"] = active_filter
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

    async def _throttle_before_request(self) -> None:
        interval = max(0, self._settings.tiflux_min_request_interval_ms) / 1000.0
        if interval <= 0:
            return
        async with self._request_lock:
            now = time.monotonic()
            wait = interval - (now - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            return max(0.0, float(raw.strip()))
        except ValueError:
            return None

    async def _get_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, object] | None,
        action: str,
        max_retries: int = 8,
        allow_statuses: frozenset[int] = frozenset(),
    ) -> httpx.Response:
        delay = 1.0
        response: httpx.Response | None = None
        for attempt in range(max_retries):
            await self._throttle_before_request()
            response = await client.get(url, headers=headers, params=params)
            if response.status_code in allow_statuses:
                return response
            if response.status_code != 429:
                self._ensure_ok(response, action)
                return response
            if attempt == max_retries - 1:
                self._ensure_ok(response, action)
            retry_after = self._retry_after_seconds(response)
            await asyncio.sleep(retry_after if retry_after is not None else delay)
            delay = min(delay * 2, 30.0)
        assert response is not None
        return response

    def _ensure_ok(self, response: httpx.Response, action: str) -> None:

        if response.status_code == 401:

            raise TifluxApiError("Token TiFlux inválido ou sem permissão.", 401)

        if response.status_code == 429:

            raise TifluxApiError(
                f"Limite de requisições TiFlux atingido ao {action}. Aguarde alguns segundos e tente novamente.",
                429,
                response.text,
            )

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





def _parse_datetime_value(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _latest_datetime_from_items(items: list[dict], keys: tuple[str, ...]) -> datetime | None:
    latest: datetime | None = None
    for item in items:
        for key in keys:
            dt = _parse_datetime_value(item.get(key))
            if dt and (latest is None or dt > latest):
                latest = dt
    return latest


def _extract_client_list(data: object) -> list[dict]:

    if isinstance(data, list):

        return [x for x in data if isinstance(x, dict)]

    if isinstance(data, dict):

        for key in ("clients", "data", "items", "results", "billings", "appointments"):

            chunk = data.get(key)

            if isinstance(chunk, list):

                return [x for x in chunk if isinstance(x, dict)]

    return []


