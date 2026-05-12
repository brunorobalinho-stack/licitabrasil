"""Persistência SQLite do scraper FIEMG."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import Licitacao


SCHEMA = """
CREATE TABLE IF NOT EXISTS licitacoes (
    sde TEXT PRIMARY KEY,
    ano INTEGER,
    sequencia TEXT,
    objeto TEXT,
    objeto_resumido TEXT,
    categoria TEXT,
    valor_estimado REAL,
    valor_referencia REAL,
    data_publicacao TEXT,
    data_abertura_propostas TEXT,
    data_encerramento_propostas TEXT,
    data_sessao_publica TEXT,
    fase TEXT,
    situacao TEXT,
    unidade_compradora TEXT,
    cidade_entrega TEXT,
    url_processo TEXT,
    url_edital TEXT,
    urls_anexos_json TEXT,
    motivo_justificativa TEXT,
    hash_registro TEXT,
    data_coleta TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fiemg_ano ON licitacoes(ano);
CREATE INDEX IF NOT EXISTS idx_fiemg_fase ON licitacoes(fase);
CREATE INDEX IF NOT EXISTS idx_fiemg_hash ON licitacoes(hash_registro);
CREATE INDEX IF NOT EXISTS idx_fiemg_enc ON licitacoes(data_encerramento_propostas);
"""


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def upsert(self, lic: Licitacao) -> str:
        existing = self._conn.execute(
            "SELECT hash_registro FROM licitacoes WHERE sde = ?", (lic.sde,)
        ).fetchone()
        row = self._row(lic)
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
            """SELECT sde, objeto, fase, unidade_compradora, data_encerramento_propostas
               FROM licitacoes ORDER BY datetime(data_coleta) DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def open_now(self) -> list[dict]:
        """Lista processos cuja fase ainda permite proposta."""
        rows = self._conn.execute(
            """SELECT sde, objeto, fase, unidade_compradora, data_encerramento_propostas
               FROM licitacoes
               WHERE fase IN ('Envio de Propostas', 'Cadastro')
                  OR data_encerramento_propostas >= datetime('now')
               ORDER BY datetime(data_encerramento_propostas) ASC"""
        ).fetchall()
        return [dict(r) for r in rows]

    # ── internals ──

    @staticmethod
    def _iso(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    def _row(self, lic: Licitacao) -> dict:
        return {
            "sde": lic.sde,
            "ano": lic.ano,
            "sequencia": lic.sequencia,
            "objeto": lic.objeto,
            "objeto_resumido": lic.objeto_resumido,
            "categoria": lic.categoria,
            "valor_estimado": lic.valor_estimado,
            "valor_referencia": lic.valor_referencia,
            "data_publicacao": self._iso(lic.data_publicacao),
            "data_abertura_propostas": self._iso(lic.data_abertura_propostas),
            "data_encerramento_propostas": self._iso(lic.data_encerramento_propostas),
            "data_sessao_publica": self._iso(lic.data_sessao_publica),
            "fase": lic.fase,
            "situacao": lic.situacao,
            "unidade_compradora": lic.unidade_compradora,
            "cidade_entrega": lic.cidade_entrega,
            "url_processo": lic.url_processo,
            "url_edital": lic.url_edital,
            "urls_anexos_json": json.dumps(lic.urls_anexos, ensure_ascii=False),
            "motivo_justificativa": lic.motivo_justificativa,
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
        set_clause = ",".join(f"{k}=:{k}" for k in row.keys() if k != "sde")
        self._conn.execute(
            f"UPDATE licitacoes SET {set_clause}, updated_at=datetime('now') WHERE sde=:sde",
            row,
        )
