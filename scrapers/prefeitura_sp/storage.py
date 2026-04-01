"""SQLite storage para licitações da Prefeitura de SP."""

import sqlite3
from pathlib import Path


from .models import LicitacaoSP


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS licitacoes (
    numero_controle_pncp TEXT PRIMARY KEY,
    numero_compra TEXT DEFAULT '',
    sequencial_compra INTEGER DEFAULT 0,
    numero_processo TEXT DEFAULT '',
    ano_compra INTEGER DEFAULT 0,
    orgao_cnpj TEXT DEFAULT '',
    orgao_nome TEXT DEFAULT '',
    orgao_unidade TEXT DEFAULT '',
    modalidade_id INTEGER DEFAULT 0,
    modalidade TEXT DEFAULT '',
    modo_disputa TEXT DEFAULT '',
    tipo_instrumento TEXT DEFAULT '',
    amparo_legal TEXT DEFAULT '',
    objeto TEXT DEFAULT '',
    valor_estimado REAL,
    valor_homologado REAL,
    informacao_complementar TEXT DEFAULT '',
    data_publicacao TEXT DEFAULT '',
    data_abertura TEXT DEFAULT '',
    data_encerramento TEXT DEFAULT '',
    situacao TEXT DEFAULT '',
    srp INTEGER DEFAULT 0,
    link_sistema TEXT DEFAULT '',
    url_pncp TEXT DEFAULT '',
    fonte TEXT DEFAULT 'PNCP-PMSP',
    hash_registro TEXT,
    data_coleta TEXT
);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_orgao ON licitacoes(orgao_cnpj);
CREATE INDEX IF NOT EXISTS idx_modalidade ON licitacoes(modalidade_id);
CREATE INDEX IF NOT EXISTS idx_situacao ON licitacoes(situacao);
CREATE INDEX IF NOT EXISTS idx_data_pub ON licitacoes(data_publicacao);
CREATE INDEX IF NOT EXISTS idx_ano ON licitacoes(ano_compra);
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

    def upsert(self, item: LicitacaoSP) -> bool:
        """Insert ou update. Retorna True se houve mudança."""
        existing = self._conn.execute(
            "SELECT hash_registro FROM licitacoes WHERE numero_controle_pncp=?",
            (item.numero_controle_pncp,),
        ).fetchone()

        if existing and existing["hash_registro"] == item.hash_registro:
            return False

        self._conn.execute("""
            INSERT OR REPLACE INTO licitacoes (
                numero_controle_pncp, numero_compra, sequencial_compra,
                numero_processo, ano_compra,
                orgao_cnpj, orgao_nome, orgao_unidade,
                modalidade_id, modalidade, modo_disputa,
                tipo_instrumento, amparo_legal,
                objeto, valor_estimado, valor_homologado, informacao_complementar,
                data_publicacao, data_abertura, data_encerramento,
                situacao, srp, link_sistema, url_pncp,
                fonte, hash_registro, data_coleta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.numero_controle_pncp, item.numero_compra, item.sequencial_compra,
            item.numero_processo, item.ano_compra,
            item.orgao.cnpj, item.orgao.razao_social, item.orgao.unidade_nome,
            item.modalidade_id, item.modalidade, item.modo_disputa,
            item.tipo_instrumento, item.amparo_legal,
            item.objeto, item.valor_estimado, item.valor_homologado, item.informacao_complementar,
            item.data_publicacao, item.data_abertura, item.data_encerramento,
            item.situacao, int(item.srp), item.link_sistema_origem, item.url_pncp,
            item.fonte, item.hash_registro, item.data_coleta.isoformat(),
        ))
        self._conn.commit()
        return True

    def upsert_batch(self, items: list[LicitacaoSP]) -> tuple[int, int]:
        """Upsert em lote. Retorna (inseridos, atualizados)."""
        inserted = updated = 0
        for item in items:
            existing = self._conn.execute(
                "SELECT hash_registro FROM licitacoes WHERE numero_controle_pncp=?",
                (item.numero_controle_pncp,),
            ).fetchone()
            if self.upsert(item):
                if existing:
                    updated += 1
                else:
                    inserted += 1
        return inserted, updated

    def count(self, modalidade_id: int = 0) -> dict:
        if modalidade_id:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM licitacoes WHERE modalidade_id=?", (modalidade_id,)
            ).fetchone()[0]
        else:
            total = self._conn.execute("SELECT COUNT(*) FROM licitacoes").fetchone()[0]
        return {"total": total}

    def stats_by_modalidade(self) -> list[dict]:
        rows = self._conn.execute("""
            SELECT modalidade_id, modalidade, COUNT(*) as total,
                   SUM(CASE WHEN valor_estimado IS NOT NULL THEN valor_estimado ELSE 0 END) as valor_total
            FROM licitacoes GROUP BY modalidade_id ORDER BY total DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def stats_by_orgao(self) -> list[dict]:
        rows = self._conn.execute("""
            SELECT orgao_cnpj, orgao_nome, COUNT(*) as total
            FROM licitacoes GROUP BY orgao_cnpj ORDER BY total DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def stats_by_situacao(self) -> list[dict]:
        rows = self._conn.execute("""
            SELECT situacao, COUNT(*) as total
            FROM licitacoes GROUP BY situacao ORDER BY total DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def search(self, term: str, limit: int = 30) -> list[dict]:
        rows = self._conn.execute("""
            SELECT numero_controle_pncp, modalidade, orgao_nome, objeto,
                   situacao, valor_estimado, data_publicacao
            FROM licitacoes
            WHERE objeto LIKE ? OR orgao_nome LIKE ? OR numero_processo LIKE ?
            ORDER BY data_publicacao DESC LIMIT ?
        """, (f"%{term}%", f"%{term}%", f"%{term}%", limit)).fetchall()
        return [dict(r) for r in rows]

    def export_all(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM licitacoes ORDER BY data_publicacao DESC"
        ).fetchall()
        return [dict(r) for r in rows]
