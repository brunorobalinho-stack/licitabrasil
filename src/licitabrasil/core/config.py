"""Shim de retrocompatibilidade — use licitabrasil.config diretamente."""

from licitabrasil.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
