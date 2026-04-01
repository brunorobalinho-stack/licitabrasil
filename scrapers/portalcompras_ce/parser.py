"""Parsers para listagem e detalhe do Licitaweb."""

import re
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger

from .models import LicitacaoCE


def parse_listing_page(html: str) -> list[LicitacaoCE]:
    """Extrai registros da tabela de listagem."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="formularioDeCrud:pagedDataTable")
    if not table:
        return []

    rows = table.find_all("tr")[1:]  # skip header
    results = []

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 8:
            continue

        try:
            # col[1]: Publicacao Sequencial
            pub_num = cells[1].get_text(strip=True)
            if not pub_num or "/" not in pub_num:
                continue

            # col[2]: Status
            status = cells[2].get_text(strip=True)

            # col[3]: Num Processo
            num_processo = cells[3].get_text(strip=True)

            # col[4]: Objeto (may have tooltip with full text)
            objeto_el = cells[4]
            tooltip = objeto_el.find("span", class_="rich-tool-tip")
            objeto = tooltip.get_text(strip=True) if tooltip else objeto_el.get_text(strip=True)

            # col[5]: Num Edital - Contratante - Entrega
            edital_orgao = cells[5].get_text(strip=True)
            num_edital = ""
            orgao = edital_orgao
            if " - " in edital_orgao:
                parts = edital_orgao.split(" - ", 1)
                num_edital = parts[0].strip()
                orgao = parts[1].strip() if len(parts) > 1 else ""
                # Remove trailing " -" if present
                orgao = re.sub(r"\s*-\s*$", "", orgao)

            # col[6]: Sistematica - Forma de Aquisicao
            sist_forma = cells[6].get_text(strip=True)
            tooltip6 = cells[6].find("span", class_="rich-tool-tip")
            if tooltip6:
                sist_forma = tooltip6.get_text(strip=True)
            sistematica = ""
            forma = ""
            if " - " in sist_forma:
                # Sometimes duplicated: "DISPENSA -  COTACAO ELETRONICADISPENSA -  COTACAO ELETRONICA"
                # Take first half
                half = sist_forma[:len(sist_forma) // 2] if sist_forma[len(sist_forma) // 2:] == sist_forma[:len(sist_forma) // 2] else sist_forma
                parts = half.split(" - ", 1)
                sistematica = parts[0].strip()
                forma = parts[1].strip() if len(parts) > 1 else ""
            else:
                sistematica = sist_forma

            # Clean trailing " -" from sistematica (when forma is absent)
            sistematica = re.sub(r"\s*-\s*$", "", sistematica)
            forma = re.sub(r"\s*-\s*$", "", forma)

            # col[7]: Acolhimento - Abertura
            datas = cells[7].get_text(strip=True)
            data_acolhimento = None
            data_abertura = None
            if " - " in datas:
                date_parts = datas.split(" - ")
                data_acolhimento = date_parts[0].strip() or None
                data_abertura = date_parts[1].strip() if len(date_parts) > 1 else None

            results.append(LicitacaoCE(
                numero_publicacao=pub_num,
                numero_processo=num_processo,
                numero_edital=num_edital,
                orgao=orgao,
                objeto=objeto,
                sistematica=sistematica,
                forma_aquisicao=forma,
                status=status,
                data_acolhimento=data_acolhimento,
                data_abertura=data_abertura,
            ))
        except Exception as e:
            logger.warning(f"Failed to parse listing row: {e}")

    return results


def parse_total_records(html: str) -> int:
    """Extrai total de registros da paginacao."""
    soup = BeautifulSoup(html, "html.parser")
    pag = soup.find("div", class_="numeracaoPagina")
    if not pag:
        return 0
    text = pag.get_text(strip=True)
    # Format: "1 a 10 de 340890|"
    match = re.search(r"de\s+([\d.]+)", text)
    if match:
        return int(match.group(1).replace(".", ""))
    return 0


def parse_total_pages(html: str) -> int:
    """Calcula total de paginas."""
    total = parse_total_records(html)
    if total == 0:
        return 0
    return (total + 9) // 10  # 10 items per page


def parse_detail_page(html: str, publicacao: str) -> Optional[LicitacaoCE]:
    """Extrai dados completos da pagina de detalhe.

    Suporta dois templates:
    - Licitacao.seam (DISPENSA / Cotação Eletrônica) — acesso via GET direto
    - Publicacao.seam (todos os outros tipos) — acesso via JSF navigation
    """
    soup = BeautifulSoup(html, "html.parser")

    def get_decoration(name: str) -> str:
        el = soup.find(id=re.compile(f"formularioDeCrud:{name}"))
        if not el:
            return ""
        return el.get_text(strip=True)

    def extract_multi(text: str, labels: list[str]) -> str:
        """Tenta remover cada label prefix, retorna o primeiro match."""
        for label in labels:
            if label in text:
                return text.replace(label, "", 1).strip()
        return text.strip()

    try:
        # Orgao — Licitacao.seam: "Promotor da Licitação" / Publicacao.seam: "Órgão/Entidade Contratante:"
        orgao_raw = get_decoration("promotorCotacaoDecoration")
        orgao = extract_multi(orgao_raw, [
            "Promotor da Licitação", "Promotor da Licita\xe7\xe3o",
            "Órgão/Entidade Contratante:", "\xd3rg\xe3o/Entidade Contratante:",
        ])

        # Gestor — "Gestor de Compras" / "Gestor Contratante:"
        gestor_raw = get_decoration("gestorComprasDecoration")
        gestor = extract_multi(gestor_raw, [
            "Gestor de Compras", "Gestor Contratante:",
        ])

        # Numero publicacao — "Nº da Publicação"
        pub_raw = get_decoration("numeroCoepDecoration")
        pub_num = extract_multi(pub_raw, [
            "Nº da Publicação", "N\xba da Publica\xe7\xe3o",
        ])
        if not pub_num or "/" not in pub_num:
            pub_num = publicacao

        # Processo
        proc_raw = get_decoration("numeroViprocDecoration")
        processo = extract_multi(proc_raw, ["Nº Processo:", "N\xba Processo:"])

        # Edital
        edital_raw = get_decoration("numeroTermoParticipacaoDecoration")
        edital = extract_multi(edital_raw, ["Nº do Edital:", "N\xba do Edital:"])

        # Status — "Status da Cotação" / "Status da Publicação"
        status_raw = get_decoration("statusDecoration")
        status = extract_multi(status_raw, [
            "Status da Cotação", "Status da Cota\xe7\xe3o",
            "Status da Publicação", "Status da Publica\xe7\xe3o",
        ])

        # PNCP (só Licitacao.seam)
        pncp_el = soup.find(id=re.compile(r"idPncpDecoration:j_id\d+"))
        pncp = pncp_el.get_text(strip=True) if pncp_el else None

        # Natureza/Tipo
        nat_raw = get_decoration("naturezaAquisicaoDecoration")
        natureza = extract_multi(nat_raw, [
            "Natureza da Aquisição:", "Natureza da Aquisi\xe7\xe3o:",
        ])

        tipo_raw = get_decoration("tipoAquisicaoDecoration")
        tipo = extract_multi(tipo_raw, [
            "Tipo de Aquisição:", "Tipo de Aquisi\xe7\xe3o:",
        ])

        # Moeda
        moeda_raw = get_decoration("moedaDecoration")
        moeda = extract_multi(moeda_raw, ["Moeda:"])

        # Datas — "Acolhimento:" / "Inicio Esperando Realização:"
        acol_raw = get_decoration("inicioAcolhimentoDecoration")
        acolhimento = extract_multi(acol_raw, [
            "Acolhimento:",
            "Inicio Esperando Realização:", "Inicio Esperando Realiza\xe7\xe3o:",
        ])

        # Abertura — "Abertura:" / "Abertura Propostas:"
        abert_raw = get_decoration("fimAcolhimentoDecoration")
        abertura = extract_multi(abert_raw, [
            "Abertura:", "Abertura Propostas:",
        ])

        # Objeto — pode ter prefix "Objeto da Contratação" no Publicacao.seam
        objeto_el = soup.find(id=re.compile(r"objetoCotacaoDecoration:objetoCoep"))
        objeto = objeto_el.get_text(strip=True) if objeto_el else ""
        for prefix in ["Objeto da Contratação", "Objeto da Contrata\xe7\xe3o"]:
            if objeto.startswith(prefix):
                objeto = objeto[len(prefix):].strip()
                break

        # Winner — tenta ambas as tabelas
        vencedor = None
        valor_lance = None

        # Licitacao.seam: grupoItensCoEPDataTable (col 3 = fornecedor, col 4 = lance)
        groups_table = soup.find("table", id="formularioDeCrud:grupoItensCoEPDataTable")
        if groups_table:
            for row in groups_table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) >= 5:
                    fornecedor_text = cells[3].get_text(strip=True)
                    if "Vencedor:" in fornecedor_text:
                        vencedor = fornecedor_text.replace("Vencedor:", "").strip()
                    lance_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    if lance_text:
                        valor_lance = lance_text

        # Publicacao.seam: itemLicitacaoDataTable (col varies, look for "Vencedor:" anywhere)
        if not vencedor:
            items_table = soup.find("table", id="formularioDeCrud:itemLicitacaoDataTable")
            if items_table:
                for row in items_table.find_all("tr")[1:]:
                    cells = row.find_all("td")
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        if "Vencedor:" in text:
                            # Format: "Vencedor: 27.595.780/0001-16 | CS BRASIL"
                            raw = text.replace("Vencedor:", "").strip()
                            # Extract name after pipe if present
                            if "|" in raw:
                                vencedor = raw.split("|", 1)[1].strip()
                            else:
                                vencedor = raw
                    # Valor contratado (penúltima ou última coluna numérica)
                    if not valor_lance and len(cells) >= 8:
                        val_text = cells[-2].get_text(strip=True)
                        if val_text and re.match(r"[\d.,]+", val_text):
                            valor_lance = val_text

        # Documents (só Licitacao.seam tem docTermoListAction)
        docs = []
        doc_table = soup.find("table", id="formularioDeCrud:docTermoListAction")
        if doc_table:
            for span in doc_table.find_all("span", id=re.compile(r"docTermo$")):
                doc_name = span.get_text(strip=True)
                if doc_name:
                    docs.append(doc_name)

        # Detect which template for the URL
        is_publicacao = "itemLicitacaoDataTable" in html or "Status da Publicação" in html or "Status da Publica" in html
        if is_publicacao:
            url = f"https://s2gpr.sefaz.ce.gov.br/licita-web/paginas/licita/Publicacao.seam?nuPublicacao={publicacao}"
        else:
            url = f"https://s2gpr.sefaz.ce.gov.br/licita-web/paginas/licita/Licitacao.seam?nuPublicacao={publicacao}"

        return LicitacaoCE(
            numero_publicacao=pub_num,
            numero_processo=processo,
            numero_edital=edital,
            id_pncp=pncp,
            orgao=orgao,
            gestor_compras=gestor or None,
            objeto=objeto,
            natureza_aquisicao=natureza or None,
            tipo_aquisicao=tipo or None,
            moeda=moeda or None,
            data_acolhimento=acolhimento or None,
            data_abertura=abertura or None,
            status=status,
            vencedor=vencedor,
            valor_lance=valor_lance,
            documentos=docs,
            url_detalhe=url,
            tem_detalhe=True,
        )
    except Exception as e:
        logger.warning(f"Failed to parse detail for {publicacao}: {e}")
        return None
