"""Parser HTML para a Central de Compras de Natal/RN."""

import re
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger

from .models import LicitacaoNatal, DocumentoNatal, HistoricoNatal, LicitanteNatal


def parse_listing_page(html: str, modalidade_slug: str, modalidade_nome: str) -> list[LicitacaoNatal]:
    """Extrai licitacoes da tabela de listagem.

    O HTML do site e malformado: a partir da 2a row, falta o <tr> de abertura.
    Estrategia: usar regex para extrair blocos de 6 <td> consecutivos.
    Colunas: Licitação | Processo | Tipo Licitação | Órgão | Data | Objeto
    """
    items = []

    # Extract all <td>...</td> blocks with their content
    # Pattern: <td ...>CONTENT</td>
    td_pattern = re.compile(
        r'<td[^>]*>(.*?)</td>',
        re.DOTALL | re.IGNORECASE,
    )
    # Find the table content
    table_match = re.search(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
    if not table_match:
        logger.warning("No table found in listing page")
        return items

    table_html = table_match.group(1)
    tds = td_pattern.findall(table_html)

    # Group into rows of 6 (skip pagination td which has colspan)
    i = 0
    while i + 5 < len(tds):
        cell0 = tds[i]
        # First cell must contain a link with ?mod=...&id=
        link_match = re.search(r'href="[^"]*id=(\d+)"[^>]*>([^<]+)</a>', cell0)
        if not link_match:
            i += 1
            continue

        record_id = int(link_match.group(1))
        numero = link_match.group(2).strip()
        processo = _strip_tags(tds[i + 1])
        tipo = _strip_tags(tds[i + 2])
        orgao = _strip_tags(tds[i + 3])
        data = _strip_tags(tds[i + 4])
        objeto = _strip_tags(tds[i + 5])

        items.append(LicitacaoNatal(
            numero_licitacao=numero,
            numero_processo=processo,
            record_id=record_id,
            modalidade=modalidade_nome,
            modalidade_slug=modalidade_slug,
            tipo_licitacao=tipo,
            orgao=orgao,
            data_publicacao=data,
            objeto=objeto,
        ))
        i += 6

    return items


def _strip_tags(html: str) -> str:
    """Remove tags HTML e retorna texto limpo."""
    return re.sub(r'<[^>]+>', '', html).strip()


def parse_total_pages(html: str) -> int:
    """Extrai o numero total de paginas da paginacao."""
    # Pattern: onclick="document.getElementById('pagina').value=N;..."
    matches = re.findall(r"getElementById\('pagina'\)\.value=(\d+)", html)
    if not matches:
        return 1
    return max(int(m) for m in matches)


def parse_detail_page(html: str, base: LicitacaoNatal) -> LicitacaoNatal:
    """Enriquece um registro com dados da pagina de detalhe.

    Tabela principal: Nr.Licitação, Nr.Processo, Modalidade, Tipo Licitação,
                      Titulo, Secretaria Licitante, Objeto, Registro Preço,
                      Local Abertura, Data Abertura
    + Bloqueios, Documentos Relacionados, Histórico, Licitantes
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- Main info table (first table with <th> rowheaders) ---
    field_map = {}
    first_table = soup.find("table")
    if first_table:
        for row in first_table.find_all("tr"):
            headers = row.find_all("th")
            cells = row.find_all("td")
            # Rows can have 2 or 4 cells (key-value or key-value-key-value)
            for i, th in enumerate(headers):
                key = th.get_text(strip=True)
                # Each th is followed by a td
                td_idx = i
                if td_idx < len(cells):
                    field_map[key] = cells[td_idx].get_text(strip=True)

    # Update base with detail fields
    update = base.model_copy()
    update.titulo = field_map.get("Titulo", base.titulo)
    update.orgao = field_map.get("Secretaria Licitante", base.orgao)
    update.objeto = field_map.get("Objeto", base.objeto) or base.objeto
    update.tipo_licitacao = field_map.get("Tipo Licitação", base.tipo_licitacao)
    update.data_abertura = field_map.get("Data Abertura", base.data_abertura)
    update.local_abertura = field_map.get("Local Abertura", base.local_abertura)
    update.registro_preco = field_map.get("Registro Preço", base.registro_preco)

    # --- Documentos Relacionados ---
    docs = _parse_documentos(soup)
    update.documentos = docs

    # --- Historico ---
    historico = _parse_historico(soup)
    update.historico = historico

    # Derive status from last historico phase
    if historico:
        update.status = historico[-1].fase

    # --- Licitantes ---
    licitantes = _parse_licitantes(soup)
    update.licitantes = licitantes

    update.tem_detalhe = True
    return update


def _find_table_after_header(soup: BeautifulSoup, header_text: str) -> Optional[BeautifulSoup]:
    """Encontra a tabela cujo primeiro <th colspan> contem header_text."""
    for table in soup.find_all("table"):
        first_th = table.find("th")
        if first_th and header_text in first_th.get_text(strip=True):
            return table
    return None


def _parse_documentos(soup: BeautifulSoup) -> list[DocumentoNatal]:
    """Extrai documentos da tabela 'Documentos Relacionados'."""
    table = _find_table_after_header(soup, "Documentos Relacionados")
    if not table:
        return []

    docs = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        link = cells[0].find("a")
        if not link:
            continue
        docs.append(DocumentoNatal(
            nome=link.get_text(strip=True),
            url=link.get("href", ""),
            responsavel=cells[1].get_text(strip=True),
        ))
    return docs


def _parse_historico(soup: BeautifulSoup) -> list[HistoricoNatal]:
    """Extrai fases da tabela 'Histórico'."""
    table = _find_table_after_header(soup, "Histórico")
    if not table:
        return []

    items = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        arquivo_url = None
        if len(cells) >= 6:
            link = cells[5].find("a")
            if link:
                arquivo_url = link.get("href", "")

        items.append(HistoricoNatal(
            data=cells[0].get_text(strip=True),
            fase=cells[1].get_text(strip=True),
            detalhe=cells[2].get_text(strip=True),
            arquivo_url=arquivo_url,
        ))
    return items


def _parse_licitantes(soup: BeautifulSoup) -> list[LicitanteNatal]:
    """Extrai participantes da tabela 'Licitantes'."""
    table = _find_table_after_header(soup, "Licitantes")
    if not table:
        return []

    items = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        items.append(LicitanteNatal(
            nome=cells[0].get_text(strip=True),
            observacao=cells[1].get_text(strip=True) if len(cells) > 1 else "",
            situacao=cells[2].get_text(strip=True) if len(cells) > 2 else "",
        ))
    return items
