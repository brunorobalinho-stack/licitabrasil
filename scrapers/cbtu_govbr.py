"""
Scraper para licitações da CBTU via portal gov.br (Plone CMS).

Estratégia: httpx + BeautifulSoup (HTML parsing).
A REST API do Plone (Accept: application/json) retorna 401 "Missing plone.restapi
permission" neste domínio, então usamos exclusivamente scraping HTML.

Navegação hierárquica:
  Hub /licitacoes/ → Unidades → Subpastas (tipo/ano) → Processos → Documentos

Uso:
  from scrapers.cbtu_govbr import CBTUGovBRScraper
  scraper = CBTUGovBRScraper()
  results = await scraper.scrape()
"""

import asyncio
import random
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from .models.cbtu import DocumentoCBTU, LicitacaoCBTU, infer_status


class CBTUGovBRScraper:
    """Scraper para licitações da CBTU via portal gov.br (Plone CMS)."""

    BASE_URL = "https://www.gov.br/cbtu/pt-br/acesso-a-informacao/receitas-e-despesas/licitacoes"

    UNIDADES = {
        "cbtu-recife": "STU Recife",
        "cbtu-joao-pessoa": "STU João Pessoa",
        "cbtu-maceio": "STU Maceió",
        "cbtu-natal": "STU Natal",
        "administracao-central": "Administração Central",
    }

    # Mapeia slug de pasta para modalidade
    MODALIDADE_MAP = {
        "pregao": "Pregão Eletrônico",
        "pregoes": "Pregão Eletrônico",
        "concorrencia": "Concorrência",
        "concorrencias": "Concorrência",
        "dispensa": "Dispensa de Licitação",
        "dispensas": "Dispensa de Licitação",
        "inexigibilidade": "Inexigibilidade",
        "credenciamento": "Credenciamento",
        "chamamento": "Chamamento Público",
        "atas": "Ata de Registro de Preços",
        "contratacao-direta": "Contratação Direta",
        "lec": "Concorrência LEI",
    }

    def __init__(
        self,
        db_path: Path = Path("./data/cbtu_govbr/cbtu_govbr.db"),
        max_concurrent: int = 3,
        delay_range: tuple[float, float] = (0.5, 1.5),
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.db_path = db_path
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._delay_range = delay_range
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            },
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    # ── HTTP com rate limiting e retry ────────────────

    async def _fetch(self, url: str) -> httpx.Response:
        """Fetch com semaphore, delay aleatório e retry com backoff."""
        async with self._semaphore:
            last_exc = None
            for attempt in range(self._max_retries):
                try:
                    resp = await self._client.get(url)
                    resp.raise_for_status()
                    delay = random.uniform(*self._delay_range)
                    await asyncio.sleep(delay)
                    return resp
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    last_exc = e
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                        raise
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self._max_retries} failed for "
                        f"{url}: {e}. Retrying in {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)
            raise last_exc

    async def _fetch_html(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch e parse HTML, retorna None em caso de erro."""
        try:
            resp = await self._fetch(url)
            return BeautifulSoup(resp.text, "lxml")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"404: {url}")
                return None
            logger.warning(f"HTTP error {e.response.status_code}: {url}")
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    # ── Parsing ───────────────────────────────────────

    def _extract_links(self, soup: BeautifulSoup, base_url: str = "") -> list[tuple[str, str]]:
        """Extrai links do #content-core. Retorna [(texto, url)]."""
        content = soup.select_one("#content-core")
        if not content:
            return []

        results = []
        for a in content.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if not text or len(text) < 3:
                continue
            # Normalizar URL
            if not href.startswith("http"):
                href = f"https://www.gov.br{href}"
            results.append((text, href))
        return results

    def _detect_modalidade(self, folder_path: str) -> str:
        """Infere modalidade pelo slug da pasta."""
        parts = folder_path.rstrip("/").split("/")
        for part in reversed(parts):
            # Remove ano (ex: pregoes-2025 → pregoes)
            slug = re.sub(r"[-_]\d{4}$", "", part).lower()
            for key, modalidade in self.MODALIDADE_MAP.items():
                if key in slug:
                    return modalidade
        return "Não identificada"

    def _extract_numero_processo(self, titulo: str) -> Optional[str]:
        """Extrai número do processo do título (ex: 'Pregão 90027/2025' → '90027/2025').

        Retorna None quando não encontra padrão reconhecível — evita poluir o DB
        com títulos completos no campo numero_processo.
        """
        # Padrões: 90027/2025, 90003-2025, 001/2025, nº 90003/2025
        match = re.search(r"n[º°]?\s*(\d[\d./-]+\d)", titulo, re.I)
        if match:
            return match.group(1)
        # Fallback: qualquer sequência numérica com / ou -
        match = re.search(r"(\d{2,5}[/.-]\d{4})", titulo)
        if match:
            return match.group(1)
        return None

    def _is_document_link(self, url: str) -> bool:
        """Verifica se o link é para um documento (não uma subpasta)."""
        lower = url.lower()
        return any(
            lower.endswith(ext)
            for ext in [
                "/view", ".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx",
                ".odt", ".ods", ".ppt", ".pptx", ".txt", ".csv",
            ]
        )

    def _is_subfolder_link(self, url: str, current_url: str) -> bool:
        """Verifica se o link é para uma subpasta (não documento)."""
        if self._is_document_link(url):
            return False
        # Deve estar sob o base URL de licitações
        return url.startswith(self.BASE_URL) and url != current_url

    # ── Scraping hierárquico ──────────────────────────

    async def scrape(
        self,
        unidades: Optional[list[str]] = None,
        max_items: int = 0,
    ) -> list[LicitacaoCBTU]:
        """Scrape todas as unidades (ou lista específica).

        max_items=0 desliga o limite. Quando > 0, o limite é propagado
        para scrape_unidade/_navigate_folder e respeitado mid-fetch.
        """
        targets = unidades or list(self.UNIDADES.keys())
        all_results: list[LicitacaoCBTU] = []

        for slug in targets:
            if slug not in self.UNIDADES:
                logger.warning(f"Unidade desconhecida: {slug}")
                continue

            remaining = max_items - len(all_results) if max_items > 0 else 0
            if max_items > 0 and remaining <= 0:
                break

            try:
                results = await self.scrape_unidade(slug, max_items=remaining)
                all_results.extend(results)
                logger.info(
                    f"{self.UNIDADES[slug]}: {len(results)} licitações encontradas"
                )
            except Exception as e:
                logger.error(f"Erro ao raspar {slug}: {e}")

            if max_items > 0 and len(all_results) >= max_items:
                all_results = all_results[:max_items]
                break

        return all_results

    async def scrape_unidade(
        self, slug: str, max_items: int = 0
    ) -> list[LicitacaoCBTU]:
        """Scrape uma unidade específica, navegando recursivamente.

        max_items > 0 interrompe a navegação assim que o limite é atingido.
        """
        unidade_nome = self.UNIDADES.get(slug, slug)
        url = f"{self.BASE_URL}/{slug}"
        logger.info(f"Raspando {unidade_nome} ({url})")

        results: list[LicitacaoCBTU] = []
        await self._navigate_folder(
            url, slug, unidade_nome, results, depth=0, max_items=max_items
        )
        return results

    async def _navigate_folder(
        self,
        url: str,
        unidade_slug: str,
        unidade_nome: str,
        results: list[LicitacaoCBTU],
        depth: int,
        max_items: int = 0,
    ):
        """Navega recursivamente uma pasta Plone coletando processos."""
        if max_items > 0 and len(results) >= max_items:
            return
        if depth > 5:
            logger.warning(f"Max depth reached: {url}")
            return

        soup = await self._fetch_html(url)
        if not soup:
            return

        links = self._extract_links(soup, url)
        if not links:
            # Pasta vazia (ex: Maceió, Natal)
            logger.debug(f"Empty folder: {url}")
            return

        # Verificar se esta página é um processo (tem documentos)
        has_documents = any(self._is_document_link(href) for _, href in links)

        if has_documents:
            # Esta é uma pasta de processo — extrair dados
            lic = self._parse_process_page(soup, url, unidade_slug, unidade_nome, links)
            if lic:
                results.append(lic)
                logger.debug(f"  [{len(results)}] {lic.numero_processo} — {lic.titulo[:60]}")
            return

        # É uma pasta intermediária — navegar subpastas
        for text, href in links:
            if max_items > 0 and len(results) >= max_items:
                return
            if self._is_subfolder_link(href, url):
                await self._navigate_folder(
                    href, unidade_slug, unidade_nome, results, depth + 1, max_items=max_items
                )

    def _parse_process_page(
        self,
        soup: BeautifulSoup,
        url: str,
        unidade_slug: str,
        unidade_nome: str,
        links: list[tuple[str, str]],
    ) -> Optional[LicitacaoCBTU]:
        """Extrai dados de uma página de processo individual."""
        # Título
        title_el = soup.select_one("h1.documentFirstHeading") or soup.select_one("h1")
        titulo = title_el.get_text(strip=True) if title_el else ""
        if not titulo:
            return None

        # Descrição (objeto)
        desc_el = soup.select_one(".documentDescription")
        descricao = desc_el.get_text(strip=True) if desc_el else titulo

        # Número do processo
        numero = self._extract_numero_processo(titulo)

        # Modalidade (inferir da URL)
        modalidade = self._detect_modalidade(url)

        # Documentos
        documentos = []
        for text, href in links:
            if self._is_document_link(href):
                doc = DocumentoCBTU.from_link(nome=text, url=href)
                documentos.append(doc)

        # Status (inferido dos documentos)
        status = infer_status(documentos)

        # Datas (metadados Plone, se disponíveis)
        data_pub = self._extract_meta_date(soup, "DC.date.created")
        data_mod = self._extract_meta_date(soup, "DC.date.modified")

        # Valor estimado (tentar extrair da descrição)
        valor = self._extract_valor(descricao)

        return LicitacaoCBTU(
            numero_processo=numero,
            modalidade=modalidade,
            titulo=descricao if descricao != titulo else titulo,
            unidade_slug=unidade_slug,
            unidade_nome=unidade_nome,
            url_processo=url,
            data_publicacao=data_pub,
            data_modificacao=data_mod,
            status=status,
            documentos=documentos,
            valor_estimado=valor,
        )

    def _extract_meta_date(self, soup: BeautifulSoup, name: str) -> Optional[datetime]:
        """Extrai data de meta tag Plone (DC.date.created, DC.date.modified)."""
        meta = soup.find("meta", attrs={"name": name})
        if meta and meta.get("content"):
            try:
                return datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        return None

    def _extract_valor(self, text: str) -> Optional[float]:
        """Tenta extrair valor estimado do texto."""
        match = re.search(
            r"R\$\s*([\d.,]+)", text.replace("\xa0", " ")
        )
        if match:
            valor_str = match.group(1).replace(".", "").replace(",", ".")
            try:
                return float(valor_str)
            except ValueError:
                pass
        return None

    # ── Storage (SQLite) ──────────────────────────────

    def _init_db(self) -> sqlite3.Connection:
        """Inicializa banco SQLite."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS licitacoes (
                numero_processo TEXT,
                modalidade TEXT NOT NULL,
                titulo TEXT,
                unidade_slug TEXT,
                unidade_nome TEXT,
                url_processo TEXT,
                data_publicacao TEXT,
                data_modificacao TEXT,
                status TEXT DEFAULT 'desconhecido',
                valor_estimado REAL,
                fonte TEXT DEFAULT 'CBTU-GOVBR',
                hash_registro TEXT,
                data_coleta TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (url_processo)
            );

            CREATE TABLE IF NOT EXISTS documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licitacao_url TEXT NOT NULL,
                nome TEXT,
                url TEXT,
                tipo TEXT DEFAULT 'outros',
                FOREIGN KEY (licitacao_url) REFERENCES licitacoes(url_processo) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_lic_numero ON licitacoes(numero_processo);
            CREATE INDEX IF NOT EXISTS idx_lic_unidade ON licitacoes(unidade_slug);
            CREATE INDEX IF NOT EXISTS idx_lic_modalidade ON licitacoes(modalidade);
            CREATE INDEX IF NOT EXISTS idx_lic_status ON licitacoes(status);
            CREATE INDEX IF NOT EXISTS idx_lic_hash ON licitacoes(hash_registro);
            CREATE INDEX IF NOT EXISTS idx_docs_lic ON documentos(licitacao_url);
        """)
        conn.commit()
        return conn

    def save(self, licitacoes: list[LicitacaoCBTU]) -> tuple[int, int, int]:
        """Salva licitações no banco. Retorna (novas, atualizadas, inalteradas)."""
        conn = self._init_db()
        new, updated, unchanged = 0, 0, 0

        try:
            for lic in licitacoes:
                existing = conn.execute(
                    "SELECT hash_registro FROM licitacoes WHERE url_processo = ?",
                    (lic.url_processo,),
                ).fetchone()

                if existing is None:
                    self._insert(conn, lic)
                    new += 1
                elif existing["hash_registro"] != lic.hash_registro:
                    self._update(conn, lic)
                    updated += 1
                else:
                    unchanged += 1

            conn.commit()
        finally:
            conn.close()

        return new, updated, unchanged

    def _insert(self, conn: sqlite3.Connection, lic: LicitacaoCBTU):
        conn.execute("""
            INSERT INTO licitacoes (numero_processo, modalidade, titulo, unidade_slug,
                unidade_nome, url_processo, data_publicacao, data_modificacao, status,
                valor_estimado, fonte, hash_registro, data_coleta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lic.numero_processo, lic.modalidade, lic.titulo,
            lic.unidade_slug, lic.unidade_nome, lic.url_processo,
            lic.data_publicacao.isoformat() if lic.data_publicacao else None,
            lic.data_modificacao.isoformat() if lic.data_modificacao else None,
            lic.status, lic.valor_estimado, lic.fonte,
            lic.hash_registro, lic.data_coleta.isoformat(),
        ))
        self._save_documents(conn, lic)

    def _update(self, conn: sqlite3.Connection, lic: LicitacaoCBTU):
        conn.execute("""
            UPDATE licitacoes SET numero_processo=?, modalidade=?, titulo=?,
                unidade_slug=?, unidade_nome=?, data_publicacao=?, data_modificacao=?,
                status=?, valor_estimado=?, hash_registro=?, data_coleta=?,
                updated_at=datetime('now')
            WHERE url_processo=?
        """, (
            lic.numero_processo, lic.modalidade, lic.titulo,
            lic.unidade_slug, lic.unidade_nome,
            lic.data_publicacao.isoformat() if lic.data_publicacao else None,
            lic.data_modificacao.isoformat() if lic.data_modificacao else None,
            lic.status, lic.valor_estimado, lic.hash_registro,
            lic.data_coleta.isoformat(), lic.url_processo,
        ))
        conn.execute("DELETE FROM documentos WHERE licitacao_url = ?", (lic.url_processo,))
        self._save_documents(conn, lic)

    def _save_documents(self, conn: sqlite3.Connection, lic: LicitacaoCBTU):
        for doc in lic.documentos:
            conn.execute("""
                INSERT INTO documentos (licitacao_url, nome, url, tipo)
                VALUES (?, ?, ?, ?)
            """, (lic.url_processo, doc.nome, doc.url, doc.tipo))

    def stats(self) -> dict:
        """Retorna estatísticas do banco."""
        if not self.db_path.exists():
            return {"total": 0}
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            total = conn.execute("SELECT COUNT(*) as c FROM licitacoes").fetchone()["c"]
            by_unidade = {
                r["unidade_nome"]: r["c"]
                for r in conn.execute(
                    "SELECT unidade_nome, COUNT(*) as c FROM licitacoes GROUP BY unidade_nome ORDER BY c DESC"
                ).fetchall()
            }
            by_modalidade = {
                r["modalidade"]: r["c"]
                for r in conn.execute(
                    "SELECT modalidade, COUNT(*) as c FROM licitacoes GROUP BY modalidade ORDER BY c DESC"
                ).fetchall()
            }
            by_status = {
                r["status"]: r["c"]
                for r in conn.execute(
                    "SELECT status, COUNT(*) as c FROM licitacoes GROUP BY status ORDER BY c DESC"
                ).fetchall()
            }
            n_docs = conn.execute("SELECT COUNT(*) as c FROM documentos").fetchone()["c"]
            return {
                "total": total,
                "documentos": n_docs,
                "by_unidade": by_unidade,
                "by_modalidade": by_modalidade,
                "by_status": by_status,
            }
        finally:
            conn.close()

    def search(self, keyword: str) -> list[dict]:
        """Busca local no banco."""
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            pattern = f"%{keyword}%"
            rows = conn.execute("""
                SELECT numero_processo, modalidade, titulo, unidade_nome, status, url_processo
                FROM licitacoes
                WHERE titulo LIKE ? OR numero_processo LIKE ? OR unidade_nome LIKE ?
                ORDER BY data_coleta DESC
            """, (pattern, pattern, pattern)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
