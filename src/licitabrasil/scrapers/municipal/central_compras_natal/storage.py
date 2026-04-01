"""SQLite storage para licitacoes de Natal/RN."""

import json
import sqlite3
from pathlib import Path


from .models import LicitacaoNatal


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS licitacoes (
    numero_licitacao TEXT NOT NULL,
    modalidade_slug TEXT NOT NULL,
    record_id INTEGER NOT NULL DEFAULT 0,
    numero_processo TEXT DEFAULT '',
    modalidade TEXT DEFAULT '',
    tipo_licitacao TEXT DEFAULT '',
    orgao TEXT DEFAULT '',
    titulo TEXT DEFAULT '',
    objeto TEXT DEFAULT '',
    data_publicacao TEXT,
    data_abertura TEXT,
    local_abertura TEXT,
    registro_preco TEXT,
    status TEXT DEFAULT '',
    documentos TEXT DEFAULT '[]',
    historico TEXT DEFAULT '[]',
    licitantes TEXT DEFAULT '[]',
    url_detalhe TEXT,
    hash_registro TEXT,
    tem_detalhe INTEGER DEFAULT 0,
    data_coleta TEXT,
    PRIMARY KEY (numero_licitacao, modalidade_slug)
);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_modalidade ON licitacoes(modalidade_slug);
CREATE INDEX IF NOT EXISTS idx_record_id ON licitacoes(record_id);
CREATE INDEX IF NOT EXISTS idx_status ON licitacoes(status);
CREATE INDEX IF NOT EXISTS idx_data ON licitacoes(data_publicacao);
"""


class Storage:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(CREATE_TABLE + CREATE_INDEX)

    def close(self):
        self._conn.close()

    def upsert(self, item: LicitacaoNatal) -> bool:
        """Insert ou update. Retorna True se houve mudanca."""
        existing = self._conn.execute(
            "SELECT hash_registro, tem_detalhe FROM licitacoes WHERE numero_licitacao=? AND modalidade_slug=?",
            (item.numero_licitacao, item.modalidade_slug),
        ).fetchone()

        if existing and existing["hash_registro"] == item.hash_registro:
            return False

        # Merge: preserve detail data if existing has it and new doesn't
        if existing and existing["tem_detalhe"] and not item.tem_detalhe:
            return False

        self._conn.execute("""
            INSERT OR REPLACE INTO licitacoes (
                numero_licitacao, modalidade_slug, record_id,
                numero_processo, modalidade, tipo_licitacao,
                orgao, titulo, objeto,
                data_publicacao, data_abertura, local_abertura, registro_preco,
                status, documentos, historico, licitantes,
                url_detalhe, hash_registro, tem_detalhe, data_coleta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.numero_licitacao, item.modalidade_slug, item.record_id,
            item.numero_processo, item.modalidade, item.tipo_licitacao,
            item.orgao, item.titulo, item.objeto,
            item.data_publicacao, item.data_abertura, item.local_abertura, item.registro_preco,
            item.status,
            json.dumps([d.model_dump() for d in item.documentos], ensure_ascii=False),
            json.dumps([h.model_dump() for h in item.historico], ensure_ascii=False),
            json.dumps([lic.model_dump() for lic in item.licitantes], ensure_ascii=False),
            item.url_detalhe, item.hash_registro, int(item.tem_detalhe),
            item.data_coleta.isoformat(),
        ))
        self._conn.commit()
        return True

    def upsert_batch(self, items: list[LicitacaoNatal]) -> tuple[int, int]:
        """Upsert em lote. Retorna (inseridos, atualizados)."""
        inserted = updated = 0
        for item in items:
            existing = self._conn.execute(
                "SELECT hash_registro FROM licitacoes WHERE numero_licitacao=? AND modalidade_slug=?",
                (item.numero_licitacao, item.modalidade_slug),
            ).fetchone()
            if self.upsert(item):
                if existing:
                    updated += 1
                else:
                    inserted += 1
        return inserted, updated

    def get_without_detail(self, modalidade_slug: str = "") -> list[dict]:
        """Retorna registros sem detalhe para enriquecimento."""
        cols = "numero_licitacao, modalidade_slug, modalidade, record_id, numero_processo, tipo_licitacao, orgao, objeto, data_publicacao"
        if modalidade_slug:
            rows = self._conn.execute(
                f"SELECT {cols} FROM licitacoes WHERE tem_detalhe=0 AND modalidade_slug=?",
                (modalidade_slug,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                f"SELECT {cols} FROM licitacoes WHERE tem_detalhe=0"
            ).fetchall()
        return [dict(r) for r in rows]

    def count(self, modalidade_slug: str = "") -> dict:
        """Retorna contagens."""
        if modalidade_slug:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM licitacoes WHERE modalidade_slug=?", (modalidade_slug,)
            ).fetchone()[0]
            with_detail = self._conn.execute(
                "SELECT COUNT(*) FROM licitacoes WHERE tem_detalhe=1 AND modalidade_slug=?", (modalidade_slug,)
            ).fetchone()[0]
        else:
            total = self._conn.execute("SELECT COUNT(*) FROM licitacoes").fetchone()[0]
            with_detail = self._conn.execute("SELECT COUNT(*) FROM licitacoes WHERE tem_detalhe=1").fetchone()[0]
        return {"total": total, "com_detalhe": with_detail, "sem_detalhe": total - with_detail}

    def stats_by_modalidade(self) -> list[dict]:
        """Retorna contagens por modalidade."""
        rows = self._conn.execute("""
            SELECT modalidade_slug, modalidade, COUNT(*) as total,
                   SUM(CASE WHEN tem_detalhe=1 THEN 1 ELSE 0 END) as com_detalhe
            FROM licitacoes GROUP BY modalidade_slug ORDER BY total DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def search(self, term: str, limit: int = 20) -> list[dict]:
        """Busca por termo no objeto, orgao ou numero."""
        rows = self._conn.execute("""
            SELECT numero_licitacao, modalidade, orgao, objeto, status, data_publicacao
            FROM licitacoes
            WHERE objeto LIKE ? OR orgao LIKE ? OR numero_licitacao LIKE ?
            ORDER BY data_publicacao DESC LIMIT ?
        """, (f"%{term}%", f"%{term}%", f"%{term}%", limit)).fetchall()
        return [dict(r) for r in rows]

    def export_all(self) -> list[dict]:
        """Exporta todos os registros."""
        rows = self._conn.execute("SELECT * FROM licitacoes ORDER BY data_publicacao DESC").fetchall()
        return [dict(r) for r in rows]
