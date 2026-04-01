"""HTTP client com sessao JSF/Seam, SSL self-signed, retry e rate limiting."""

import asyncio
import re
import urllib3
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from .config import Settings
from .retry import retry_http

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Default form fields for JSF POST
NO_SELECTION = "org.jboss.seam.ui.NoSelectionConverter.noSelectionValue"


class JsfSession:
    """Gerencia ViewState, jsessionid e cid do JBoss Seam."""

    def __init__(self):
        self.jsessionid: str = ""
        self.viewstate: str = ""
        self.cid: str = ""
        self.current_date: str = ""

    def update_from_html(self, html: str, url: str = ""):
        soup = BeautifulSoup(html, "html.parser")
        vs = soup.find("input", {"name": "javax.faces.ViewState"})
        if vs:
            self.viewstate = vs.get("value", self.viewstate)

        cid_match = re.search(r"cid=(\d+)", html)
        if cid_match:
            self.cid = cid_match.group(1)

        jsid_match = re.search(r"jsessionid=([^\"&\s]+)", html)
        if jsid_match:
            self.jsessionid = jsid_match.group(1)

        # Extract current date for calendar fields
        date_input = soup.find("input", {"name": re.compile(r"inicioAcolhimento.*CurrentDate")})
        if date_input:
            self.current_date = date_input.get("value", "")

    @property
    def action_url(self) -> str:
        base = "/licita-web/paginas/licita/PublicacaoList.seam"
        if self.jsessionid:
            return f"{base};jsessionid={self.jsessionid}"
        return base


class LicitawebClient:
    """Client HTTP para o Licitaweb (S2GPR/SEFAZ-CE)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrent)
        self._client: Optional[httpx.AsyncClient] = None
        self._session = JsfSession()

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
        """Decode response handling ISO-8859-1."""
        return resp.content.decode("iso-8859-1", errors="replace")

    # -- Listing -------------------------------------------------------

    async def init_listing_session(self) -> str:
        """GET inicial para obter sessao JSF. Retorna HTML da pagina 1."""
        resp = await self._request("GET", self.settings.listing_url)
        html = self._decode(resp)
        self._session.update_from_html(html, str(resp.url))
        logger.info(f"JSF session initialized: jsid={self._session.jsessionid[:20]}... cid={self._session.cid}")
        return html

    def _build_listing_form(self, page: int = 1, **filters) -> dict:
        """Monta form data para POST de paginacao."""
        data = {
            "formularioDeCrud": "formularioDeCrud",
            "javax.faces.ViewState": self._session.viewstate,
            "autoScroll": "",
            "formularioDeCrud:j_idcl": "",
            "formularioDeCrud:_link_hidden_": "",
            "formularioDeCrud:numeroCoepDecoration:numeroLicitacao": "",
            "formularioDeCrud:numeroViprocDecoration:numeroViproc": "",
            "formularioDeCrud:numeroEditalDecoration:sequencialParticipacao": "",
            "formularioDeCrud:numeroEdowebDecoration:numeroEdoweb": "",
            "formularioDeCrud:inicioAcolhimentoDecoration:inicioAcolhimentoPropostasInputDate": "",
            "formularioDeCrud:inicioAcolhimentoDecoration:inicioAcolhimentoPropostasInputCurrentDate": self._session.current_date or "03/2026",
            "formularioDeCrud:fimAcolhimentoDecoration:aberturaPropostasInputDate": "",
            "formularioDeCrud:fimAcolhimentoDecoration:aberturaPropostasInputCurrentDate": self._session.current_date or "03/2026",
            "formularioDeCrud:numeroEditalDecoration:numeroEditalOption": NO_SELECTION,
            "formularioDeCrud:promotorCotacaoDecoration:promotorLicitacao": NO_SELECTION,
            "formularioDeCrud:naturezaAquisicaoDecoration:naturezaAquisicao": NO_SELECTION,
            "formularioDeCrud:tipoAquisicaoDecoration:tipoAquisicao": NO_SELECTION,
            "formularioDeCrud:sistematicaAquisicaoDecoration:sistAquisicao": NO_SELECTION,
            "formularioDeCrud:formaAquisicaoDecoration:formaAquisicao": NO_SELECTION,
            "formularioDeCrud:statusDecoration:status": NO_SELECTION,
            "formularioDeCrud:microRegiaoDecoration:microRegiao": NO_SELECTION,
        }

        # Apply filters
        if filters.get("status"):
            data["formularioDeCrud:statusDecoration:status"] = filters["status"]

        # Page number via datascroller
        if page > 1:
            data["formularioDeCrud:datascrollerSuperior"] = str(page)

        return data

    async def fetch_listing_page(self, page: int) -> str:
        """Busca uma pagina da listagem via POST JSF."""
        url = f"{self.settings.licitaweb_base}/paginas/licita/PublicacaoList.seam;jsessionid={self._session.jsessionid}"
        data = self._build_listing_form(page)
        resp = await self._request("POST", url, data=data)
        html = self._decode(resp)
        self._session.update_from_html(html)
        return html

    async def reinit_session(self):
        """Re-inicializa sessao se expirar."""
        logger.warning("Re-initializing JSF session...")
        await self.init_listing_session()

    # -- Detail --------------------------------------------------------

    async def fetch_detail(self, publicacao: str) -> Optional[str]:
        """Busca pagina de detalhe. Tenta GET direto, fallback para JSF navigation."""
        # Attempt 1: Direct GET (works for DISPENSA / Cotação Eletrônica)
        url = self.settings.detail_page_url(publicacao)
        try:
            resp = await self._client.get(url, timeout=httpx.Timeout(self.settings.request_timeout, connect=30.0))
            html = self._decode(resp)
            if resp.status_code == 200 and "objetoCotacaoDecoration" in html:
                await asyncio.sleep(self.settings.delay_seconds)
                return html
        except Exception:
            pass

        # Attempt 2: JSF navigation (non-DISPENSA types that redirect to debug.seam)
        try:
            return await self._fetch_detail_via_jsf(publicacao)
        except Exception as e:
            logger.warning(f"Detail fetch failed for {publicacao}: {e}")
            return None

    def _extract_form_data(self, html: str) -> dict:
        """Serializa todos os campos do form JSF (como o A4J.AJAX.Submit faz no browser)."""
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form", id="formularioDeCrud")
        if not form:
            return {}

        data = {}
        for inp in form.find_all("input", {"type": ["hidden", "text"]}):
            name = inp.get("name", "")
            if name:
                data[name] = inp.get("value", "")
        for sel in form.find_all("select"):
            name = sel.get("name", "")
            if name:
                opt = sel.find("option", selected=True)
                data[name] = opt.get("value", "") if opt else ""
        return data

    async def _fetch_detail_via_jsf(self, publicacao: str) -> Optional[str]:
        """Busca detalhe via navegação JSF A4J: search → row click → visualizar → redirect.

        Necessário para ~17% dos registros (INEXIGIBILIDADE, ADESÃO, CHAMADA PÚBLICA, etc.)
        que retornam 302→debug.seam quando acessados via GET direto.
        """
        base = self.settings.licitaweb_base

        # Step 1: Init fresh session
        resp = await self._request("GET", self.settings.listing_url)
        html = self._decode(resp)
        jsf = JsfSession()
        jsf.update_from_html(html)

        if not jsf.viewstate:
            logger.warning(f"JSF nav: no ViewState for {publicacao}")
            return None

        action_url = f"{base}/paginas/licita/PublicacaoList.seam;jsessionid={jsf.jsessionid}"
        form_data = self._extract_form_data(html)
        form_data["AJAXREQUEST"] = "_viewRoot"

        # Step 2: A4J Search — preenche numero e clica Pesquisar
        form_data["formularioDeCrud:numeroCoepDecoration:numeroLicitacao"] = publicacao
        form_data["formularioDeCrud:pesquisar"] = "formularioDeCrud:pesquisar"

        resp = await self._request("POST", action_url, data=form_data)
        html = self._decode(resp)

        # Extract record ID from the table row that matches our publication number.
        # The A4J response contains partial HTML with <tr onclick="...pagedDataTable:{ID}:j_id430...">.
        # We parse rows and match by publication number to avoid grabbing the wrong record.
        record_id = None
        btn_id = "j_id430"
        soup = BeautifulSoup(html, "html.parser")
        for row in soup.find_all("tr"):
            onclick = row.get("onclick", "")
            m = re.search(r"pagedDataTable:(\d+):(j_id\d+)", onclick)
            if not m:
                continue
            # Verify this row contains our publication number
            row_text = row.get_text()
            if publicacao in row_text:
                record_id = m.group(1)
                btn_id = m.group(2)
                break

        # Fallback: take first match if exact text match failed (e.g. encoding differences)
        if not record_id:
            m = re.search(r"pagedDataTable:(\d+):(j_id\d+)", html)
            if m:
                record_id = m.group(1)
                btn_id = m.group(2)

        if not record_id:
            logger.debug(f"JSF nav: no record found for {publicacao}")
            return None

        # Step 3: Row click A4J
        form_data.pop("formularioDeCrud:pesquisar", None)
        click_param = f"formularioDeCrud:pagedDataTable:{record_id}:{btn_id}"
        form_data["formularioDeCrud:j_idcl"] = click_param
        form_data[click_param] = click_param

        resp = await self._request("POST", action_url, data=form_data)
        html = self._decode(resp)

        # Step 4: Visualizar A4J
        form_data.pop(click_param, None)
        form_data["formularioDeCrud:j_idcl"] = ""
        form_data["ajaxSingle"] = "formularioDeCrud:visualizarSuperior"
        form_data["formularioDeCrud:visualizarSuperior"] = "formularioDeCrud:visualizarSuperior"

        resp = await self._request("POST", action_url, data=form_data)
        html = self._decode(resp)

        # Step 5: Parse A4J redirect
        loc_match = re.search(r'name="Location"\s*content="([^"]+)"', html)
        if not loc_match:
            logger.debug(f"JSF nav: no redirect Location for {publicacao}")
            return None

        redirect_path = loc_match.group(1)
        if "error.seam" in redirect_path:
            logger.debug(f"JSF nav: redirected to error page for {publicacao}")
            return None

        redirect_url = f"https://s2gpr.sefaz.ce.gov.br{redirect_path}"
        if jsf.jsessionid and "jsessionid" not in redirect_url:
            sep = "?" if "?" in redirect_url else ""
            redirect_url = redirect_url.replace(sep, f";jsessionid={jsf.jsessionid}{sep}", 1) if sep else f"{redirect_url};jsessionid={jsf.jsessionid}"

        # Step 6: GET the detail page
        resp = await self._request("GET", redirect_url)
        detail_html = self._decode(resp)

        if "objetoCotacaoDecoration" in detail_html or "itemLicitacaoDataTable" in detail_html:
            return detail_html

        logger.debug(f"JSF nav: detail page missing expected content for {publicacao}")
        return None
