"""Migra dados de 6 bases SQLite dos scrapers para PostgreSQL unificado.

Uso:
    python -m app.scripts.migrate_sqlite
    python -m app.scripts.migrate_sqlite --fonte maceio
    python -m app.scripts.migrate_sqlite --dry-run
"""

import argparse
import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.models.licitacao import Documento, Licitacao

DATA_DIR = Path("data")

FONTES = {
    "maceio": {
        "db": DATA_DIR / "maceio" / "maceio.db",
        "query": "SELECT * FROM licitacoes",
        "docs_query": "SELECT * FROM documentos WHERE licitacao_id = ?",
        "docs_key": "id",
    },
    "natal": {
        "db": DATA_DIR / "central_compras_natal" / "licitacoes_natal.db",
        "query": "SELECT * FROM licitacoes",
    },
    "ceara": {
        "db": DATA_DIR / "portalcompras_ce" / "licitacoes_ce.db",
        "query": "SELECT * FROM licitacoes",
    },
    "pmsp": {
        "db": DATA_DIR / "prefeitura_sp" / "prefeitura_sp.db",
        "query": "SELECT * FROM licitacoes",
    },
    "cbtu": {
        "db": DATA_DIR / "cbtu_govbr" / "cbtu_govbr.db",
        "query": "SELECT * FROM licitacoes",
        "docs_query": "SELECT * FROM documentos WHERE licitacao_url = ?",
        "docs_key": "url_processo",
    },
    "jfpe": {
        "db": DATA_DIR / "jfpe" / "jfpe.db",
        "query": "SELECT * FROM licitacoes",
        "docs_query": "SELECT * FROM arquivos WHERE licitacao_id = ?",
        "docs_key": "id_licitacao",
    },
}


def parse_date(val) -> datetime | None:
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(val).strip()[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None


def parse_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val) if float(val) > 0 else None
    except (ValueError, TypeError):
        return None


def read_sqlite(db_path: Path, query: str) -> list[dict]:
    if not db_path.exists():
        print(f"  SKIP: {db_path} não encontrado")
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


def read_sqlite_docs(db_path: Path, query: str, key_value) -> list[dict]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, (key_value,)).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


# ── Mappers por fonte ─────────────────────────────────


def map_maceio(row: dict, db_path: Path) -> tuple[dict, list[dict]]:
    lic = {
        "numero_processo": row.get("num_processo", ""),
        "modalidade": row.get("modalidade"),
        "objeto": row.get("objeto", ""),
        "orgao": row.get("orgao_nome"),
        "uf": "AL",
        "status": row.get("status"),
        "data_publicacao": parse_date(row.get("data_abertura")),
        "data_abertura": parse_date(row.get("data_abertura")),
        "data_encerramento": parse_date(row.get("data_fechamento")),
        "valor_estimado": None,  # em homologacoes
        "fonte": "maceio",
        "fonte_id": str(row["id"]),
        "hash_registro": row.get("hash_registro", ""),
        "data_coleta": parse_date(row.get("data_coleta")) or datetime.now(),
    }

    # Buscar valor da primeira homologação
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    homolog = conn.execute(
        "SELECT valor_estimado FROM homologacoes WHERE licitacao_id = ? AND valor_estimado > 0 LIMIT 1",
        (row["id"],)
    ).fetchone()
    if homolog:
        lic["valor_estimado"] = homolog["valor_estimado"]
    conn.close()

    # Documentos
    docs_rows = read_sqlite_docs(db_path, "SELECT * FROM documentos WHERE licitacao_id = ?", row["id"])
    docs = [{"nome": d.get("descricao") or d.get("tipo", "doc"), "url": d.get("arquivo"), "tipo": d.get("tipo")} for d in docs_rows]

    return lic, docs


def map_natal(row: dict, db_path: Path) -> tuple[dict, list[dict]]:
    import json
    lic = {
        "numero_processo": row.get("numero_processo", ""),
        "modalidade": row.get("modalidade"),
        "objeto": row.get("objeto", ""),
        "orgao": row.get("orgao"),
        "uf": "RN",
        "status": row.get("status"),
        "data_publicacao": parse_date(row.get("data_publicacao")),
        "data_abertura": parse_date(row.get("data_abertura")),
        "valor_estimado": None,
        "fonte": "natal",
        "fonte_id": f"{row.get('numero_licitacao', '')}_{row.get('modalidade_slug', '')}",
        "url_origem": row.get("url_detalhe"),
        "hash_registro": row.get("hash_registro", ""),
        "data_coleta": parse_date(row.get("data_coleta")) or datetime.now(),
    }

    docs = []
    try:
        raw_docs = json.loads(row.get("documentos", "[]"))
        for d in raw_docs:
            if isinstance(d, dict):
                docs.append({"nome": d.get("nome", "doc"), "url": d.get("url", ""), "tipo": d.get("tipo")})
    except (json.JSONDecodeError, TypeError):
        pass

    return lic, docs


def map_ceara(row: dict, db_path: Path) -> tuple[dict, list[dict]]:
    import json
    lic = {
        "numero_processo": row.get("numero_processo", ""),
        "modalidade": row.get("sistematica"),
        "objeto": row.get("objeto", ""),
        "orgao": row.get("orgao"),
        "uf": "CE",
        "status": row.get("status"),
        "data_publicacao": parse_date(row.get("data_acolhimento")),
        "data_abertura": parse_date(row.get("data_abertura")),
        "valor_estimado": parse_float(row.get("valor_lance")),
        "fonte": "ceara",
        "fonte_id": row.get("numero_publicacao", ""),
        "url_origem": row.get("url_detalhe"),
        "hash_registro": row.get("hash_registro", ""),
        "data_coleta": parse_date(row.get("data_coleta")) or datetime.now(),
    }

    docs = []
    try:
        raw_docs = json.loads(row.get("documentos", "[]"))
        for d in raw_docs:
            if isinstance(d, dict):
                docs.append({"nome": d.get("nome", "doc"), "url": d.get("url", ""), "tipo": d.get("tipo")})
    except (json.JSONDecodeError, TypeError):
        pass

    return lic, docs


def map_pmsp(row: dict, db_path: Path) -> tuple[dict, list[dict]]:
    lic = {
        "numero_processo": row.get("numero_processo", ""),
        "modalidade": row.get("modalidade"),
        "objeto": row.get("objeto", ""),
        "orgao": row.get("orgao_nome"),
        "uf": "SP",
        "status": row.get("situacao"),
        "data_publicacao": parse_date(row.get("data_publicacao")),
        "data_abertura": parse_date(row.get("data_abertura")),
        "data_encerramento": parse_date(row.get("data_encerramento")),
        "valor_estimado": parse_float(row.get("valor_estimado")),
        "fonte": "pmsp",
        "fonte_id": row.get("numero_controle_pncp", ""),
        "url_origem": row.get("url_pncp"),
        "hash_registro": row.get("hash_registro", ""),
        "data_coleta": parse_date(row.get("data_coleta")) or datetime.now(),
    }
    return lic, []


def map_cbtu(row: dict, db_path: Path) -> tuple[dict, list[dict]]:
    lic = {
        "numero_processo": row.get("numero_processo", ""),
        "modalidade": row.get("modalidade"),
        "objeto": row.get("titulo", ""),
        "orgao": row.get("unidade_nome"),
        "uf": None,
        "status": row.get("status"),
        "data_publicacao": parse_date(row.get("data_publicacao")),
        "valor_estimado": parse_float(row.get("valor_estimado")),
        "fonte": "cbtu",
        "fonte_id": row.get("url_processo", ""),
        "url_origem": row.get("url_processo"),
        "hash_registro": row.get("hash_registro", ""),
        "data_coleta": parse_date(row.get("data_coleta")) or datetime.now(),
    }

    docs_rows = read_sqlite_docs(db_path, "SELECT * FROM documentos WHERE licitacao_url = ?", row.get("url_processo"))
    docs = [{"nome": d.get("nome", "doc"), "url": d.get("url", ""), "tipo": d.get("tipo")} for d in docs_rows]

    return lic, docs


def map_jfpe(row: dict, db_path: Path) -> tuple[dict, list[dict]]:
    lic = {
        "numero_processo": row.get("numero", ""),
        "modalidade": row.get("modalidade"),
        "objeto": row.get("objeto", ""),
        "orgao": "JFPE",
        "uf": "PE",
        "status": None,
        "data_publicacao": parse_date(row.get("data_abertura")),
        "data_abertura": parse_date(row.get("data_abertura")),
        "valor_estimado": None,
        "fonte": "jfpe",
        "fonte_id": str(row.get("id_licitacao", "")),
        "hash_registro": row.get("hash_registro", ""),
        "data_coleta": parse_date(row.get("data_coleta")) or datetime.now(),
    }

    docs_rows = read_sqlite_docs(db_path, "SELECT * FROM arquivos WHERE licitacao_id = ?", row.get("id_licitacao"))
    docs = [{"nome": d.get("nome", "doc"), "url": "", "tipo": d.get("tipo_arquivo")} for d in docs_rows]

    return lic, docs


MAPPERS = {
    "maceio": map_maceio,
    "natal": map_natal,
    "ceara": map_ceara,
    "pmsp": map_pmsp,
    "cbtu": map_cbtu,
    "jfpe": map_jfpe,
}


# ── Main ──────────────────────────────────────────────


async def migrate(fonte_filter: str | None = None, dry_run: bool = False):
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    fontes_to_process = {fonte_filter: FONTES[fonte_filter]} if fonte_filter else FONTES
    total_migrated = 0
    total_docs = 0

    for fonte_name, fonte_cfg in fontes_to_process.items():
        db_path = fonte_cfg["db"]
        print(f"\n{'='*60}")
        print(f"Fonte: {fonte_name} ({db_path})")
        print(f"{'='*60}")

        rows = read_sqlite(db_path, fonte_cfg["query"])
        if not rows:
            continue

        mapper = MAPPERS[fonte_name]
        batch = []
        docs_batch = []

        for row in rows:
            try:
                lic_data, docs = mapper(row, db_path)
                if not lic_data.get("fonte_id"):
                    continue
                batch.append(lic_data)
                for d in docs:
                    docs_batch.append({**d, "_fonte_id": lic_data["fonte_id"], "_fonte": fonte_name})
            except Exception as e:
                print(f"  ERRO mapeando registro: {e}")
                continue

        print(f"  Registros mapeados: {len(batch)}")
        print(f"  Documentos mapeados: {len(docs_batch)}")

        if dry_run:
            print("  [DRY RUN] Nada inserido.")
            continue

        # Insert em batches de 500
        async with session_maker() as session:
            inserted = 0
            for i in range(0, len(batch), 500):
                chunk = batch[i:i+500]
                stmt = pg_insert(Licitacao).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_fonte_id",
                    set_={
                        "numero_processo": stmt.excluded.numero_processo,
                        "modalidade": stmt.excluded.modalidade,
                        "objeto": stmt.excluded.objeto,
                        "orgao": stmt.excluded.orgao,
                        "status": stmt.excluded.status,
                        "data_publicacao": stmt.excluded.data_publicacao,
                        "valor_estimado": stmt.excluded.valor_estimado,
                        "hash_registro": stmt.excluded.hash_registro,
                        "updated_at": func.now(),
                    },
                )
                await session.execute(stmt)
                inserted += len(chunk)
                print(f"  Inseridos: {inserted}/{len(batch)}", end="\r")

            await session.commit()
            print(f"  Licitações inseridas/atualizadas: {inserted}")

            # Inserir documentos
            if docs_batch:
                # Buscar IDs das licitações inseridas
                for doc in docs_batch:
                    result = await session.execute(
                        select(Licitacao.id).where(
                            Licitacao.fonte == doc["_fonte"],
                            Licitacao.fonte_id == doc["_fonte_id"],
                        )
                    )
                    lic_id = result.scalar_one_or_none()
                    if lic_id:
                        session.add(Documento(
                            licitacao_id=lic_id,
                            nome=doc.get("nome", "doc"),
                            url=doc.get("url"),
                            tipo=doc.get("tipo"),
                        ))

                await session.commit()
                print(f"  Documentos inseridos: {len(docs_batch)}")
                total_docs += len(docs_batch)

            total_migrated += inserted

    print(f"\n{'='*60}")
    print(f"TOTAL: {total_migrated} licitações, {total_docs} documentos")
    print(f"{'='*60}")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Migrar SQLite → PostgreSQL")
    parser.add_argument("--fonte", choices=list(FONTES.keys()), help="Migrar apenas uma fonte")
    parser.add_argument("--dry-run", action="store_true", help="Simular sem inserir")
    args = parser.parse_args()

    asyncio.run(migrate(args.fonte, args.dry_run))


if __name__ == "__main__":
    main()
