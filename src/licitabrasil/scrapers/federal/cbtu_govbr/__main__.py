"""Entry point CLI do scraper CBTU (gov.br Plone).

Uso:
    python -m licitabrasil.scrapers.federal.cbtu_govbr [--max-unidades N]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback

from loguru import logger

from .scraper import CBTUGovBRScraper


async def _run(max_unidades: int) -> int:
    async with CBTUGovBRScraper() as scraper:
        try:
            results = await scraper.scrape(max_unidades=max_unidades or None)
        except TypeError:
            results = await scraper.scrape()

        if not isinstance(results, list):
            logger.warning(f"[CBTU] scrape() retornou tipo inesperado: {type(results).__name__}")
            return 0

        total = len(results)
        if total == 0:
            logger.info("[CBTU] sync concluido sem registros coletados.")
            return 0

        # Persiste no SQLite. Antes deste fix, scrape() retornava a lista em
        # memoria e o processo terminava sem chamar save() -- itens coletados,
        # DB sem update (mesma raiz do bug do JFPE).
        new, updated, unchanged = scraper.save(results)
        logger.info(
            f"[CBTU] sync concluido. coletados={total} novos={new} "
            f"atualizados={updated} inalterados={unchanged}"
        )
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scraper CBTU gov.br")
    parser.add_argument(
        "--max-unidades", type=int, default=0, help="Limitar a N unidades (0 = todas)"
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args.max_unidades))
    except Exception as exc:
        logger.error(f"[CBTU] FAIL: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
