"""Parsing HTML / XML do PE-Integrado.

Duas estratégias coexistem:

1. **Feed RSS/Atom** (se disponível em ``/internet/rss/editais.xml``):
   parsing rápido, sem necessidade de ViewState.

2. **Listagem HTML** (consultaProcessos.seam): parsing com BeautifulSoup,
   sujeito a quebrar quando o portal atualizar.

⚠ TODOs com ``# PROBE`` precisam ser validados contra HTML real.
"""

from __future__ import annotations

import re
from datetime import datetime
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
from loguru import logger

from .models import Licitacao, LicitacaoListItem, infer_modalidade, parse_processo_number


DATE_FORMATS = (
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
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
    logger.debug(f"Data não reconhecida: {text!r}")
    return None


def parse_valor(text: str | None) -> float | None:
    """Converte 'R$ 1.234.567,89' → 1234567.89."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", text).replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────
# RSS / Atom feed
# ─────────────────────────────────────────────────────────────


def parse_feed(xml_text: str) -> list[LicitacaoListItem]:
    """Parsea feed RSS de novos editais. Retorna lista de itens leves."""
    if not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning(f"Feed XML inválido: {exc}")
        return []

    items: list[LicitacaoListItem] = []
    # RSS 2.0: //channel/item
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()

        # Extrai número de processo do título
        from .models import PROCESSO_REGEX
        match = PROCESSO_REGEX.search(title) or PROCESSO_REGEX.search(description)
        numero = match.group(1) if match else ""
        if not numero:
            continue

        items.append(
            LicitacaoListItem(
                numero=numero,
                objeto_resumido=description[:200],
                modalidade=infer_modalidade(numero),
                url=link,
            )
        )
    return items


# ─────────────────────────────────────────────────────────────
# HTML — listagem
# ─────────────────────────────────────────────────────────────


def parse_listing(html: str) -> list[LicitacaoListItem]:
    """Extrai itens da página de listagem do PE-Integrado.

    Páginas reais (probe 2026-05-12):
      - /Portal/Pages/LicitacoesEmAndamento.aspx — table sem id, 17 colunas
      - /Portal/Pages/DispensaLicitacoes.aspx — table id=exibirDados, 18 cols

    Colunas observadas (na ordem do <thead>):
      0  Código sequencial
      1  Processo                ← número do processo (formato XXXX.YYYY.TIPO.SUB.NNNN.ORGAO)
      2  Edital
      3  Unidade compradora
      4  Unidade gestora
      5  Objeto
      6  Modalidade
      7  Título
      8  Data/Hora inicial       ← data_abertura_propostas
      9  Data/Hora final         ← data_encerramento_propostas
      10 Situação do processo
      11 Edital (link PDF)
      12 Finalização
      13 Valor estimado
      14 Valor negociado
      15 Economia
      16 % economia
    """
    soup = BeautifulSoup(html, "lxml")

    # Tenta primeiro pela id exibirDados (página dispensa), depois pela classe
    # 'small-fonts-table' usada nas duas variantes
    table = soup.find("table", id="exibirDados")
    if table is None:
        for t in soup.find_all("table"):
            classes = " ".join(t.get("class") or [])
            if "small-fonts-table" in classes:
                table = t
                break

    if table is None:
        logger.warning("Tabela de listagem PE-Integrado não encontrada — portal mudou?")
        return []

    items: list[LicitacaoListItem] = []
    from .models import PROCESSO_REGEX

    # Pula <thead>, processa só <tbody> ou <tr> com <td>
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 8:
            continue  # cabeçalho ou linha de filtro

        try:
            numero = cells[1].get_text(strip=True)
            if not PROCESSO_REGEX.search(numero):
                # Tenta na coluna 0 (caso a ordem mude)
                numero = cells[0].get_text(strip=True)
                if not PROCESSO_REGEX.search(numero):
                    continue

            link = cells[1].find("a") or cells[0].find("a")
            url = link.get("href", "") if link else ""
            if url and not url.startswith("http"):
                url = f"https://www.peintegrado.pe.gov.br{url}"

            unidade_compradora = cells[3].get_text(strip=True) if len(cells) > 3 else ""

            items.append(
                LicitacaoListItem(
                    numero=numero,
                    orgao_sigla=unidade_compradora[:40],
                    modalidade=(cells[6].get_text(strip=True) if len(cells) > 6 else infer_modalidade(numero)),
                    objeto_resumido=cells[5].get_text(strip=True) if len(cells) > 5 else "",
                    situacao=cells[10].get_text(strip=True) if len(cells) > 10 else "",
                    url=url,
                )
            )
        except (IndexError, AttributeError):
            continue

    return items


# ─────────────────────────────────────────────────────────────
# HTML — detalhe
# ─────────────────────────────────────────────────────────────


def parse_detail(html: str, numero: str) -> Licitacao:
    """Extrai dados completos da página de detalhe.

    # PROBE: a página de detalhe usa labels textuais ("Número do Processo:",
    # "Objeto:", "Data Abertura:") em ``<span>`` ou ``<td>``. O parser abaixo
    # busca por label e captura o irmão imediato.
    """
    soup = BeautifulSoup(html, "lxml")

    lic = Licitacao.from_numero(numero)

    label_map = {
        "objeto": ("objeto", "objeto da compra"),
        "data_abertura_propostas": ("data abertura", "abertura das propostas", "data de abertura"),
        "data_encerramento_propostas": ("data encerramento", "encerramento das propostas"),
        "data_publicacao": ("publicação", "data de publicação"),
        "situacao": ("situação", "fase atual", "status"),
        "valor_estimado": ("valor estimado", "valor de referência", "valor referência"),
    }

    text = soup.get_text("\n", strip=True).lower()

    for field, labels in label_map.items():
        for label in labels:
            pattern = re.compile(
                rf"{re.escape(label)}\s*[:：]\s*([^\n]+)", re.IGNORECASE
            )
            match = pattern.search(text)
            if match:
                value = match.group(1).strip()
                if field.startswith("data_") or field == "data_publicacao":
                    setattr(lic, field, parse_datetime(value))
                elif field == "valor_estimado":
                    lic.valor_estimado = parse_valor(value)
                else:
                    setattr(lic, field, value)
                break

    # Links para edital e anexos
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text_low = a.get_text(strip=True).lower()
        if any(kw in text_low for kw in ("edital", "termo de referência")):
            lic.url_edital = href
        elif any(href.lower().endswith(ext) for ext in (".pdf", ".zip", ".docx", ".xlsx")):
            lic.urls_anexos.append(href)

    return lic
