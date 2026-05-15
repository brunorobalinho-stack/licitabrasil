"""Shim — reexporta cbtu.py da raiz para .models.cbtu (esperado pelo scraper)."""
from ..cbtu import *  # noqa: F401, F403
from ..cbtu import (  # explicit re-export pra IDE e mypy
    DocumentoCBTU,
    LicitacaoCBTU,
)

# infer_status pode não existir como nome explícito — tentar importar
try:
    from ..cbtu import infer_status  # noqa: F401
except ImportError:
    pass
