"""SQLite storage com checkpoint/resume para 340K+ registros."""

import json
import sqlite3
from pathlib import Path
from typing import Optional


from .models import LicitacaoCE


SCHEMA = """
CREATE TABLE IF NOT EXISTS licitacoes (
    numero_publicacao TEXT PRIMARY KEY,
    numero_processo TEXT DEFAULT '',
    numero_edital TEXT DEFAULT '',
    viproc TEXT,
    id_pncp TEXT,
    orgao TEXT DEFAULT '',
    gestor_compras TEXT,
    objeto TEXT DEFAULT '',
    sistematica TEXT DEFAULT '',
    forma_aquisicao TEXT DEFAULT '',
    natureza_aquisicao TEXT,
    tipo_aquisicao TEXT,
    moeda TEXT,
    data_acolhimento TEXT,
    data_abertura TEXT,
    status TEXT DEFAULT '',
    vencedor TEXT,
    valor_lance TEXT,
    documentos TEXT DEFAULT '[]',
    fonte TEXT DEFAULT 'licitaweb_ce',
    url_detalhe TEXT,
    tem_detalhe INTEGER DEFAULT 0,
    hash_registro TEXT NOT NULL,
    data_coleta TEXT NOT NULL,
    ano INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scrape_progress (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_page INTEGER DEFAULT 0,
    total_pages INTEGER DEFAULT 0,
    total_records INTEGER DEFAULT 0,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lic_status ON licitacoes(status);
CREATE INDEX IF NOT EXISTS idx_lic_orgao ON licitacoes(orgao);
CREATE INDEX IF NOT EXISTS idx_lic_sistematica ON licitacoes(sistematica);
CREATE INDEX IF NOT EXISTS idx_lic_ano ON licitacoes(ano);
CREATE INDEX IF NOT EXISTS idx_lic_hash ON licitacoes(hash_registro);
CREATE INDEX IF NOT EXISTS idx_lic_detalhe ON licitacoes(tem_detalhe);
"""


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # -- Upsert --------------------------------------------------------

    def upsert(self, lic: LicitacaoCE) -> tuple[bool, bool]:
        """Insere ou atualiza. Retorna (is_new, is_updated)."""
        existing = self.conn.execute(
            "SELECT hash_registro, tem_detalhe FROM licitacoes WHERE numero_publicacao = ?",
            (lic.numero_publicacao,),
        ).fetchone()

        if existing is None:
            self._insert(lic)
            return (True, False)

        # Don't overwrite detail data with listing data
        if existing["tem_detalhe"] and not lic.tem_detalhe:
            if existing["hash_registro"] == lic.hash_registro:
                return (False, False)
            # Update only listing-level fields
            self._update_listing_fields(lic)
            return (False, True)

        if existing["hash_registro"] != lic.hash_registro or (lic.tem_detalhe and not existing["tem_detalhe"]):
            # When enriching from detail, preserve listing-only fields
            if lic.tem_detalhe and not existing["tem_detalhe"]:
                self._merge_update(lic)
            else:
                self._update(lic)
            return (False, True)

        return (False, False)

    def _insert(self, lic: LicitacaoCE):
        self.conn.execute("""
            INSERT INTO licitacoes (numero_publicacao, numero_processo, numero_edital, viproc,
                id_pncp, orgao, gestor_compras, objeto, sistematica, forma_aquisicao,
                natureza_aquisicao, tipo_aquisicao, moeda, data_acolhimento, data_abertura,
                status, vencedor, valor_lance, documentos, fonte, url_detalhe, tem_detalhe,
                hash_registro, data_coleta, ano)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, self._to_row(lic))
        self.conn.commit()

    def _update(self, lic: LicitacaoCE):
        self.conn.execute("""
            UPDATE licitacoes SET numero_processo=?, numero_edital=?, viproc=?,
                id_pncp=?, orgao=?, gestor_compras=?, objeto=?, sistematica=?, forma_aquisicao=?,
                natureza_aquisicao=?, tipo_aquisicao=?, moeda=?, data_acolhimento=?, data_abertura=?,
                status=?, vencedor=?, valor_lance=?, documentos=?, fonte=?, url_detalhe=?, tem_detalhe=?,
                hash_registro=?, data_coleta=?, ano=?, updated_at=CURRENT_TIMESTAMP
            WHERE numero_publicacao=?
        """, self._to_row(lic)[1:] + (lic.numero_publicacao,))
        self.conn.commit()

    def _merge_update(self, lic: LicitacaoCE):
        """Update with detail data but preserve listing-only fields if detail provides empty values."""
        existing = self.conn.execute(
            "SELECT sistematica, forma_aquisicao FROM licitacoes WHERE numero_publicacao = ?",
            (lic.numero_publicacao,),
        ).fetchone()

        # Preserve listing-only fields that detail page doesn't provide
        if existing:
            if not lic.sistematica and existing["sistematica"]:
                lic.sistematica = existing["sistematica"]
            if not lic.forma_aquisicao and existing["forma_aquisicao"]:
                lic.forma_aquisicao = existing["forma_aquisicao"]

        self._update(lic)

    def _update_listing_fields(self, lic: LicitacaoCE):
        """Update only fields available from listing (don't overwrite detail enrichment)."""
        self.conn.execute("""
            UPDATE licitacoes SET status=?, data_coleta=?, updated_at=CURRENT_TIMESTAMP
            WHERE numero_publicacao=?
        """, (lic.status, lic.data_coleta.isoformat(), lic.numero_publicacao))
        self.conn.commit()

    def _to_row(self, lic: LicitacaoCE) -> tuple:
        return (
            lic.numero_publicacao,
            lic.numero_processo,
            lic.numero_edital,
            lic.viproc,
            lic.id_pncp,
            lic.orgao,
            lic.gestor_compras,
            lic.objeto,
            lic.sistematica,
            lic.forma_aquisicao,
            lic.natureza_aquisicao,
            lic.tipo_aquisicao,
            lic.moeda,
            lic.data_acolhimento,
            lic.data_abertura,
            lic.status,
            lic.vencedor,
            lic.valor_lance,
            json.dumps(lic.documentos, ensure_ascii=False),
            lic.fonte,
            lic.url_detalhe,
            1 if lic.tem_detalhe else 0,
            lic.hash_registro,
            lic.data_coleta.isoformat(),
            lic.ano,
        )

    # -- Checkpoint ----------------------------------------------------

    def get_progress(self) -> dict:
        row = self.conn.execute("SELECT * FROM scrape_progress WHERE id = 1").fetchone()
        if row:
            return dict(row)
        return {"last_page": 0, "total_pages": 0, "total_records": 0}

    def save_progress(self, page: int, total_pages: int = 0, total_records: int = 0):
        self.conn.execute("""
            INSERT INTO scrape_progress (id, last_page, total_pages, total_records, last_updated)
            VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                last_page=excluded.last_page,
                total_pages=CASE WHEN excluded.total_pages > 0 THEN excluded.total_pages ELSE total_pages END,
                total_records=CASE WHEN excluded.total_records > 0 THEN excluded.total_records ELSE total_records END,
                last_updated=CURRENT_TIMESTAMP
        """, (page, total_pages, total_records))
        self.conn.commit()

    def reset_progress(self):
        self.conn.execute("DELETE FROM scrape_progress")
        self.conn.commit()

    # -- Queries -------------------------------------------------------

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) as c FROM licitacoes").fetchone()["c"]

    def count_with_detail(self) -> int:
        return self.conn.execute("SELECT COUNT(*) as c FROM licitacoes WHERE tem_detalhe = 1").fetchone()["c"]

    def get_without_detail(self, limit: int = 0, status: Optional[str] = None,
                           sistematica: Optional[str] = None) -> list[str]:
        """Publicacoes que ainda nao tem dados de detalhe."""
        query = "SELECT numero_publicacao FROM licitacoes WHERE tem_detalhe = 0"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if sistematica:
            query += " AND sistematica = ?"
            params.append(sistematica)
        query += " ORDER BY numero_publicacao DESC"
        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [r["numero_publicacao"] for r in rows]

    def search(self, keyword: str) -> list[dict]:
        pattern = f"%{keyword}%"
        rows = self.conn.execute("""
            SELECT numero_publicacao, orgao, objeto, sistematica, status, data_abertura, vencedor
            FROM licitacoes
            WHERE objeto LIKE ? OR orgao LIKE ? OR numero_publicacao LIKE ? OR vencedor LIKE ?
            ORDER BY numero_publicacao DESC
            LIMIT 50
        """, (pattern, pattern, pattern, pattern)).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        total = self.count()
        with_detail = self.count_with_detail()
        by_status = self.conn.execute(
            "SELECT status, COUNT(*) as c FROM licitacoes GROUP BY status ORDER BY c DESC"
        ).fetchall()
        by_sistematica = self.conn.execute(
            "SELECT sistematica, COUNT(*) as c FROM licitacoes GROUP BY sistematica ORDER BY c DESC LIMIT 15"
        ).fetchall()
        by_orgao = self.conn.execute(
            "SELECT orgao, COUNT(*) as c FROM licitacoes GROUP BY orgao ORDER BY c DESC LIMIT 15"
        ).fetchall()
        by_ano = self.conn.execute(
            "SELECT ano, COUNT(*) as c FROM licitacoes WHERE ano > 0 GROUP BY ano ORDER BY ano DESC"
        ).fetchall()
        return {
            "total": total,
            "com_detalhe": with_detail,
            "by_status": {r["status"]: r["c"] for r in by_status},
            "by_sistematica": {r["sistematica"]: r["c"] for r in by_sistematica},
            "by_orgao": {r["orgao"]: r["c"] for r in by_orgao},
            "by_ano": {r["ano"]: r["c"] for r in by_ano},
        }

    # -- Export --------------------------------------------------------

    def export_json(self, path: Path) -> int:
        rows = self.conn.execute("SELECT * FROM licitacoes ORDER BY numero_publicacao DESC").fetchall()
        data = [dict(r) for r in rows]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return len(data)

    def export_csv(self, path: Path) -> int:
        import csv
        rows = self.conn.execute("SELECT * FROM licitacoes ORDER BY numero_publicacao DESC").fetchall()
        if not rows:
            return 0
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = rows[0].keys()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow(dict(r))
        return len(rows)
