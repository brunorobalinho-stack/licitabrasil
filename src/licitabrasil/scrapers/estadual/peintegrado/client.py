"""Cliente HTTP do PE-Integrado.

O portal usa **ASP.NET WebForms** com ``__VIEWSTATE`` / ``__EVENTVALIDATION``.
A página inicial vem vazia (sem ``<tr>`` de dados); os registros chegam via
``__doPostBack`` — um POST que devolve a tabela renderizada server-side.

Estratégia:

1. GET inicial — captura ``__VIEWSTATE``, ``__VIEWSTATEGENERATOR``,
   ``__EVENTVALIDATION``.
2. POST com ``__EVENTTARGET`` apontando para o controle de ordenação ou
   paginação. Os parâmetros vêm do JS embutido (``btOrdenarPor_Click``,
   ``btPaginacao_Click``).
3. Cada response atualiza os campos hidden — preservar entre chamadas.

⚠ Endpoints validados em probe 2026-05-12:

* ``/Portal/Pages/LicitacoesEmAndamento.aspx`` (pregões/concorrências)
* ``/Portal/Pages/DispensaLicitacoes.aspx`` (CCD)
* ``/Portal/Pages/LicitacoesEncerradas.aspx``
"""

from __future__ import annotations

import asyncio
import random
import re
from typing import Optional

import httpx
from loguru import logger

from .config import Settings


# ASP.NET hidden fields que precisam acompanhar todo POST
ASPNET_FIELDS = (
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
    "__VIEWSTATEENCRYPTED",
)

HIDDEN_REGEX = re.compile(
    r'<input[^>]*name="(__[A-Z]+\w*)"[^>]*value="([^"]*)"', re.IGNORECASE
)


class PEIntegradoClient:
    """Cliente assíncrono para o portal PE-Integrado (ASP.NET WebForms)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(settings.max_concurrent)
        # State ASP.NET por URL — cada endpoint tem seu próprio ViewState
        self._aspnet_state: dict[str, dict[str, str]] = {}

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.settings.request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    # ── HTTP helpers ────────────────────────────────────────────────

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Request com retry exponencial e rate limit."""
        async with self._semaphore:
            last_exc: Optional[Exception] = None
            for attempt in range(1, self.settings.max_retries + 1):
                try:
                    resp = await self._client.request(method, url, **kwargs)  # type: ignore[union-attr]
                    resp.raise_for_status()
                    await asyncio.sleep(self.settings.delay_seconds)
                    self._capture_state(url, resp.text)
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
                        f"PE-Integrado tentativa {attempt}/{self.settings.max_retries} "
                        f"em {url}: {exc}. Retry em {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)
            assert last_exc is not None
            raise last_exc

    def _capture_state(self, url: str, html: str) -> None:
        """Extrai e armazena hidden fields ASP.NET para o endpoint."""
        key = self._state_key(url)
        state = self._aspnet_state.setdefault(key, {})
        for name, value in HIDDEN_REGEX.findall(html):
            if name in ASPNET_FIELDS:
                state[name] = value

    def _state_key(self, url: str) -> str:
        # Considera apenas o path como chave
        return re.sub(r"\?.*$", "", url).lower()

    def _form_data(self, url: str, extras: dict[str, str] | None = None) -> dict[str, str]:
        """Monta dict de form-data com os hidden ASP.NET preservados."""
        state = dict(self._aspnet_state.get(self._state_key(url), {}))
        if extras:
            state.update(extras)
        return state

    # ── endpoints ──────────────────────────────────────────────────

    async def fetch_landing(self, kind: str = "andamento") -> str:
        """GET inicial — captura ViewState."""
        path = {
            "andamento": self.settings.listing_andamento_path,
            "dispensa": self.settings.listing_dispensa_path,
            "encerradas": self.settings.listing_encerradas_path,
        }[kind]
        resp = await self._request("GET", f"{self.settings.base_url}{path}")
        return resp.text

    async def fetch_listing(self, page: int = 1, kind: str = "andamento") -> str:
        """Busca página da listagem.

        Em page=1 faz GET (carrega tabela vazia + ViewState).
        Em page>1 faz POST com __EVENTTARGET de paginação.

        # PROBE: a primeira invocação do PE-Integrado retorna a página HTML
        # sem dados — eles são carregados após o usuário clicar "Pesquisar"
        # ou ordenar. Para o scraper, fazemos um POST simulando clique no
        # botão de busca/ordenação no campo SNRPROCESSODISPLAY.
        """
        path = {
            "andamento": self.settings.listing_andamento_path,
            "dispensa": self.settings.listing_dispensa_path,
            "encerradas": self.settings.listing_encerradas_path,
        }[kind]
        url = f"{self.settings.base_url}{path}"

        if page == 1 and not self._aspnet_state.get(self._state_key(url)):
            # GET inicial
            resp = await self._request("GET", url)
            return resp.text

        # POST com postback — simula ordenação pela coluna processo (carrega dados)
        # # PROBE: o nome do controle ('ctl00$...') pode variar; ler do HTML
        # # inicial os EVENTTARGET disponíveis se necessário.
        extras = {
            "__EVENTTARGET": "ctl00$ConteudoPagina$btOrdenarPor",
            "__EVENTARGUMENT": "SNRPROCESSODISPLAY",
            "ctl00$ConteudoPagina$paginaAtual": str(page),
        }
        data = self._form_data(url, extras=extras)
        resp = await self._request("POST", url, data=data)
        return resp.text

    async def fetch_detail(self, processo: str) -> str:
        """Busca página de detalhe de um processo específico."""
        url = self.settings.detail_url(processo)
        resp = await self._request("GET", url)
        return resp.text

    async def fetch_feed(self) -> str:
        """Tenta baixar RSS — retorna '' se 404."""
        try:
            resp = await self._request("GET", self.settings.feed_url)
            return resp.text
        except Exception as exc:
            logger.info(f"Feed RSS PE-Integrado indisponível ({exc}).")
            return ""

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

    # Compat property usada pelo cli probe
    @property
    def _view_state(self) -> Optional[str]:
        for state in self._aspnet_state.values():
            if state.get("__VIEWSTATE"):
                return state["__VIEWSTATE"][:30] + "..."
        return None
