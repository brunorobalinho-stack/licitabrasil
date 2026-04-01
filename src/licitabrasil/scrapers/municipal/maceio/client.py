"""HTTP client com rate limiting, retry e backoff."""

import asyncio
from typing import Optional

import httpx
from loguru import logger

from .config import Settings
from .models import Licitacao, Orgao, Homologacao, Empresa, AtaRegistro, Documento


class MaceioClient:
    """Client HTTP para o portal de licitações de Maceió."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrent)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.settings.request_timeout,
            headers={"User-Agent": self.settings.user_agent},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def _fetch(self, url: str) -> httpx.Response:
        """Fetch com semaphore, delay e retry com backoff."""
        async with self._semaphore:
            last_exc = None
            for attempt in range(self.settings.max_retries):
                try:
                    resp = await self._client.get(url)
                    resp.raise_for_status()
                    await asyncio.sleep(self.settings.delay_seconds)
                    return resp
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    last_exc = e
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                        raise  # Don't retry 404s
                    wait = 2 ** attempt
                    logger.warning(f"Attempt {attempt+1}/{self.settings.max_retries} failed for {url}: {e}. Retrying in {wait}s...")
                    await asyncio.sleep(wait)
            raise last_exc

    # ── API methods ──────────────────────────────────

    async def fetch_licitacao_api(self, licitacao_id: int) -> Optional[Licitacao]:
        """Busca uma licitação individual pela API JSON."""
        url = self.settings.detail_api_url(licitacao_id)
        try:
            resp = await self._fetch(url)
            data = resp.json()

            # API wraps in {"data": {...}} for individual, or returns array for bulk
            if isinstance(data, dict) and "data" in data:
                record = data["data"]
            elif isinstance(data, dict):
                record = data
            else:
                return None

            return self._parse_api_record(licitacao_id, record, resp.text)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.warning(f"API error for ID {licitacao_id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to parse API response for ID {licitacao_id}: {e}")
            return None

    async def fetch_bulk_api(self) -> list[Licitacao]:
        """Busca a lista completa via API (retorna ~47 registros)."""
        url = self.settings.api_base
        try:
            resp = await self._fetch(url)
            records = resp.json()
            if not isinstance(records, list):
                logger.warning("Bulk API didn't return a list")
                return []

            results = []
            for i, record in enumerate(records):
                try:
                    lic = self._parse_api_record(i + 1, record)
                    if lic:
                        results.append(lic)
                except Exception as e:
                    logger.warning(f"Failed to parse bulk record {i}: {e}")
            return results
        except Exception as e:
            logger.error(f"Bulk API fetch failed: {e}")
            return []

    # ── HTML listing ────────────────────────────────

    async def fetch_listing_page(self, page: int) -> str:
        """Busca uma página HTML da listagem."""
        url = self.settings.listing_page_url(page)
        resp = await self._fetch(url)
        return resp.text

    async def fetch_listing_ids(self, max_pages: int = 0) -> list[int]:
        """Descobre todos os IDs de licitações via HTML listing."""
        from .parser import parse_listing_page, parse_total_pages

        logger.info("Discovering licitação IDs from HTML listing...")
        first_html = await self.fetch_listing_page(1)
        total_pages = parse_total_pages(first_html)

        if max_pages > 0:
            total_pages = min(total_pages, max_pages)

        logger.info(f"Total pages to scrape: {total_pages}")

        all_ids = []
        # Parse first page
        items = parse_listing_page(first_html)
        all_ids.extend(item.id for item in items)
        logger.debug(f"Page 1: {len(items)} items")

        # Fetch remaining pages with concurrency
        for page in range(2, total_pages + 1):
            try:
                html = await self.fetch_listing_page(page)
                items = parse_listing_page(html)
                all_ids.extend(item.id for item in items)
                if page % 50 == 0:
                    logger.info(f"Progress: page {page}/{total_pages} ({len(all_ids)} IDs)")
            except Exception as e:
                logger.warning(f"Failed to fetch page {page}: {e}")

        logger.info(f"Discovered {len(all_ids)} licitação IDs")
        return sorted(set(all_ids))

    async def fetch_document(self, url: str) -> Optional[bytes]:
        """Downloads a document, returns raw bytes."""
        try:
            resp = await self._fetch(url)
            return resp.content
        except Exception as e:
            logger.warning(f"Failed to download document {url}: {e}")
            return None

    # ── Parsing helpers ─────────────────────────────

    def _parse_api_record(self, licitacao_id: int, record, raw: str = None) -> Optional[Licitacao]:
        """Converte um registro JSON da API em modelo Licitacao."""
        if not isinstance(record, dict):
            logger.warning(f"Record {licitacao_id} is not a dict: {type(record)}")
            return None
        try:
            orgao_data = record.get("orgao")
            orgao = Orgao(**orgao_data) if orgao_data and isinstance(orgao_data, dict) else None

            homologacoes = []
            for h in record.get("homologacoes", []) or []:
                if not isinstance(h, dict):
                    continue
                empresa_data = h.get("empresa")
                empresa = Empresa(**empresa_data) if empresa_data and isinstance(empresa_data, dict) else None
                homologacoes.append(Homologacao(
                    data_publicacao_homologacao=h.get("data_publicacao_homologacao"),
                    data_publicacao_extrato=h.get("data_publicacao_extrato"),
                    lotes=h.get("lotes", ""),
                    valor_estimado=h.get("valor_estimado", 0) or 0,
                    valor_contratado=h.get("valor_contratado", 0) or 0,
                    empresa=empresa,
                    arquivo=h.get("arquivo"),
                ))

            atas = []
            for a in record.get("atas", []) or []:
                if not isinstance(a, dict):
                    continue
                empresa_data = a.get("empresa")
                empresa = Empresa(**empresa_data) if empresa_data and isinstance(empresa_data, dict) else None
                atas.append(AtaRegistro(
                    numero=a.get("numero", ""),
                    data_assinatura=a.get("data_assinatura"),
                    data_publicacao=a.get("data_publicacao"),
                    vigencia_inicio=a.get("vigencia_inicio"),
                    vigencia_fim=a.get("vigencia_fim"),
                    empresa=empresa,
                    arquivo=a.get("arquivo"),
                ))

            documentos = []
            for d in record.get("documentos", []) or []:
                if not isinstance(d, dict):
                    continue
                documentos.append(Documento(
                    tipo=d.get("tipo", ""),
                    descricao=d.get("descricao", ""),
                    criado_em=d.get("criado_em"),
                    arquivo=d.get("arquivo", ""),
                ))

            return Licitacao(
                id=licitacao_id,
                num_processo=record.get("num_processo", ""),
                objeto=record.get("objeto", ""),
                data_abertura=record.get("data_abertura"),
                hora_abertura=record.get("hora_abertura", "") or "",
                data_fechamento=record.get("data_fechamento"),
                hora_fechamento=record.get("hora_fechamento"),
                numero_modalidade=record.get("numero_modalidade", 0) or 0,
                ano_modalidade=record.get("ano_modalidade", 0) or 0,
                modalidade=record.get("modalidade", ""),
                orgao=orgao,
                cota=record.get("cota", ""),
                status=record.get("status", ""),
                responsavel=record.get("responsavel", ""),
                homologacoes=homologacoes,
                atas=atas,
                documentos=documentos,
                raw_json=raw,
            )
        except Exception as e:
            logger.warning(f"Failed to parse record ID {licitacao_id}: {e}")
            return None
