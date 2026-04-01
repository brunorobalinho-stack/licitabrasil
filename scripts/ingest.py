#!/usr/bin/env python3
"""Script de ingestão — roda todos os scrapers em sequência.

Uso: python scripts/ingest.py [--portal PORTAL] [--dias N]
"""

from __future__ import annotations

import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("ingest")


def main():
    parser = argparse.ArgumentParser(description="Ingestão de licitações")
    parser.add_argument("--portal", help="Portal específico (default: todos)")
    parser.add_argument("--dias", type=int, default=7, help="Dias retroativos")
    args = parser.parse_args()

    logger.info("Ingestão: portal=%s, dias=%d", args.portal or "todos", args.dias)
    # TODO: Invocar scrapers registrados
    logger.warning("Script de ingestão ainda não implementado")


if __name__ == "__main__":
    main()
