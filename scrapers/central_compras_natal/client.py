"""HTTP client para Central de Compras de Natal/RN."""

import asyncio
from typing import Optional

import httpx
from loguru import logger

from .config import Settings
from .retry import retry_http


class NatalClient:
    """Client HTTP com retry, rate limiting e decode ISO-8859-1."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrent)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.request_timeout, connect=30.0),
            verify=self.settings.verify_ssl,
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    @retry_http
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Request com semaphore, delay e retry via tenacity (backoff exponencial 1-10s)."""
        async with self._semaphore:
            if method == "GET":
                resp = await self._client.get(url, **kwargs)
            else:
                resp = await self._client.post(url, **kwargs)
            resp.raise_for_status()
            await asyncio.sleep(self.settings.delay_seconds)
            return resp

    def _decode(self, resp: httpx.Response) -> str:
        """Decode ISO-8859-1."""
        return resp.content.decode("iso-8859-1", errors="replace")

    async def fetch_listing(self, mod: str, page: int = 1) -> str:
        """Busca pagina de listagem via POST form."""
        data = {"mod": mod, "pagina": str(page)}
        resp = await self._request("POST", self.settings.listing_url, data=data)
        return self._decode(resp)

    async def fetch_detail(self, mod: str, record_id: int) -> Optional[str]:
        """Busca pagina de detalhe via GET."""
        url = self.settings.detail_url(mod, record_id)
        try:
            resp = await self._request("GET", url)
            html = self._decode(resp)
            # Validate we got the detail page
            if "Detalhamento" in html or "Nr.Licita" in html:
                return html
            logger.warning(f"Detail page missing expected content: {mod}&id={record_id}")
            return None
        except Exception as e:
            logger.warning(f"Detail fetch failed for {mod}&id={record_id}: {e}")
            return None
