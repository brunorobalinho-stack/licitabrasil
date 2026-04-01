"""
Scraper para licitacoes da JFPE (Justica Federal de Pernambuco).

A pagina HTML em jfpe.jus.br usa DataTables com server-side processing,
chamando a API REST em apisapi.jfpe.jus.br/api/SCPA/. Usamos httpx direto
na API JSON — sem necessidade de Playwright ou BS4.

Endpoints:
  - ListarLicitacoes     : listagem paginada (DataTables params)
  - ListarEmpenhos       : empenhos por idLicitacao
  - ListarContratosLicitacao : contratos por idLicitacao
  - ListarAtaRegistroLicitacao : atas por idLicitacao

Uso:
  from scrapers.jfpe_licitacoes import JFPEScraper
  scraper = JFPEScraper()
  results = await scraper.scrape()
"""

import asyncio
import hashlib
import random
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger
from pydantic import BaseModel, Field, computed_field


# ── Modelos ───────────────────────────────────────────

MODALIDADE_MAP = {
    1: "Pregao Eletronico",
    2: "Convite",
    3: "Tomada de Precos",
    4: "Concorrencia",
    5: "Dispensa de Licitacao",
    6: "Inexigibilidade",
}


def extract_modalidade_from_desc(descricao: str) -> Optional[str]:
    """Extrai modalidade do HTML da descricao (ex: '<span>PREGAO ELETRONICO</span> - ...')."""
    clean = re.sub(r"<[^>]+>", "", descricao).strip()
    match = re.match(r"^([A-Z\s\u00C0-\u00FF]+)\s*[-\u2013]", clean)
    if match:
        return match.group(1).strip().title()
    return None


def extract_objeto(descricao: str) -> str:
    """Remove a modalidade do inicio da descricao para obter o objeto."""
    clean = re.sub(r"<[^>]+>", "", descricao).strip()
    # Remove "PREGAO ELETRONICO - " ou similar do inicio
    obj = re.sub(r"^[A-Z\s\u00C0-\u00FF]+\s*[-\u2013]\s*", "", clean, count=1)
    return obj.strip() or clean


class ArquivoJFPE(BaseModel):
    id_arquivo: int
    nome: str
    tipo_arquivo: Optional[str] = "application/pdf"
    categoria: str = "edital"  # edital, empenho, contrato, ata

    @property
    def url_download(self) -> str:
        endpoint_map = {
            "edital": "GetLicitacaoFile?idLicitacaoArquivo=",
            "empenho": "GetEmpenhoFile?idEmpenho=",
            "contrato": "GetContratoFile?idContrato=",
            "ata": "GetAtaRegistroFile?idAta=",
        }
        base = "https://apisapi.jfpe.jus.br/api/SCPA/"
        ep = endpoint_map.get(self.categoria, endpoint_map["edital"])
        return f"{base}{ep}{self.id_arquivo}"


class LicitacaoJFPE(BaseModel):
    id_licitacao: int
    numero: str
    modalidade: str
    modalidade_codigo: int
    objeto: str
    data_abertura: Optional[datetime] = None
    hora: Optional[str] = None
    e_pregao: bool = False
    tem_registro_preco: bool = False
    qtd_empenhos: int = 0
    qtd_contratos: int = 0
    qtd_atas: int = 0
    arquivos: list[ArquivoJFPE] = Field(default_factory=list)
    fonte: str = "JFPE"
    data_coleta: datetime = Field(default_factory=datetime.now)

    @computed_field
    @property
    def hash_registro(self) -> str:
        content = (
            f"{self.id_licitacao}|{self.numero}|{self.modalidade}|"
            f"{self.qtd_empenhos}|{self.qtd_contratos}|{self.qtd_atas}|"
            f"{len(self.arquivos)}"
        )
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:16]


# ── Scraper ───────────────────────────────────────────


class JFPEScraper:
    """Scraper para licitacoes da JFPE via API SCPA."""

    API_BASE = "https://apisapi.jfpe.jus.br/api/SCPA"

    def __init__(
        self,
        db_path: Path = Path("./data/jfpe/jfpe.db"),
        page_size: int = 50,
        max_concurrent: int = 3,
        delay_range: tuple[float, float] = (0.3, 1.0),
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.db_path = db_path
        self._page_size = page_size
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._delay_range = delay_range
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.jfpe.jus.br/",
            },
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    # ── HTTP ──────────────────────────────────────────

    async def _fetch_json(self, url: str, params: Optional[dict] = None) -> Optional[dict]:
        """GET com rate limiting, retry e backoff."""
        async with self._semaphore:
            last_exc = None
            for attempt in range(self._max_retries):
                try:
                    resp = await self._client.get(url, params=params)
                    resp.raise_for_status()
                    delay = random.uniform(*self._delay_range)
                    await asyncio.sleep(delay)
                    return resp.json()
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    last_exc = e
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self._max_retries} failed for "
                        f"{url}: {e}. Retrying in {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)
            logger.error(f"All retries exhausted for {url}: {last_exc}")
            return None

    # ── Parsing ───────────────────────────────────────

    def _parse_licitacao(self, item: dict) -> LicitacaoJFPE:
        """Converte item da API para modelo Pydantic."""
        descricao = item.get("descricao", "")
        cod_modalidade = item.get("modalidadeLicitacao", 0)

        # Modalidade: primeiro tenta extrair do HTML da descricao, depois do codigo
        modalidade = extract_modalidade_from_desc(descricao) or MODALIDADE_MAP.get(
            cod_modalidade, f"Modalidade {cod_modalidade}"
        )

        # Data de abertura
        data_abertura = None
        dt_str = item.get("dataHoraLicitacao")
        if dt_str:
            try:
                data_abertura = datetime.fromisoformat(dt_str)
            except (ValueError, TypeError):
                pass

        # Arquivos do edital
        arquivos = []
        for arq in item.get("arquivosEdital", []):
            arquivos.append(ArquivoJFPE(
                id_arquivo=arq["idArquivo"],
                nome=arq.get("nomeArquivo", ""),
                tipo_arquivo=arq.get("tipoArquivo", "application/pdf"),
                categoria="edital",
            ))

        return LicitacaoJFPE(
            id_licitacao=item["idLicitacao"],
            numero=item.get("numero", ""),
            modalidade=modalidade,
            modalidade_codigo=cod_modalidade,
            objeto=extract_objeto(descricao),
            data_abertura=data_abertura,
            hora=item.get("hora"),
            e_pregao=item.get("ePregao", False),
            tem_registro_preco=item.get("temRegistroPreco", False),
            qtd_empenhos=item.get("quantidadeEmpenhos", 0),
            qtd_contratos=item.get("quantidadeContratos", 0),
            qtd_atas=item.get("quantidadeAtaRegistroPreco", 0),
            arquivos=arquivos,
        )

    # ── Scraping ──────────────────────────────────────

    async def scrape(self, max_items: int = 0) -> list[LicitacaoJFPE]:
        """Coleta todas as licitacoes paginando pela API."""
        url = f"{self.API_BASE}/ListarLicitacoes"
        all_results = []
        start = 0
        draw = 1
        total = None

        while True:
            data = await self._fetch_json(url, params={
                "draw": draw,
                "start": start,
                "length": self._page_size,
            })
            if not data:
                break

            if total is None:
                total = data.get("recordsTotal", 0)
                logger.info(f"Total de licitacoes na API: {total}")

            items = data.get("data", [])
            if not items:
                break

            for item in items:
                try:
                    lic = self._parse_licitacao(item)
                    all_results.append(lic)
                except Exception as e:
                    logger.warning(f"Erro parsing licitacao {item.get('idLicitacao')}: {e}")

            logger.debug(f"Pagina {draw}: {len(items)} itens (total coletado: {len(all_results)})")

            if max_items > 0 and len(all_results) >= max_items:
                all_results = all_results[:max_items]
                break

            start += self._page_size
            draw += 1

            if start >= (total or 0):
                break

        logger.info(f"Coletadas {len(all_results)} licitacoes")
        return all_results

    async def enrich_licitacao(self, lic: LicitacaoJFPE) -> LicitacaoJFPE:
        """Busca documentos adicionais (empenhos, contratos, atas) para uma licitacao."""
        tasks = []
        if lic.qtd_empenhos > 0:
            tasks.append(("empenho", self._fetch_related(
                f"{self.API_BASE}/ListarEmpenhos",
                {"idLicitacao": lic.id_licitacao},
            )))
        if lic.qtd_contratos > 0:
            tasks.append(("contrato", self._fetch_related(
                f"{self.API_BASE}/ListarContratosLicitacao",
                {"idLicitacao": lic.id_licitacao},
            )))
        if lic.qtd_atas > 0:
            tasks.append(("ata", self._fetch_related(
                f"{self.API_BASE}/ListarAtaRegistroLicitacao",
                {"idLicitacao": lic.id_licitacao},
            )))

        if not tasks:
            return lic

        categorias = [t[0] for t in tasks]
        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

        for cat, result in zip(categorias, results):
            if isinstance(result, Exception):
                logger.warning(f"Erro buscando {cat} para {lic.numero}: {result}")
                continue
            if not result:
                continue
            for item in result:
                id_key = self._get_id_key(cat, item)
                if id_key is not None:
                    lic.arquivos.append(ArquivoJFPE(
                        id_arquivo=id_key,
                        nome=item.get("nomeArquivo", item.get("numero", f"{cat}")),
                        tipo_arquivo=item.get("tipoArquivo", "application/pdf"),
                        categoria=cat,
                    ))

        return lic

    def _get_id_key(self, categoria: str, item: dict) -> Optional[int]:
        """Extrai o ID relevante do item conforme a categoria."""
        key_map = {
            "empenho": "idEmpenho",
            "contrato": "idContrato",
            "ata": "idAta",
        }
        return item.get(key_map.get(categoria))

    async def _fetch_related(self, url: str, params: dict) -> list[dict]:
        """Busca lista de itens relacionados."""
        data = await self._fetch_json(url, params=params)
        if data is None:
            return []
        # A API pode retornar lista direta ou objeto com data
        if isinstance(data, list):
            return data
        return data.get("data", data.get("items", []))

    # ── Storage (SQLite) ──────────────────────────────

    def _init_db(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS licitacoes (
                id_licitacao INTEGER PRIMARY KEY,
                numero TEXT NOT NULL,
                modalidade TEXT,
                modalidade_codigo INTEGER,
                objeto TEXT,
                data_abertura TEXT,
                hora TEXT,
                e_pregao INTEGER DEFAULT 0,
                tem_registro_preco INTEGER DEFAULT 0,
                qtd_empenhos INTEGER DEFAULT 0,
                qtd_contratos INTEGER DEFAULT 0,
                qtd_atas INTEGER DEFAULT 0,
                fonte TEXT DEFAULT 'JFPE',
                hash_registro TEXT,
                data_coleta TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS arquivos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licitacao_id INTEGER NOT NULL,
                id_arquivo INTEGER,
                nome TEXT,
                tipo_arquivo TEXT,
                categoria TEXT DEFAULT 'edital',
                FOREIGN KEY (licitacao_id) REFERENCES licitacoes(id_licitacao) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_lic_numero ON licitacoes(numero);
            CREATE INDEX IF NOT EXISTS idx_lic_modalidade ON licitacoes(modalidade);
            CREATE INDEX IF NOT EXISTS idx_lic_hash ON licitacoes(hash_registro);
            CREATE INDEX IF NOT EXISTS idx_arq_lic ON arquivos(licitacao_id);
        """)
        conn.commit()
        return conn

    def save(self, licitacoes: list[LicitacaoJFPE]) -> tuple[int, int, int]:
        """Salva licitacoes. Retorna (novas, atualizadas, inalteradas)."""
        conn = self._init_db()
        new, updated, unchanged = 0, 0, 0

        try:
            for lic in licitacoes:
                existing = conn.execute(
                    "SELECT hash_registro FROM licitacoes WHERE id_licitacao = ?",
                    (lic.id_licitacao,),
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

    def _insert(self, conn: sqlite3.Connection, lic: LicitacaoJFPE):
        conn.execute("""
            INSERT INTO licitacoes (id_licitacao, numero, modalidade, modalidade_codigo,
                objeto, data_abertura, hora, e_pregao, tem_registro_preco,
                qtd_empenhos, qtd_contratos, qtd_atas, fonte, hash_registro, data_coleta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lic.id_licitacao, lic.numero, lic.modalidade, lic.modalidade_codigo,
            lic.objeto,
            lic.data_abertura.isoformat() if lic.data_abertura else None,
            lic.hora, int(lic.e_pregao), int(lic.tem_registro_preco),
            lic.qtd_empenhos, lic.qtd_contratos, lic.qtd_atas,
            lic.fonte, lic.hash_registro, lic.data_coleta.isoformat(),
        ))
        self._save_arquivos(conn, lic)

    def _update(self, conn: sqlite3.Connection, lic: LicitacaoJFPE):
        conn.execute("""
            UPDATE licitacoes SET numero=?, modalidade=?, modalidade_codigo=?,
                objeto=?, data_abertura=?, hora=?, e_pregao=?, tem_registro_preco=?,
                qtd_empenhos=?, qtd_contratos=?, qtd_atas=?,
                hash_registro=?, data_coleta=?, updated_at=datetime('now')
            WHERE id_licitacao=?
        """, (
            lic.numero, lic.modalidade, lic.modalidade_codigo,
            lic.objeto,
            lic.data_abertura.isoformat() if lic.data_abertura else None,
            lic.hora, int(lic.e_pregao), int(lic.tem_registro_preco),
            lic.qtd_empenhos, lic.qtd_contratos, lic.qtd_atas,
            lic.hash_registro, lic.data_coleta.isoformat(),
            lic.id_licitacao,
        ))
        conn.execute("DELETE FROM arquivos WHERE licitacao_id = ?", (lic.id_licitacao,))
        self._save_arquivos(conn, lic)

    def _save_arquivos(self, conn: sqlite3.Connection, lic: LicitacaoJFPE):
        for arq in lic.arquivos:
            conn.execute("""
                INSERT INTO arquivos (licitacao_id, id_arquivo, nome, tipo_arquivo, categoria)
                VALUES (?, ?, ?, ?, ?)
            """, (lic.id_licitacao, arq.id_arquivo, arq.nome, arq.tipo_arquivo, arq.categoria))

    def stats(self) -> dict:
        """Estatisticas do banco."""
        if not self.db_path.exists():
            return {"total": 0}
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            total = conn.execute("SELECT COUNT(*) as c FROM licitacoes").fetchone()["c"]
            by_modalidade = {
                r["modalidade"]: r["c"]
                for r in conn.execute(
                    "SELECT modalidade, COUNT(*) as c FROM licitacoes GROUP BY modalidade ORDER BY c DESC"
                ).fetchall()
            }
            by_ano = {
                str(r["ano"]): r["c"]
                for r in conn.execute("""
                    SELECT CAST(substr(numero, -4) AS INTEGER) as ano, COUNT(*) as c
                    FROM licitacoes
                    GROUP BY ano ORDER BY ano DESC
                """).fetchall()
            }
            n_arquivos = conn.execute("SELECT COUNT(*) as c FROM arquivos").fetchone()["c"]
            by_categoria = {
                r["categoria"]: r["c"]
                for r in conn.execute(
                    "SELECT categoria, COUNT(*) as c FROM arquivos GROUP BY categoria ORDER BY c DESC"
                ).fetchall()
            }
            return {
                "total": total,
                "arquivos": n_arquivos,
                "by_modalidade": by_modalidade,
                "by_ano": by_ano,
                "by_categoria": by_categoria,
            }
        finally:
            conn.close()

    def search(self, keyword: str) -> list[dict]:
        """Busca local."""
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            pattern = f"%{keyword}%"
            rows = conn.execute("""
                SELECT id_licitacao, numero, modalidade, objeto, data_abertura, hora
                FROM licitacoes
                WHERE objeto LIKE ? OR numero LIKE ? OR modalidade LIKE ?
                ORDER BY data_abertura DESC
                LIMIT 50
            """, (pattern, pattern, pattern)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
