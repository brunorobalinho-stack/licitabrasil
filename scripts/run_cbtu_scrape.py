#!/usr/bin/env python3
"""
Runner para coleta CBTU. Roda o scraper completo, salva no SQLite e imprime resumo.

Uso:
    python scripts/run_cbtu_scrape.py
"""
import asyncio
import sys
from pathlib import Path

# Garantir import relativo a partir da raiz do projeto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scrapers.cbtu_govbr import CBTUGovBRScraper  # noqa: E402
from loguru import logger  # noqa: E402


async def main() -> int:
    db_path = ROOT / "data" / "cbtu_govbr" / "cbtu_govbr.db"
    logger.info(f"DB: {db_path}")

    async with CBTUGovBRScraper(db_path=db_path) as scraper:
        results = await scraper.scrape()
        logger.info(f"Scrape concluido: {len(results)} licitacoes coletadas")
        new, updated, unchanged = scraper.save(results)
        logger.info(f"DB: novas={new} atualizadas={updated} inalteradas={unchanged}")

    # Stats finais
    stats = CBTUGovBRScraper(db_path=db_path).stats()
    print("=" * 60)
    print("RESUMO POS-COLETA CBTU")
    print("=" * 60)
    print(f"Total licitacoes: {stats.get('total', 0)}")
    print(f"Total documentos: {stats.get('documentos', 0)}")
    print()
    print("Por unidade:")
    for k, v in stats.get("by_unidade", {}).items():
        print(f"  {k:30s} {v}")
    print()
    print("Por status:")
    for k, v in stats.get("by_status", {}).items():
        print(f"  {k:20s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
