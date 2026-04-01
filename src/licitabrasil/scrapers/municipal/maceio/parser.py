"""Parser HTML para listagem de licitações de Maceió."""

import re

from bs4 import BeautifulSoup

from .models import LicitacaoListItem


def parse_listing_page(html: str) -> list[LicitacaoListItem]:
    """Extrai itens da listagem HTML."""
    soup = BeautifulSoup(html, "lxml")
    items = []

    # Find all table rows in the listing grid
    tbody = soup.select("table tbody tr")
    for row in tbody:
        cells = row.select("td")
        if len(cells) < 7:
            continue

        # Extract ID from "Ver mais" link: /visualizar/{id}
        link = row.find("a", href=re.compile(r"/visualizar/(\d+)"))
        if not link:
            # Also check the expand row that appears after clicking
            continue

        match = re.search(r"/visualizar/(\d+)", link["href"])
        if not match:
            continue

        licitacao_id = int(match.group(1))

        items.append(LicitacaoListItem(
            id=licitacao_id,
            numero=cells[1].get_text(strip=True) if len(cells) > 1 else "",
            tipo=cells[2].get_text(strip=True) if len(cells) > 2 else "",
            objeto=cells[3].get_text(strip=True) if len(cells) > 3 else "",
            data_abertura=cells[4].get_text(strip=True) if len(cells) > 4 else "",
            orgao=cells[5].get_text(strip=True) if len(cells) > 5 else "",
            status=cells[6].get_text(strip=True) if len(cells) > 6 else "",
        ))

    return items


def parse_listing_ids(html: str) -> list[int]:
    """Extrai somente IDs da listagem HTML (mais rápido)."""
    ids = []
    for match in re.finditer(r"/visualizar/(\d+)", html):
        licitacao_id = int(match.group(1))
        if licitacao_id not in ids:
            ids.append(licitacao_id)
    return ids


def parse_total_pages(html: str) -> int:
    """Extrai o número total de páginas da paginação."""
    soup = BeautifulSoup(html, "lxml")

    # Look for pagination links - last page number before "Next"
    pagination = soup.select("nav ul li a")
    max_page = 1
    for link in pagination:
        href = link.get("href", "")
        match = re.search(r"page=(\d+)", href)
        if match:
            page_num = int(match.group(1))
            max_page = max(max_page, page_num)

    # Also check for text in pagination items (e.g., "355", "356")
    for li in soup.select("nav ul li"):
        text = li.get_text(strip=True)
        if text.isdigit():
            max_page = max(max_page, int(text))

    return max_page
