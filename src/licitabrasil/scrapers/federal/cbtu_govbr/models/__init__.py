"""Shim — re-exporta modelos de ..cbtu para compatibilidade com scraper.py.

Bug pré-existente: scraper.py faz `from .models.cbtu import ...` mas
o arquivo cbtu.py vive na raiz de cbtu_govbr/, não em models/.
Este shim evita refatorar o scraper.py original.
"""
from ..cbtu import *  # noqa: F401, F403
