import asyncio

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

    async def _list_clientes(self, params: dict) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/clientes",
                headers=self._auth_headers(),
                params=params,
            )

        if response.status_code == 401:
            raise VhsysApiError("Tokens VHSYS inválidos.", 401)
        if _is_not_found_response(response):
            return []
        if response.status_code >= 400:
            raise VhsysApiError(
                f"Erro ao listar clientes VHSYS: {response.status_code}.",
                response.status_code,
                response.text,
            )

        data = response.json()
        if isinstance(data, dict) and int(data.get("code", 200)) == 403:
            return []

        if isinstance(data, dict):
            code = data.get("code")
            if code is not None and int(code) >= 400:
                message = data.get("message") or data.get("data") or "Erro VHSYS."
                raise VhsysApiError(str(message), int(code), response.text)

        return _extract_vhsys_clients(data)

    async def find_by_cnpj(self, cnpj_formatted: str) -> dict | None:
        clients = await self.find_matches_by_cnpj(cnpj_formatted, limit=5)
        return clients[0] if clients else None

    async def find_matches_by_cnpj(
        self,
        cnpj_formatted: str,
        limit: int = 10,
        *,
        lixeira: str = "Nao",
    ) -> list[dict]:
        return await self._list_clientes(
            {
                "cnpj_cliente": cnpj_formatted,
                "lixeira": lixeira,
                "limit": min(limit, 250),
            }
        )

    async def find_matches_by_name(
        self,
        name: str,
        limit: int = 10,
        *,
        lixeira: str = "Nao",
    ) -> list[dict]:
        term = (name or "").strip()
        if not term:
            return []

        seen: dict[int, dict] = {}
        for param_key in ("razao_cliente", "fantasia_cliente"):
            items = await self._list_clientes(
                {param_key: term, "lixeira": lixeira, "limit": 250}
            )
            for item in items:
                cid = item.get("id_cliente")
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

    async def find_by_name(self, name: str, limit: int = 10) -> list[dict]:
        return await self.find_matches_by_name(name, limit=limit, lixeira="Nao")

    async def find_matches_active_and_trash_by_cnpj(
        self, cnpj_formatted: str, limit: int = 10
    ) -> tuple[list[dict], list[dict]]:
        active, trash = await asyncio.gather(
            self.find_matches_by_cnpj(cnpj_formatted, limit=limit, lixeira="Nao"),
            self.find_matches_by_cnpj(cnpj_formatted, limit=limit, lixeira="Sim"),
        )
        return active, trash

    async def find_matches_active_and_trash_by_name(
        self, name: str, limit: int = 10
    ) -> tuple[list[dict], list[dict]]:
        active, trash = await asyncio.gather(
            self.find_matches_by_name(name, limit=limit, lixeira="Nao"),
            self.find_matches_by_name(name, limit=limit, lixeira="Sim"),
        )
        return active, trash

    async def get_by_id(self, id_cliente: int | str) -> dict | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/clientes/{id_cliente}",
                headers=self._auth_headers(),
            )

        if response.status_code == 401:
            raise VhsysApiError("Tokens VHSYS inválidos.", 401, response.text)
        if _is_not_found_response(response) or response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise VhsysApiError(
                f"Erro ao consultar cliente VHSYS: {response.status_code}.",
                response.status_code,
                response.text,
            )

        parsed = self._parse_response(response)
        data = parsed.get("data")
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        return None

    async def delete_client(self, id_cliente: int | str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{self._base}/clientes/{id_cliente}",
                headers=self._auth_headers(),
            )

        if response.status_code == 401:
            raise VhsysApiError("Tokens VHSYS inválidos.", 401, response.text)
        if response.status_code == 404:
            raise VhsysApiError("Cliente não encontrado no VHSYS.", 404, response.text)
        if response.status_code >= 400:
            raise VhsysApiError(
                f"Erro ao excluir cliente VHSYS: {response.status_code}.",
                response.status_code,
                response.text,
            )
        return self._parse_response(response)

    async def create_client(self, company: CompanyPayload) -> dict:
        payload = to_vhsys_payload(company)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base}/clientes",
                headers=self._json_headers(),
                json=payload,
            )

        return self._parse_response(response)

    async def _get_produtos_page(self, params: dict[str, str | int]) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/produtos",
                headers=self._auth_headers(),
                params=params,
            )
        if response.status_code == 401:
            raise VhsysApiError("Tokens VHSYS inválidos.", 401, response.text)
        if _is_not_found_response(response):
            return []
        if response.status_code >= 400:
            raise VhsysApiError(
                f"Erro ao listar produtos VHSYS: {response.status_code}.",
                response.status_code,
                response.text,
            )
        data = response.json()
        if isinstance(data, dict) and int(data.get("code", 200)) == 403:
            return []
        if isinstance(data, dict):
            code = data.get("code")
            if code is not None and int(code) >= 400:
                message = data.get("message") or data.get("data") or "Erro VHSYS."
                raise VhsysApiError(str(message), int(code), response.text)
        return _extract_vhsys_list(data)

    async def get_product(self, product_id: int) -> dict | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/produtos/{int(product_id)}",
                headers=self._auth_headers(),
            )
        if response.status_code == 401:
            raise VhsysApiError("Tokens VHSYS inválidos.", 401, response.text)
        if _is_not_found_response(response) or response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise VhsysApiError(
                f"Erro ao consultar produto VHSYS: {response.status_code}.",
                response.status_code,
                response.text,
            )
        parsed = self._parse_response(response)
        data = parsed.get("data")
        row: dict | None = None
        if isinstance(data, dict):
            row = data
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            row = data[0]
        if row is None:
            return None
        return _normalize_catalog_product(row)

    async def list_categories(
        self,
        *,
        lixeira: str = "Nao",
        limit: int = 250,
    ) -> list[dict]:
        """GET /categorias — categorias de produtos (não confundir com /categorias-clientes)."""
        page_size = min(max(limit, 1), 250)
        collected: list[dict] = []
        offset = 0
        max_pages = 40
        for _ in range(max_pages):
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self._base}/categorias",
                    headers=self._auth_headers(),
                    params={
                        "lixeira": lixeira,
                        "limit": page_size,
                        "offset": offset,
                        "subcategoria": 1,
                    },
                )
            if response.status_code == 401:
                raise VhsysApiError("Tokens VHSYS inválidos.", 401, response.text)
            if _is_not_found_response(response):
                break
            if response.status_code >= 400:
                raise VhsysApiError(
                    f"Erro ao listar categorias VHSYS: {response.status_code}.",
                    response.status_code,
                    response.text,
                )
            data = response.json()
            if isinstance(data, dict) and int(data.get("code", 200)) == 403:
                break
            if isinstance(data, dict):
                code = data.get("code")
                if code is not None and int(code) >= 400:
                    message = data.get("message") or data.get("data") or "Erro VHSYS."
                    raise VhsysApiError(str(message), int(code), response.text)
            page = _extract_vhsys_list(data)
            if not page:
                break
            collected.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        return collected

    async def list_subcategories(
        self,
        *,
        lixeira: str = "Nao",
        limit: int = 250,
        id_categoria: int | None = None,
    ) -> list[dict]:
        """GET /subcategorias — subcategorias de produtos vinculadas a categorias."""
        page_size = min(max(limit, 1), 250)
        collected: list[dict] = []
        offset = 0
        max_pages = 40
        for _ in range(max_pages):
            params: dict[str, str | int] = {
                "lixeira": lixeira,
                "limit": page_size,
                "offset": offset,
            }
            if id_categoria is not None and int(id_categoria) > 0:
                params["id_categoria"] = int(id_categoria)
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self._base}/subcategorias",
                    headers=self._auth_headers(),
                    params=params,
                )
            if response.status_code == 401:
                raise VhsysApiError("Tokens VHSYS inválidos.", 401, response.text)
            if _is_not_found_response(response):
                break
            if response.status_code >= 400:
                raise VhsysApiError(
                    f"Erro ao listar subcategorias VHSYS: {response.status_code}.",
                    response.status_code,
                    response.text,
                )
            data = response.json()
            if isinstance(data, dict) and int(data.get("code", 200)) == 403:
                break
            if isinstance(data, dict):
                code = data.get("code")
                if code is not None and int(code) >= 400:
                    message = data.get("message") or data.get("data") or "Erro VHSYS."
                    raise VhsysApiError(str(message), int(code), response.text)
            page = _extract_vhsys_list(data)
            if not page:
                break
            collected.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        return collected

    async def list_catalog_categories(self) -> list[dict]:
        """Categorias ativas + subcategorias aninhadas para o wizard de orçamento."""
        raw = await self.list_categories(lixeira="Nao")
        try:
            raw_subs = await self.list_subcategories(lixeira="Nao")
        except VhsysApiError:
            raw_subs = []
        by_cat: dict[int, dict[int, dict]] = {}
        for row in raw_subs:
            sub = _normalize_catalog_subcategory(row)
            if sub is None:
                continue
            cid = int(sub["category_id"])
            by_cat.setdefault(cid, {})[int(sub["id"])] = {
                "id": int(sub["id"]),
                "name": sub["name"],
            }
        items: list[dict] = []
        for row in raw:
            normalized = _normalize_catalog_category(row)
            if normalized is None:
                continue
            merged = {
                int(s["id"]): {"id": int(s["id"]), "name": s["name"]}
                for s in _subcategories_from_category_row(row)
            }
            merged.update(by_cat.get(int(normalized["id"]), {}))
            normalized["subcategories"] = sorted(
                merged.values(),
                key=lambda it: str(it.get("name") or "").casefold(),
            )
            items.append(normalized)
        items.sort(key=lambda it: str(it.get("name") or "").casefold())
        return items

    async def search_products(
        self,
        query: str = "",
        limit: int = 100,
        *,
        lixeira: str = "Nao",
        filter_key: str | None = "desc_produto",
    ) -> list[dict]:
        """GET /produtos — pagina até `limit`. `limit<=0` = catálogo completo."""
        fetch_all = limit <= 0
        target = 10_000 if fetch_all else min(max(limit, 1), 10_000)
        page_size = 250
        term = (query or "").strip()
        collected: list[dict] = []
        offset = 0
        max_pages = 80  # 80 * 250 = 20k hard stop
        for _ in range(max_pages):
            params: dict[str, str | int] = {
                "lixeira": lixeira,
                "limit": page_size,
                "offset": offset,
            }
            if term and filter_key:
                params[filter_key] = term
            page = await self._get_produtos_page(params)
            if not page:
                break
            collected.extend(page)
            if len(page) < page_size:
                break
            if not fetch_all and len(collected) >= target:
                break
            offset += page_size
        return collected if fetch_all else collected[:target]

    async def search_catalog_items(
        self,
        query: str = "",
        limit: int = 100,
        *,
        category_id: int | None = None,
        subcategory_id: int | None = None,
    ) -> list[dict]:
        """Normaliza produtos/serviços VHSYS. `limit<=0` = todos os ativos."""
        fetch_all = limit <= 0
        target = 10_000 if fetch_all else min(max(limit, 1), 10_000)
        term = (query or "").strip()
        raw_by_id: dict[int, dict] = {}

        def _ingest(rows: list[dict]) -> None:
            for row in rows:
                raw_id = row.get("id_produto")
                try:
                    pid = int(raw_id)
                except (TypeError, ValueError):
                    continue
                if pid not in raw_by_id:
                    raw_by_id[pid] = row

        # Sem filtro de texto: uma varredura completa (paginada).
        # Com filtro: desc + código (merge), ainda paginado até o fim se limit=0.
        # Doc /produtos não expõe query id_categoria → filtro pós-fetch.
        if term:
            _ingest(await self.search_products(term, limit=limit, filter_key="desc_produto"))
            _ingest(await self.search_products(term, limit=limit, filter_key="cod_produto"))
        else:
            _ingest(await self.search_products("", limit=limit, filter_key=None))

        items: list[dict] = []
        for row in raw_by_id.values():
            status = str(row.get("status_produto") or "").strip().lower()
            if status and status not in {"ativo", "active", "1", "sim"}:
                continue
            normalized = _normalize_catalog_product(row)
            if normalized is None:
                continue
            if category_id is not None and normalized.get("category_id") != category_id:
                continue
            if subcategory_id is not None:
                sub_ids = normalized.get("subcategory_ids") or []
                if subcategory_id not in sub_ids:
                    continue
            items.append(normalized)
            if not fetch_all and len(items) >= target:
                break
        items.sort(key=lambda it: str(it.get("name") or "").casefold())
        return items if fetch_all else items[:target]

    async def create_product(
        self,
        *,
        desc_produto: str,
        valor_produto: float = 0.0,
        tipo_produto: str = "Servico",
        unidade_produto: str = "UN",
        cod_produto: str | None = None,
        id_categoria: int | None = None,
        id_subcategoria: int | None = None,
    ) -> dict:
        """POST /produtos — cadastra produto/serviço no VHSYS (via dupla do orçamento)."""
        name = (desc_produto or "").strip()
        if not name:
            raise VhsysApiError("desc_produto é obrigatório.", 422)
        tipo = (tipo_produto or "Servico").strip()
        if tipo not in {"Servico", "Produto"}:
            raise VhsysApiError("tipo_produto deve ser Servico ou Produto.", 422)
        payload: dict[str, str | float | int] = {
            "desc_produto": name,
            "tipo_produto": tipo,
            "valor_produto": f"{max(0.0, float(valor_produto)):.2f}",
            "unidade_produto": (unidade_produto or "UN").strip() or "UN",
        }
        code = (cod_produto or "").strip()
        if code:
            payload["cod_produto"] = code
        if id_categoria is not None and int(id_categoria) > 0:
            payload["id_categoria"] = int(id_categoria)
        if id_subcategoria is not None and int(id_subcategoria) > 0:
            payload["id_subcategoria"] = int(id_subcategoria)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base}/produtos",
                headers=self._json_headers(),
                json=payload,
            )
        if response.status_code == 401:
            raise VhsysApiError("Tokens VHSYS inválidos.", 401, response.text)
        if response.status_code >= 400:
            raise VhsysApiError(
                f"Erro ao cadastrar produto VHSYS: {response.status_code}.",
                response.status_code,
                response.text,
            )
        parsed = self._parse_response(response)
        data = parsed.get("data") if isinstance(parsed, dict) else None
        if isinstance(data, list) and data:
            row = data[0] if isinstance(data[0], dict) else {}
        elif isinstance(data, dict):
            row = data
        else:
            row = {}
        # Garantir campos usados pelo normalizer (POST pode omitir status).
        if "desc_produto" not in row:
            row["desc_produto"] = name
        if "valor_produto" not in row:
            row["valor_produto"] = payload["valor_produto"]
        if "status_produto" not in row:
            row["status_produto"] = "Ativo"
        if "tipo_produto" not in row:
            row["tipo_produto"] = tipo
        if id_categoria is not None and "id_categoria" not in row:
            row["id_categoria"] = int(id_categoria)
        if id_subcategoria is not None and "id_subcategoria" not in row:
            row["id_subcategoria"] = int(id_subcategoria)
        return row

    async def find_or_create_catalog_item(
        self,
        *,
        name: str,
        unit_value: float = 0.0,
        tipo_produto: str = "Servico",
        unidade_produto: str = "UN",
        id_categoria: int | None = None,
        id_subcategoria: int | None = None,
    ) -> tuple[dict, bool]:
        """
        Via dupla: se nome já existir (casefold) no catálogo ativo, devolve existente.
        Senão, POST /produtos e devolve o criado. Retorno: (item_normalizado, created).
        """
        term = (name or "").strip()
        if not term:
            raise VhsysApiError("Nome do produto é obrigatório.", 422)

        # Match exacto no catálogo completo (paginado) — independente da categoria.
        catalog = await self.search_catalog_items("", limit=0)
        needle = term.casefold()
        for item in catalog:
            if str(item.get("name") or "").casefold() == needle:
                return item, False

        raw = await self.create_product(
            desc_produto=term,
            valor_produto=unit_value,
            tipo_produto=tipo_produto,
            unidade_produto=unidade_produto,
            id_categoria=id_categoria,
            id_subcategoria=id_subcategoria,
        )
        normalized = _normalize_catalog_product(raw)
        if normalized is None:
            raise VhsysApiError(
                "Produto criado no VHSYS, mas resposta sem id_produto.",
                502,
                str(raw),
            )
        return normalized, True

    async def create_service_order(self, payload: dict) -> dict:
        """POST /ordens-servico — O2.0 Go (doc)."""
        if not isinstance(payload, dict) or not payload:
            raise VhsysApiError("Payload de OS VHSYS inválido.", 422)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base}/ordens-servico",
                headers=self._json_headers(),
                json=payload,
            )
        return self._parse_response(response)

    async def list_service_orders(self, params: dict | None = None) -> list[dict]:
        """GET /ordens-servico."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/ordens-servico",
                headers=self._auth_headers(),
                params=params or {"limit": 50},
            )
        parsed = self._parse_response(response)
        return _extract_vhsys_list(parsed)

    async def create_service_invoice(self, payload: dict) -> dict:
        """POST /notas-servico — NFS-e (F1 live / O2.0 Go)."""
        if not isinstance(payload, dict) or not payload:
            raise VhsysApiError("Payload de NF serviço VHSYS inválido.", 422)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base}/notas-servico",
                headers=self._json_headers(),
                json=payload,
            )
        return self._parse_response(response)

    async def list_service_invoices(self, params: dict | None = None) -> list[dict]:
        """GET /notas-servico."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/notas-servico",
                headers=self._auth_headers(),
                params=params or {"limit": 50},
            )
        parsed = self._parse_response(response)
        return _extract_vhsys_list(parsed)

    async def create_accounts_receivable(self, payload: dict) -> dict:
        """POST /contas-receber — CR; boleto via tipo_conta=Boleto → link_boleto."""
        if not isinstance(payload, dict) or not payload:
            raise VhsysApiError("Payload de conta a receber VHSYS inválido.", 422)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base}/contas-receber",
                headers=self._json_headers(),
                json=payload,
            )
        return self._parse_response(response)

    async def list_accounts_receivable(self, params: dict | None = None) -> list[dict]:
        """GET /contas-receber."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base}/contas-receber",
                headers=self._auth_headers(),
                params=params or {"limit": 50},
            )
        parsed = self._parse_response(response)
        return _extract_vhsys_list(parsed)

    @staticmethod
    def extract_boleto_link(cr_response: dict) -> str | None:
        """Extrai link_boleto de resposta/listagem de CR (Go parcial O2.0)."""
        data = cr_response.get("data") if isinstance(cr_response, dict) else None
        candidates: list[dict] = []
        if isinstance(data, dict):
            candidates.append(data)
        elif isinstance(data, list):
            candidates.extend(x for x in data if isinstance(x, dict))
        if isinstance(cr_response, dict):
            candidates.append(cr_response)
        for item in candidates:
            link = item.get("link_boleto")
            if isinstance(link, str) and link.strip():
                return link.strip()
        return None


def _extract_vhsys_list(data: object) -> list[dict]:
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
        if isinstance(inner, dict):
            return [inner]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _extract_vhsys_clients(data: object) -> list[dict]:
    return _extract_vhsys_list(data)


def _parse_vhsys_money(raw: object) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace("R$", "").replace(" ", "")
    if not text:
        return 0.0
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _positive_int(raw: object) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _normalize_catalog_subcategory(row: dict) -> dict | None:
    subcategory_id = _positive_int(row.get("id_subcategoria") or row.get("id"))
    category_id = _positive_int(row.get("id_categoria"))
    if subcategory_id is None or category_id is None:
        return None
    name = str(row.get("nome_subcategoria") or row.get("name") or "").strip()
    if not name:
        return None
    status = str(row.get("status_subcategoria") or "").strip().lower()
    if status and status not in {"ativo", "active", "1", "sim"}:
        return None
    trash = str(row.get("lixeira") or "").strip().lower()
    if trash in {"sim", "s", "1", "true"}:
        return None
    return {"id": subcategory_id, "name": name, "category_id": category_id}


def _subcategories_from_category_row(row: dict) -> list[dict]:
    raw = row.get("subcategorias") or row.get("subcategoria")
    if isinstance(raw, dict):
        items = [raw]
    elif isinstance(raw, list):
        items = [x for x in raw if isinstance(x, dict)]
    else:
        return []
    parent_id = _positive_int(row.get("id_categoria"))
    out: list[dict] = []
    seen: set[int] = set()
    for item in items:
        payload = dict(item)
        if parent_id is not None and payload.get("id_categoria") is None:
            payload["id_categoria"] = parent_id
        normalized = _normalize_catalog_subcategory(payload)
        if normalized is None or int(normalized["id"]) in seen:
            continue
        seen.add(int(normalized["id"]))
        out.append({"id": int(normalized["id"]), "name": normalized["name"]})
    return out


def _product_subcategory_ids(row: dict) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()

    def _add(raw: object) -> None:
        value = _positive_int(raw)
        if value is None or value in seen:
            return
        seen.add(value)
        ids.append(value)

    _add(row.get("id_subcategoria"))
    raw = row.get("subcategoria") or row.get("subcategorias")
    if isinstance(raw, dict):
        _add(raw.get("id_subcategoria") or raw.get("id"))
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                _add(item.get("id_subcategoria") or item.get("id"))
            else:
                _add(item)
    return ids


def _normalize_catalog_category(row: dict) -> dict | None:
    raw_id = row.get("id_categoria")
    if raw_id is None:
        return None
    try:
        category_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    name = str(row.get("nome_categoria") or "").strip()
    if not name:
        return None
    status = str(row.get("status_categoria") or "").strip().lower()
    if status and status not in {"ativo", "active", "1", "sim"}:
        return None
    trash = str(row.get("lixeira") or "").strip().lower()
    if trash in {"sim", "s", "1", "true"}:
        return None
    return {
        "id": category_id,
        "name": name,
        "subcategories": _subcategories_from_category_row(row),
    }


def _normalize_catalog_product(row: dict) -> dict | None:
    raw_id = row.get("id_produto")
    if raw_id is None:
        return None
    try:
        product_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    name = str(row.get("desc_produto") or row.get("nome_produto") or "").strip()
    if not name:
        return None
    code = str(row.get("cod_produto") or "").strip() or None
    unit_value = _parse_vhsys_money(row.get("valor_produto"))
    raw_cost = row.get("valor_custo_produto")
    cost_value: float | None
    if raw_cost is None or str(raw_cost).strip() in {"", "-"}:
        cost_value = None
    else:
        cost_value = _parse_vhsys_money(raw_cost)
    supplier_name = str(row.get("fornecedor_produto") or "").strip() or None
    supplier_id: int | None = None
    raw_sup = row.get("fornecedor_produto_id")
    if raw_sup is not None and str(raw_sup).strip() not in {"", "0"}:
        try:
            supplier_id = int(raw_sup)
        except (TypeError, ValueError):
            supplier_id = None
    category_id: int | None = None
    raw_cat = row.get("id_categoria")
    if raw_cat is not None and str(raw_cat).strip() not in {"", "0"}:
        try:
            category_id = int(raw_cat)
        except (TypeError, ValueError):
            category_id = None
    return {
        "id": product_id,
        "kind": "produto",
        "name": name,
        "code": code,
        "unit_value": unit_value,
        "cost_value": cost_value,
        "supplier_name": supplier_name,
        "supplier_id": supplier_id,
        "category_id": category_id,
        "subcategory_ids": _product_subcategory_ids(row),
    }


def normalize_vhsys_party(row: dict) -> dict | None:
    """Cliente VHSYS → opção 'Faturado por'."""
    raw_id = row.get("id_cliente")
    if raw_id is None:
        return None
    try:
        client_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    name = str(
        row.get("razao_cliente")
        or row.get("fantasia_cliente")
        or row.get("nome_cliente")
        or ""
    ).strip()
    if not name:
        return None
    fantasy = str(row.get("fantasia_cliente") or "").strip() or None
    return {
        "id": client_id,
        "name": name,
        "fantasy_name": fantasy,
        "cnpj": str(row.get("cnpj_cliente") or "").strip() or None,
    }

