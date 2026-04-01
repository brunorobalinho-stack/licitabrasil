"""Shim de retrocompatibilidade — use licitabrasil.database diretamente."""

from licitabrasil.database import dispose_engine, get_session

__all__ = ["get_session", "dispose_engine"]
