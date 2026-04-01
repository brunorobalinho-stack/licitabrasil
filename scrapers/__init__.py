"""LicitaBrasil — Scrapers de portais de licitações."""

from .cbtu_govbr import CBTUGovBRScraper
from .jfpe_licitacoes import JFPEScraper

__all__ = ["CBTUGovBRScraper", "JFPEScraper"]
