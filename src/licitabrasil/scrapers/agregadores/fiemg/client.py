"""Cliente HTTP do portal FIEMG Compras."""

from __future__ import annotations

import asyncio
import random
from typing import Optional

import httpx
from loguru import logger

from .config import Settings


class FIEMGClient:
    """Cliente assíncrono para licitacoes.compras.fiemg.com.br."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(settings.max_concurrent)
        self._authenticated = False

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.settings.request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
            },
        )

        if self.settings.login and self.settings.password:
            await self._login()

        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def _login(self) -> None:
        """Login opcional. # PROBE: validar endpoint de auth e form fields."""
        try:
            login_url = f"{self.settings.base_url}/portal/login"
            resp = await self._client.post(  # type: ignore[union-attr]
                login_url,
                data={
                    "username": self.settings.login,
                    "password": self.settings.password,
                },
            )
            self._authenticated = resp.status_code == 200
            if self._authenticated:
                logger.info("FIEMG: login bem-sucedido")
        except Exception as exc:
            logger.warning(f"FIEMG login falhou ({exc}). Continuando sem autenticação.")

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with self._semaphore:
            last_exc: Optional[Exception] = None
            for attempt in range(1, self.settings.max_retries + 1):
                try:
                    resp = await self._client.request(method, url, **kwargs)  # type: ignore[union-attr]
                    resp.raise_for_status()
                    await asyncio.sleep(self.settings.delay_seconds)
                    return resp
                except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                    last_exc = exc
                    if (
                        isinstance(exc, httpx.HTTPStatusError)
                        and exc.response.status_code == 404
                    ):
                        raise
                    wait = 2**attempt + random.uniform(0, 1)
                    logger.warning(
                        f"FIEMG retry {attempt}/{self.settings.max_retries} em {url}: {exc} "
                        f"(wait {wait:.1f}s)"
                    )
                    await asyncio.sleep(wait)
            assert last_exc is not None
            raise last_exc

    # ── endpoints ──────────────────────────────────────────────────

    async def fetch_feed(self) -> str:
        try:
            resp = await self._request("GET", self.settings.feed_url)
            return resp.text
        except Exception as exc:
            logger.info(f"Feed FIEMG indisponível ({exc}). Caindo no HTML.")
            return ""

    async def fetch_listing(self, page: int = 1) -> str:
        url = self.settings.listing_url
        params = {"page": page} if page > 1 else None
        resp = await self._request("GET", url, params=params)
        return resp.text

    async def fetch_detail(self, sde: str) -> str:
        # Aceita 'SDE-2026001650' ou '2026001650'
        clean = sde.replace("SDE-", "").replace("SDE ", "").strip()
        url = self.settings.detail_url(clean)
        resp = await self._request("GET", url)
        return resp.text

    async def health_check(self) -> dict:
        try:
            resp = await self._client.get(  # type: ignore[union-attr]
                self.settings.base_url, timeout=10.0
            )
            return {
                "status": "ok" if resp.status_code < 400 else "degraded",
                "http_code": resp.status_code,
            }
        except Exception as exc:
            return {"status": "offline", "error": str(exc)}
