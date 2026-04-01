"""BaseScraper — classe abstrata para todos os scrapers LicitaBrasil."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Classe base para scrapers de portais de licitações.

    Implementa rate limiting, retry com backoff, e logging padronizado.
    Subclasses devem implementar `buscar_licitacoes` e `buscar_detalhes`.
    """

    portal: str = ""
    base_url: str = ""
    rate_limit_delay: float = 1.0  # segundos entre requests ao mesmo domínio
    max_retries: int = 3

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "LicitaBrasil/2.0"},
        )
        self._owns_client = client is None
        self._semaphore = asyncio.Semaphore(2)

    async def close(self):
        """Fecha o client HTTP se foi criado internamente."""
        if self._owns_client:
            await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Request com rate limiting e retry com backoff exponencial."""
        async with self._semaphore:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await self.client.request(method, url, **kwargs)
                    response.raise_for_status()
                    await asyncio.sleep(self.rate_limit_delay)
                    return response
                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500 and attempt < self.max_retries:
                        wait = 2**attempt
                        logger.warning(
                            "HTTP %d em %s — retry %d/%d em %ds",
                            e.response.status_code, url, attempt, self.max_retries, wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise
                except httpx.RequestError as e:
                    if attempt < self.max_retries:
                        wait = 2**attempt
                        logger.warning(
                            "Erro de rede em %s (%s) — retry %d/%d em %ds",
                            url, e, attempt, self.max_retries, wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise
        raise RuntimeError("Unreachable")  # pragma: no cover

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self._request("POST", url, **kwargs)

    @abstractmethod
    async def buscar_licitacoes(self, dias: int = 7, **filtros) -> list[dict]:
        """Retorna lista de licitações do portal.

        Args:
            dias: Buscar licitações dos últimos N dias.

        Returns:
            Lista de dicts prontos para upsert no banco.
        """
        ...

    @abstractmethod
    async def buscar_detalhes(self, id_licitacao: str) -> dict:
        """Retorna detalhes completos de uma licitação específica."""
        ...

    async def health_check(self) -> dict:
        """Verifica se o portal está acessível."""
        try:
            resp = await self.client.get(self.base_url, timeout=10.0)
            return {
                "portal": self.portal,
                "status": "ok" if resp.status_code < 400 else "degraded",
                "http_code": resp.status_code,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "portal": self.portal,
                "status": "offline",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
