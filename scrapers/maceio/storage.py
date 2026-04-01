"""SQLite storage com 4 tabelas normalizadas."""

import json
import sqlite3
from pathlib import Path
from typing import Optional


from .models import Licitacao


SCHEMA = """
CREATE TABLE IF NOT EXISTS licitacoes (
    id INTEGER PRIMARY KEY,
    num_processo TEXT NOT NULL,
    objeto TEXT NOT NULL,
    data_abertura TEXT,
    hora_abertura TEXT,
    data_fechamento TEXT,
    hora_fechamento TEXT,
    numero_modalidade INTEGER DEFAULT 0,
    ano_modalidade INTEGER DEFAULT 0,
    modalidade TEXT DEFAULT '',
    orgao_nome TEXT DEFAULT '',
    orgao_sigla TEXT DEFAULT '',
    cota TEXT DEFAULT '',
    status TEXT DEFAULT '',
    responsavel TEXT DEFAULT '',
    hash_registro TEXT NOT NULL,
    raw_json TEXT,
    data_coleta TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS homologacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    licitacao_id INTEGER NOT NULL,
    data_publicacao_homologacao TEXT,
    data_publicacao_extrato TEXT,
    lotes TEXT DEFAULT '',
    valor_estimado REAL DEFAULT 0,
    valor_contratado REAL DEFAULT 0,
    empresa_nome TEXT DEFAULT '',
    empresa_cnpj TEXT DEFAULT '',
    empresa_enquadramento TEXT DEFAULT '',
    empresa_tipo TEXT DEFAULT '',
    empresa_cidade TEXT DEFAULT '',
    empresa_estado TEXT DEFAULT '',
    arquivo TEXT,
    FOREIGN KEY (licitacao_id) REFERENCES licitacoes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS atas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    licitacao_id INTEGER NOT NULL,
    numero TEXT DEFAULT '',
    data_assinatura TEXT,
    data_publicacao TEXT,
    vigencia_inicio TEXT,
    vigencia_fim TEXT,
    empresa_nome TEXT DEFAULT '',
    empresa_cnpj TEXT DEFAULT '',
    arquivo TEXT,
    FOREIGN KEY (licitacao_id) REFERENCES licitacoes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    licitacao_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    descricao TEXT DEFAULT '',
    criado_em TEXT,
    arquivo TEXT NOT NULL,
    sha256 TEXT,
    local_path TEXT,
    FOREIGN KEY (licitacao_id) REFERENCES licitacoes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lic_processo ON licitacoes(num_processo);
CREATE INDEX IF NOT EXISTS idx_lic_modalidade ON licitacoes(modalidade);
CREATE INDEX IF NOT EXISTS idx_lic_orgao ON licitacoes(orgao_nome);
CREATE INDEX IF NOT EXISTS idx_lic_status ON licitacoes(status);
CREATE INDEX IF NOT EXISTS idx_lic_ano ON licitacoes(ano_modalidade);
CREATE INDEX IF NOT EXISTS idx_lic_hash ON licitacoes(hash_registro);
CREATE INDEX IF NOT EXISTS idx_homolog_lic ON homologacoes(licitacao_id);
CREATE INDEX IF NOT EXISTS idx_atas_lic ON atas(licitacao_id);
CREATE INDEX IF NOT EXISTS idx_docs_lic ON documentos(licitacao_id);
CREATE INDEX IF NOT EXISTS idx_docs_sha ON documentos(sha256);
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

    # ── Upsert ──────────────────────────────────────

    def upsert_licitacao(self, lic: Licitacao) -> tuple[bool, bool]:
        """Insere ou atualiza. Retorna (is_new, is_updated)."""
        existing = self.conn.execute(
            "SELECT hash_registro FROM licitacoes WHERE id = ?", (lic.id,)
        ).fetchone()

        if existing is None:
            self._insert_licitacao(lic)
            return (True, False)

        if existing["hash_registro"] != lic.hash_registro:
            self._update_licitacao(lic)
            return (False, True)

        return (False, False)

    def _insert_licitacao(self, lic: Licitacao):
        self.conn.execute("""
            INSERT INTO licitacoes (id, num_processo, objeto, data_abertura, hora_abertura,
                data_fechamento, hora_fechamento, numero_modalidade, ano_modalidade, modalidade,
                orgao_nome, orgao_sigla, cota, status, responsavel, hash_registro, raw_json, data_coleta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, self._lic_to_row(lic))
        self._save_related(lic)
        self.conn.commit()

    def _update_licitacao(self, lic: Licitacao):
        self.conn.execute("""
            UPDATE licitacoes SET num_processo=?, objeto=?, data_abertura=?, hora_abertura=?,
                data_fechamento=?, hora_fechamento=?, numero_modalidade=?, ano_modalidade=?,
                modalidade=?, orgao_nome=?, orgao_sigla=?, cota=?, status=?, responsavel=?,
                hash_registro=?, raw_json=?, data_coleta=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, self._lic_to_row(lic)[1:] + (lic.id,))
        # Replace related records
        self.conn.execute("DELETE FROM homologacoes WHERE licitacao_id = ?", (lic.id,))
        self.conn.execute("DELETE FROM atas WHERE licitacao_id = ?", (lic.id,))
        self.conn.execute("DELETE FROM documentos WHERE licitacao_id = ?", (lic.id,))
        self._save_related(lic)
        self.conn.commit()

    def _lic_to_row(self, lic: Licitacao) -> tuple:
        return (
            lic.id,
            lic.num_processo,
            lic.objeto,
            lic.data_abertura.isoformat() if lic.data_abertura else None,
            lic.hora_abertura,
            lic.data_fechamento.isoformat() if lic.data_fechamento else None,
            lic.hora_fechamento,
            lic.numero_modalidade,
            lic.ano_modalidade,
            lic.modalidade,
            lic.orgao.nome if lic.orgao else "",
            lic.orgao.sigla if lic.orgao else "",
            lic.cota,
            lic.status,
            lic.responsavel,
            lic.hash_registro,
            lic.raw_json,
            lic.data_coleta.isoformat(),
        )

    def _save_related(self, lic: Licitacao):
        for h in lic.homologacoes:
            self.conn.execute("""
                INSERT INTO homologacoes (licitacao_id, data_publicacao_homologacao,
                    data_publicacao_extrato, lotes, valor_estimado, valor_contratado,
                    empresa_nome, empresa_cnpj, empresa_enquadramento, empresa_tipo,
                    empresa_cidade, empresa_estado, arquivo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lic.id,
                h.data_publicacao_homologacao.isoformat() if h.data_publicacao_homologacao else None,
                h.data_publicacao_extrato.isoformat() if h.data_publicacao_extrato else None,
                h.lotes,
                h.valor_estimado,
                h.valor_contratado,
                h.empresa.nome if h.empresa else "",
                h.empresa.cnpj if h.empresa else "",
                h.empresa.enquadramento if h.empresa else "",
                h.empresa.tipo_societario if h.empresa else "",
                h.empresa.cidade if h.empresa else "",
                h.empresa.estado if h.empresa else "",
                h.arquivo,
            ))

        for a in lic.atas:
            self.conn.execute("""
                INSERT INTO atas (licitacao_id, numero, data_assinatura, data_publicacao,
                    vigencia_inicio, vigencia_fim, empresa_nome, empresa_cnpj, arquivo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lic.id,
                a.numero,
                a.data_assinatura.isoformat() if a.data_assinatura else None,
                a.data_publicacao.isoformat() if a.data_publicacao else None,
                a.vigencia_inicio.isoformat() if a.vigencia_inicio else None,
                a.vigencia_fim.isoformat() if a.vigencia_fim else None,
                a.empresa.nome if a.empresa else "",
                a.empresa.cnpj if a.empresa else "",
                a.arquivo,
            ))

        for d in lic.documentos:
            self.conn.execute("""
                INSERT INTO documentos (licitacao_id, tipo, descricao, criado_em, arquivo, sha256, local_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                lic.id,
                d.tipo,
                d.descricao,
                d.criado_em.isoformat() if d.criado_em else None,
                d.arquivo,
                d.sha256,
                d.local_path,
            ))

    # ── Queries ─────────────────────────────────────

    def get_known_ids(self) -> set[int]:
        rows = self.conn.execute("SELECT id FROM licitacoes").fetchall()
        return {r["id"] for r in rows}

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) as c FROM licitacoes").fetchone()["c"]

    def search(self, keyword: str) -> list[dict]:
        pattern = f"%{keyword}%"
        rows = self.conn.execute("""
            SELECT id, num_processo, objeto, modalidade, orgao_nome, status, ano_modalidade,
                   numero_modalidade, data_abertura
            FROM licitacoes
            WHERE objeto LIKE ? OR orgao_nome LIKE ? OR num_processo LIKE ? OR modalidade LIKE ?
            ORDER BY id DESC
        """, (pattern, pattern, pattern, pattern)).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        total = self.count()
        by_modalidade = self.conn.execute(
            "SELECT modalidade, COUNT(*) as c FROM licitacoes GROUP BY modalidade ORDER BY c DESC"
        ).fetchall()
        by_orgao = self.conn.execute(
            "SELECT orgao_nome, COUNT(*) as c FROM licitacoes GROUP BY orgao_nome ORDER BY c DESC LIMIT 15"
        ).fetchall()
        by_status = self.conn.execute(
            "SELECT status, COUNT(*) as c FROM licitacoes GROUP BY status ORDER BY c DESC"
        ).fetchall()
        by_ano = self.conn.execute(
            "SELECT ano_modalidade, COUNT(*) as c FROM licitacoes WHERE ano_modalidade > 0 GROUP BY ano_modalidade ORDER BY ano_modalidade DESC"
        ).fetchall()
        n_homolog = self.conn.execute("SELECT COUNT(*) as c FROM homologacoes").fetchone()["c"]
        n_atas = self.conn.execute("SELECT COUNT(*) as c FROM atas").fetchone()["c"]
        n_docs = self.conn.execute("SELECT COUNT(*) as c FROM documentos").fetchone()["c"]
        total_valor = self.conn.execute(
            "SELECT COALESCE(SUM(valor_contratado), 0) as total FROM homologacoes"
        ).fetchone()["total"]

        return {
            "total": total,
            "by_modalidade": {r["modalidade"]: r["c"] for r in by_modalidade},
            "by_orgao": {r["orgao_nome"]: r["c"] for r in by_orgao},
            "by_status": {r["status"]: r["c"] for r in by_status},
            "by_ano": {r["ano_modalidade"]: r["c"] for r in by_ano},
            "homologacoes": n_homolog,
            "atas": n_atas,
            "documentos": n_docs,
            "valor_total_contratado": total_valor,
        }

    def get_pending_downloads(self) -> list[dict]:
        """Docs que ainda não foram baixados (sem sha256)."""
        rows = self.conn.execute("""
            SELECT d.id, d.licitacao_id, d.tipo, d.arquivo, l.num_processo
            FROM documentos d
            JOIN licitacoes l ON d.licitacao_id = l.id
            WHERE d.sha256 IS NULL AND d.arquivo IS NOT NULL AND d.arquivo != ''
        """).fetchall()
        return [dict(r) for r in rows]

    def update_document_hash(self, doc_id: int, sha256: str, local_path: str):
        self.conn.execute(
            "UPDATE documentos SET sha256=?, local_path=? WHERE id=?",
            (sha256, local_path, doc_id),
        )
        self.conn.commit()

    def doc_exists_by_hash(self, sha256: str) -> Optional[str]:
        """Retorna local_path se documento com esse hash já existe."""
        row = self.conn.execute(
            "SELECT local_path FROM documentos WHERE sha256 = ? AND local_path IS NOT NULL LIMIT 1",
            (sha256,),
        ).fetchone()
        return row["local_path"] if row else None

    # ── Export ──────────────────────────────────────

    def export_json(self, path: Path) -> int:
        rows = self.conn.execute("""
            SELECT l.*, GROUP_CONCAT(DISTINCT d.tipo || ':' || d.arquivo) as doc_list
            FROM licitacoes l
            LEFT JOIN documentos d ON l.id = d.licitacao_id
            GROUP BY l.id
            ORDER BY l.id DESC
        """).fetchall()
        data = [dict(r) for r in rows]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return len(data)

    def export_csv(self, path: Path) -> int:
        import csv
        rows = self.conn.execute(
            "SELECT * FROM licitacoes ORDER BY id DESC"
        ).fetchall()
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
