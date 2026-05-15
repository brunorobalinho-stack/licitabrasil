"""Cliente HTTP async para a API PNCP (filtro Prefeitura de SP)."""

import asyncio
from typing import Optional

import httpx
from loguru import logger

from .config import Settings, MODALIDADES


class PrefeituraSPClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrent)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        # Separa connect (10s) de read (settings.request_timeout): o
        # gargalo das modalidades grandes do PNCP e a fase de LEITURA da
        # resposta (a API demora pra montar paginas com milhares de
        # registros), nao a conexao. Sem essa separacao, um httpx.Timeout
        # escalar aplicava o mesmo valor pra tudo e o connect ficava
        # generoso demais sem que o read recebesse a folga necessaria.
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=float(self.settings.request_timeout),
                write=10.0,
                pool=10.0,
            ),
            headers={"User-Agent": self.settings.user_agent},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def _get(self, url: str, params: dict) -> dict | None:
        """GET com semaphore, delay e retry."""
        async with self._semaphore:
            last_exc = None
            for attempt in range(self.settings.max_retries):
                try:
                    resp = await self._client.get(url, params=params)
                    resp.raise_for_status()
                    await asyncio.sleep(self.settings.delay_seconds)
                    text = resp.text.strip()
                    if not text:
                        logger.debug(f"Empty response for {params}")
                        return None
                    return resp.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (404, 422):
                        logger.debug(f"HTTP {e.response.status_code} for {params}")
                        return None
                    last_exc = e
                except (httpx.RequestError, Exception) as e:
                    last_exc = e

                wait = 2 ** attempt
                logger.warning(
                    f"Attempt {attempt+1}/{self.settings.max_retries} failed: {last_exc}. "
                    f"Retrying in {wait}s..."
                )
                await asyncio.sleep(wait)

            logger.error(f"All {self.settings.max_retries} attempts failed: {last_exc}")
            return None

    async def fetch_page(
        self,
        data_inicial: str,
        data_final: str,
        modalidade: int,
        pagina: int = 1,
    ) -> dict | None:
        """Busca uma página de licitações no PNCP.

        Args:
            data_inicial: yyyyMMdd
            data_final: yyyyMMdd
            modalidade: código 1-13
            pagina: número da página (1-based)

        Returns:
            dict com {data, totalRegistros, totalPaginas, ...} ou None se falhou.
        """
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": modalidade,
            "uf": self.settings.uf,
            "codigoMunicipioIbge": self.settings.ibge_municipio,
            "pagina": pagina,
            "tamanhoPagina": self.settings.page_size,
        }

        result = await self._get(self.settings.api_url, params)
        if result and not result.get("empty", True):
            logger.debug(
                f"mod={modalidade} ({MODALIDADES.get(modalidade, '?')}) "
                f"pag={pagina} items={len(result.get('data', []))}"
            )
        return result
