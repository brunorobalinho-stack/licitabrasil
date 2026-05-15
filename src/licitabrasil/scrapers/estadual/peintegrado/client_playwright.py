"""Cliente Playwright para PE-Integrado.

Use este client quando o ``httpx`` puro não consegue extrair dados — caso do
PE-Integrado, que renderiza a tabela via postback ASP.NET acionado por JS.

Instalação::

    pip install '.[browser]'
    playwright install chromium

Uso::

    from licitabrasil.scrapers.estadual.peintegrado.client_playwright import (
        PEIntegradoPlaywrightClient
    )
    async with PEIntegradoPlaywrightClient(settings) as c:
        html = await c.fetch_listing(kind="andamento")
"""

from __future__ import annotations

import asyncio
from typing import Optional

from loguru import logger

from .config import Settings


class PEIntegradoPlaywrightClient:
    """Cliente headless Chromium para extrair listagens completas do PE-Integrado.

    Estratégia:

    1. Abre a página alvo (LicitacoesEmAndamento / DispensaLicitacoes).
    2. Espera o ``<tbody>`` ser populado pelo postback automático.
    3. Itera paginação clicando no botão "Próximo" enquanto houver.
    4. Retorna o HTML completo de cada página.
    """

    def __init__(self, settings: Settings, headless: bool = True):
        self.settings = settings
        self.headless = headless
        self._browser = None
        self._context = None
        self._page = None

    async def __aenter__(self):
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Playwright não instalado. Rode: pip install '.[browser]' "
                "&& playwright install chromium"
            ) from exc

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            user_agent=self.settings.user_agent,
            locale="pt-BR",
            viewport={"width": 1440, "height": 900},
        )
        self._page = await self._context.new_page()
        return self

    async def __aexit__(self, *args):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_pw"):
            await self._pw.stop()

    # ── endpoints ──────────────────────────────────────────────────

    async def fetch_listing(
        self,
        kind: str = "andamento",
        max_pages: int = 1,
        wait_table_selector: str = "table.small-fonts-table tbody tr, table#exibirDados tbody tr",
    ) -> list[str]:
        """Carrega N páginas da listagem e retorna lista de HTMLs.

        Args:
            kind: 'andamento' | 'dispensa' | 'encerradas'
            max_pages: quantas páginas paginar (1 = só a primeira)
            wait_table_selector: CSS pra esperar a tabela popular.

        Returns:
            Lista de strings HTML — uma por página visitada.
        """
        path_map = {
            "andamento": self.settings.listing_andamento_path,
            "dispensa": self.settings.listing_dispensa_path,
            "encerradas": self.settings.listing_encerradas_path,
        }
        url = f"{self.settings.base_url}{path_map[kind]}"

        assert self._page is not None
        logger.info(f"Playwright: GET {url}")
        # networkidle (nao domcontentloaded): o postback ASP.NET de carga
        # inicial dispara DEPOIS do DOM montar. Esperar idle do network
        # cobre os dois casos (autoload OU sem autoload).
        await self._page.goto(url, wait_until="networkidle", timeout=30_000)

        # Algumas variantes do PE-Integrado nao auto-disparam o postback de
        # carga: chegam com tbody vazio e so populam apos clique em
        # "Pesquisar". Tentativa proativa cobre esse caso; se a tabela ja
        # esta populada, o click_pesquisar e no-op silencioso.
        await self._try_trigger_search()

        # Espera a tabela popular. Timeout subido de 15s pra 30s -- a
        # combinacao ASP.NET + postback as vezes passa de 15s quando o
        # lado servidor esta sobrecarregado.
        try:
            await self._page.wait_for_selector(wait_table_selector, timeout=30_000)
        except Exception:
            logger.warning(
                f"PE-Integrado/{kind}: tabela nao populou em 30s mesmo apos "
                "tentar Pesquisar. Retornando HTML como esta."
            )

        htmls: list[str] = [await self._page.content()]

        # Paginação: clica em "Próximo" até max_pages
        for page_num in range(2, max_pages + 1):
            next_btn = await self._page.query_selector(
                'a:has-text("Próximo"), button:has-text("Próximo"), '
                '.pagination a[aria-label*="próximo" i], '
                'a[onclick*="paginacao"]:not([disabled])'
            )
            if not next_btn:
                logger.info(f"Sem botão de próxima página — parando em {page_num - 1}")
                break

            try:
                await next_btn.click()
                await self._page.wait_for_load_state("networkidle", timeout=15_000)
                await asyncio.sleep(self.settings.delay_seconds)
                htmls.append(await self._page.content())
                logger.info(f"  Página {page_num} carregada")
            except Exception as exc:
                logger.warning(f"Falha ao navegar pra página {page_num}: {exc}")
                break

        return htmls

    async def _try_trigger_search(self) -> bool:
        """Tenta acionar o postback de carga clicando em "Pesquisar".

        Helper interno usado por fetch_listing pra cobrir variantes da
        peintegrado que chegam com a tabela vazia. Retorna True se algum
        botao foi clicado e o postback retornou; False se nao houver
        botao (caso em que a tabela ja foi populada por autoload). Nao
        levanta excecao -- falha graciosa pra nao quebrar o fluxo.
        """
        assert self._page is not None
        candidates = [
            'input[id$="btPesquisar"]',
            'input[id*="Pesquisar"]',
            'button:has-text("Pesquisar")',
            'input[value="Pesquisar"]',
            'a:has-text("Pesquisar")',
            '#btPesquisar',
        ]
        for sel in candidates:
            btn = await self._page.query_selector(sel)
            if not btn:
                continue
            try:
                await btn.click()
                await self._page.wait_for_load_state("networkidle", timeout=30_000)
                logger.info(f"PE-Integrado: postback acionado via '{sel}'")
                return True
            except Exception as exc:
                logger.warning(f"PE-Integrado: falha clicando em '{sel}': {exc}")
                continue
        logger.debug("PE-Integrado: nenhum botao Pesquisar localizado (autoload provavel).")
        return False

    async def click_pesquisar(self) -> str:
        """Clica em "Pesquisar" e devolve o HTML resultante.

        Mantido por compatibilidade externa. O fluxo interno do
        fetch_listing usa _try_trigger_search (mesma logica, mas
        booleano). Use este quando precisar do HTML cru pos-click.
        """
        assert self._page is not None
        await self._try_trigger_search()
        return await self._page.content()

    async def fetch_detail(self, processo: str) -> str:
        """Carrega página de detalhe. Caminho: navegar listagem → clicar no link."""
        assert self._page is not None
        url = self.settings.detail_url(processo)
        await self._page.goto(url, wait_until="networkidle")
        return await self._page.content()

    async def health_check(self) -> dict:
        assert self._page is not None
        try:
            resp = await self._page.goto(self.settings.base_url, timeout=10_000)
            return {
                "status": "ok" if (resp and resp.ok) else "degraded",
                "http_code": resp.status if resp else None,
            }
        except Exception as exc:
            return {"status": "offline", "error": str(exc)}
