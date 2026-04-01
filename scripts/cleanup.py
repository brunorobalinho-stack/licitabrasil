#!/usr/bin/env python3
"""Script de limpeza — remove licitações antigas/encerradas.

Uso: python scripts/cleanup.py [--dias N] [--dry-run]
"""

from __future__ import annotations

import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("cleanup")


def main():
    parser = argparse.ArgumentParser(description="Limpeza de licitações antigas")
    parser.add_argument("--dias", type=int, default=180, help="Remover encerradas há mais de N dias")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra o que seria removido")
    args = parser.parse_args()

    logger.info("Cleanup: dias=%d, dry_run=%s", args.dias, args.dry_run)
    # TODO: Query licitações encerradas há mais de N dias e deletar
    logger.warning("Script de cleanup ainda não implementado")


if __name__ == "__main__":
    main()
