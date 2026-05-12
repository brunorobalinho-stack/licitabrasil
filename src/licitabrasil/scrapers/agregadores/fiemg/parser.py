"""Parsing HTML / XML do FIEMG Compras."""

from __future__ import annotations

import re
from datetime import datetime
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
from loguru import logger

from .models import (
    Licitacao,
    LicitacaoListItem,
    SDE_REGEX,
    normalize_fase,
)


DATE_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def parse_datetime(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_valor(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", text).replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_feed(xml_text: str) -> list[LicitacaoListItem]:
    if not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning(f"Feed FIEMG inválido: {exc}")
        return []

    items: list[LicitacaoListItem] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pubdate = (item.findtext("pubDate") or "").strip()

        match = SDE_REGEX.search(title) or SDE_REGEX.search(description)
        if not match:
            continue
        sde = f"SDE-{match.group(1)}"

        items.append(
            LicitacaoListItem(
                sde=sde,
                objeto_resumido=(title or description)[:200],
                url=link,
                data_encerramento_propostas=parse_datetime(pubdate),
            )
        )
    return items


def parse_listing(html: str) -> list[LicitacaoListItem]:
    """Lista processos em andamento da FIEMG.

    # PROBE: portal usa cards/tabela com classes Bootstrap. Estrutura
    # esperada: ``.processo-card`` ou ``table.tabela-processos`` com
    # colunas SDE | Objeto | Fase | Data limite.
    """
    soup = BeautifulSoup(html, "lxml")

    items: list[LicitacaoListItem] = []

    # Estratégia 1: cards
    for card in soup.select(".processo-card, .card-processo, [data-sde]"):
        sde_text = card.get("data-sde") or card.select_one(".sde, .numero-sde")
        if hasattr(sde_text, "get_text"):
            sde_text = sde_text.get_text(strip=True)
        if not sde_text:
            continue
        match = SDE_REGEX.search(str(sde_text))
        if not match:
            continue
        sde = f"SDE-{match.group(1)}"

        link = card.find("a", href=True)
        items.append(
            LicitacaoListItem(
                sde=sde,
                objeto_resumido=(card.select_one(".objeto, .descricao") or card).get_text(strip=True)[:200],
                fase=normalize_fase(
                    (card.select_one(".fase, .status") or card).get_text(strip=True)
                ),
                url=link["href"] if link else "",
            )
        )

    # Estratégia 2: tabela
    if not items:
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if not any("sde" in h or "processo" in h for h in headers):
                continue
            for row in table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if not cells:
                    continue
                sde_match = SDE_REGEX.search(cells[0].get_text())
                if not sde_match:
                    continue
                items.append(
                    LicitacaoListItem(
                        sde=f"SDE-{sde_match.group(1)}",
                        objeto_resumido=cells[1].get_text(strip=True) if len(cells) > 1 else "",
                        fase=normalize_fase(cells[2].get_text(strip=True)) if len(cells) > 2 else "",
                        data_encerramento_propostas=parse_datetime(
                            cells[3].get_text(strip=True) if len(cells) > 3 else ""
                        ),
                        url=(cells[0].find("a") or {}).get("href", "") if cells[0].find("a") else "",
                    )
                )

    return items


def parse_detail(html: str, sde: str) -> Licitacao:
    """Parseia página de detalhe de um processo FIEMG.

    # PROBE: validar labels e seletores; FIEMG usa labels como
    # 'Objeto:', 'Data limite para envio de propostas:', 'Fase atual:',
    # 'Unidade Compradora:', 'Valor estimado:'.
    """
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)

    lic = Licitacao.from_sde(sde)

    patterns = {
        "objeto": re.compile(r"objeto\s*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "fase": re.compile(r"fase\s*(?:atual)?\s*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "situacao": re.compile(r"situa[çc][ãa]o\s*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "unidade_compradora": re.compile(
            r"unidade\s+compradora\s*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE
        ),
        "categoria": re.compile(r"categoria\s*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE),
        "data_publicacao": re.compile(
            r"data\s+de\s+publica[çc][ãa]o\s*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE
        ),
        "data_encerramento_propostas": re.compile(
            r"data\s+limite[^\n:]*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE
        ),
        "data_abertura_propostas": re.compile(
            r"data\s+(?:de\s+)?in[íi]cio[^\n:]*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE
        ),
        "data_sessao_publica": re.compile(
            r"sess[ãa]o\s+p[úu]blica\s*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE
        ),
        "valor_estimado": re.compile(
            r"valor\s+estimado\s*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE
        ),
        "motivo_justificativa": re.compile(
            r"justificativa\s*[:：]\s*(.+?)(?:\n|$)", re.IGNORECASE
        ),
    }

    for field, pattern in patterns.items():
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1).strip()
        if field.startswith("data_"):
            setattr(lic, field, parse_datetime(value))
        elif field == "valor_estimado":
            lic.valor_estimado = parse_valor(value)
        elif field == "fase":
            lic.fase = normalize_fase(value)
        else:
            setattr(lic, field, value)

    # Links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text_low = a.get_text(strip=True).lower()
        if "edital" in text_low or "termo de referência" in text_low:
            lic.url_edital = href
        elif any(href.lower().endswith(ext) for ext in (".pdf", ".zip", ".docx", ".xlsx")):
            lic.urls_anexos.append(href)

    return lic
