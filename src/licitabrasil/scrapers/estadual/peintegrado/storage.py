"""Persistência SQLite do scraper PE-Integrado."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import Licitacao


SCHEMA = """
CREATE TABLE IF NOT EXISTS licitacoes (
    numero TEXT PRIMARY KEY,
    ano INTEGER,
    sequencia TEXT,
    tipo TEXT,
    sub_modalidade TEXT,
    modalidade TEXT,
    orgao_sigla TEXT,
    orgao_nome TEXT,
    objeto TEXT,
    objeto_resumido TEXT,
    valor_estimado REAL,
    valor_referencia REAL,
    data_publicacao TEXT,
    data_abertura_propostas TEXT,
    data_encerramento_propostas TEXT,
    data_sessao_publica TEXT,
    situacao TEXT,
    fase TEXT,
    url_processo TEXT,
    url_edital TEXT,
    urls_anexos_json TEXT,
    cnpj_empresa_vencedora TEXT,
    razao_social_vencedora TEXT,
    hash_registro TEXT,
    data_coleta TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_lic_ano ON licitacoes(ano);
CREATE INDEX IF NOT EXISTS idx_lic_modalidade ON licitacoes(modalidade);
CREATE INDEX IF NOT EXISTS idx_lic_situacao ON licitacoes(situacao);
CREATE INDEX IF NOT EXISTS idx_lic_orgao ON licitacoes(orgao_sigla);
CREATE INDEX IF NOT EXISTS idx_lic_hash ON licitacoes(hash_registro);
CREATE INDEX IF NOT EXISTS idx_lic_data_pub ON licitacoes(data_publicacao);
"""


class Database:
    """Wrapper SQLite com upsert por hash_registro."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── ops ────────────────────────────────────────────────────────

    def upsert(self, lic: Licitacao) -> str:
        """Insere ou atualiza uma licitação. Retorna 'new' | 'updated' | 'unchanged'."""
        existing = self._conn.execute(
            "SELECT hash_registro FROM licitacoes WHERE numero = ?",
            (lic.numero,),
        ).fetchone()

        row = self._row_from_lic(lic)

        if existing is None:
            self._insert(row)
            return "new"
        if existing["hash_registro"] != lic.hash_registro:
            self._update(row)
            return "updated"
        return "unchanged"

    def upsert_many(self, licitacoes: Iterable[Licitacao]) -> dict[str, int]:
        counts = {"new": 0, "updated": 0, "unchanged": 0}
        for lic in licitacoes:
            counts[self.upsert(lic)] += 1
        self._conn.commit()
        return counts

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM licitacoes").fetchone()[0]

    def latest(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT numero, modalidade, orgao_sigla, objeto, situacao, data_publicacao
            FROM licitacoes
            ORDER BY datetime(data_coleta) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def search(self, keyword: str) -> list[dict]:
        pattern = f"%{keyword.lower()}%"
        rows = self._conn.execute(
            """
            SELECT numero, modalidade, orgao_sigla, objeto, situacao
            FROM licitacoes
            WHERE LOWER(objeto) LIKE ?
               OR LOWER(orgao_sigla) LIKE ?
               OR LOWER(numero) LIKE ?
            ORDER BY datetime(data_publicacao) DESC NULLS LAST
            LIMIT 200
            """,
            (pattern, pattern, pattern),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── internals ─────────────────────────────────────────────────

    @staticmethod
    def _iso(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    def _row_from_lic(self, lic: Licitacao) -> dict:
        return {
            "numero": lic.numero,
            "ano": lic.ano,
            "sequencia": lic.sequencia,
            "tipo": lic.tipo,
            "sub_modalidade": lic.sub_modalidade,
            "modalidade": lic.modalidade,
            "orgao_sigla": lic.orgao.sigla if lic.orgao else "",
            "orgao_nome": lic.orgao.nome if lic.orgao else "",
            "objeto": lic.objeto,
            "objeto_resumido": lic.objeto_resumido,
            "valor_estimado": lic.valor_estimado,
            "valor_referencia": lic.valor_referencia,
            "data_publicacao": self._iso(lic.data_publicacao),
            "data_abertura_propostas": self._iso(lic.data_abertura_propostas),
            "data_encerramento_propostas": self._iso(lic.data_encerramento_propostas),
            "data_sessao_publica": self._iso(lic.data_sessao_publica),
            "situacao": lic.situacao,
            "fase": lic.fase,
            "url_processo": lic.url_processo,
            "url_edital": lic.url_edital,
            "urls_anexos_json": json.dumps(lic.urls_anexos, ensure_ascii=False),
            "cnpj_empresa_vencedora": lic.cnpj_empresa_vencedora,
            "razao_social_vencedora": lic.razao_social_vencedora,
            "hash_registro": lic.hash_registro,
            "data_coleta": self._iso(lic.data_coleta),
        }

    def _insert(self, row: dict) -> None:
        cols = ",".join(row.keys())
        placeholders = ",".join(f":{k}" for k in row.keys())
        self._conn.execute(
            f"INSERT INTO licitacoes ({cols}) VALUES ({placeholders})", row
        )

    def _update(self, row: dict) -> None:
        set_clause = ",".join(f"{k}=:{k}" for k in row.keys() if k != "numero")
        self._conn.execute(
            f"UPDATE licitacoes SET {set_clause}, updated_at=datetime('now') WHERE numero=:numero",
            row,
        )
