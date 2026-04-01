"""Registry de scrapers disponíveis."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from licitabrasil.scrapers.base import BaseScraper

# Lazy imports — evita carregar todos os scrapers na inicialização
SCRAPERS: dict[str, str] = {
    # "maceio": "licitabrasil.scrapers.portals.maceio:MaceioScraper",
    # "natal": "licitabrasil.scrapers.portals.natal:NatalScraper",
    # "ceara": "licitabrasil.scrapers.portals.ceara:CearaScraper",
    # "cbtu": "licitabrasil.scrapers.portals.cbtu:CBTUScraper",
}


def get_scraper(name: str) -> BaseScraper:
    """Instancia um scraper pelo nome do portal."""
    if name not in SCRAPERS:
        available = ", ".join(sorted(SCRAPERS.keys())) or "(nenhum registrado)"
        raise ValueError(f"Scraper '{name}' não encontrado. Disponíveis: {available}")

    module_path, class_name = SCRAPERS[name].rsplit(":", 1)

    import importlib
    module = importlib.import_module(module_path)
    scraper_class = getattr(module, class_name)
    return scraper_class()


def list_scrapers() -> list[str]:
    """Retorna nomes dos scrapers registrados."""
    return sorted(SCRAPERS.keys())
