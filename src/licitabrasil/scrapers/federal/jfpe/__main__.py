"""Entry point CLI do scraper JFPE.

Uso:
    python -m licitabrasil.scrapers.federal.jfpe [--max-items N]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback

from loguru import logger

from .scraper import JFPEScraper


async def _run(max_items: int) -> int:
    async with JFPEScraper() as scraper:
        try:
            results = await scraper.scrape(max_items=max_items)
        except TypeError:
            results = await scraper.scrape()

        if not isinstance(results, list):
            logger.warning(f"[JFPE] scrape() retornou tipo inesperado: {type(results).__name__}")
            return 0

        total = len(results)
        if total == 0:
            logger.info("[JFPE] sync concluido sem registros coletados.")
            return 0

        # Persiste no SQLite. Antes deste fix, scrape() retornava a lista em
        # memoria e o processo terminava sem chamar save() -- itens coletados,
        # DB intocado (Bug Dia 0.5 #1).
        new, updated, unchanged = scraper.save(results)
        logger.info(
            f"[JFPE] sync concluido. coletados={total} novos={new} "
            f"atualizados={updated} inalterados={unchanged}"
        )
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scraper JFPE")
    parser.add_argument("--max-items", type=int, default=0, help="Limitar a N itens (0 = todos)")
    parser.add_argument("--max-pages", type=int, default=0, help="Alias compat (passa pra max-items)")
    args = parser.parse_args()
    n = args.max_items or args.max_pages or 0
    try:
        return asyncio.run(_run(n))
    except Exception as exc:
        logger.error(f"[JFPE] FAIL: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
