"""EditalExtractor — extrai dados estruturados de editais em PDF/DOCX.

Usa pdfplumber para PDFs e python-docx para DOCX. Identifica seções
via regex patterns + heurística de headers (CLÁUSULA, SEÇÃO, CAPÍTULO).

Seções identificadas:
    OBJETO, VALOR, HABILITACAO, PRAZOS, JULGAMENTO, PAGAMENTO,
    PENALIDADES, IMPUGNACAO, PROPOSTA, GARANTIA, SUBCONTRATACAO,
    CONSORCIO, VISITA, AMOSTRA
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models de saída
# ---------------------------------------------------------------------------

class SecaoEdital(BaseModel):
    """Seção identificada no edital."""

    tipo: str
    texto: str
    pagina_inicio: int
    pagina_fim: int
    confianca: float = Field(ge=0.0, le=1.0)


class HabilitacaoDetalhada(BaseModel):
    """Requisitos de habilitação categorizados."""

    juridica: list[str] = Field(default_factory=list)
    tecnica: list[str] = Field(default_factory=list)
    economico_financeira: list[str] = Field(default_factory=list)
    fiscal: list[str] = Field(default_factory=list)
    outros: list[str] = Field(default_factory=list)


class GarantiaContratual(BaseModel):
    """Info sobre garantia contratual."""

    exige: bool = False
    percentual: float | None = None
    descricao: str | None = None


class EditalExtraido(BaseModel):
    """Resultado da extração de um edital."""

    arquivo: str
    total_paginas: int

    # 1. Objeto
    objeto: str | None = None

    # 2. Valor
    valor_estimado: Decimal | None = None

    # 3. Habilitação
    requisitos_habilitacao: list[str] = Field(default_factory=list)
    habilitacao_detalhada: HabilitacaoDetalhada = Field(default_factory=HabilitacaoDetalhada)

    # 4. Prazos
    data_abertura: datetime | None = None
    prazos: dict[str, str] = Field(default_factory=dict)

    # 5. Critério de julgamento
    criterio_julgamento: str | None = None

    # 6. Tratamento diferenciado ME/EPP
    exclusiva_me_epp: bool | None = None
    cota_reservada: bool | None = None
    margem_preferencia: bool | None = None

    # 7. Garantia contratual
    garantia: GarantiaContratual = Field(default_factory=GarantiaContratual)

    # 8. Subcontratação
    permite_subcontratacao: bool | None = None

    # 9. Consórcio
    permite_consorcio: bool | None = None

    # 10. Visita técnica
    visita_tecnica: str | None = None  # "obrigatoria", "facultativa", None

    # 11. Amostra
    exige_amostra: bool | None = None

    # 12. Penalidades
    penalidades: list[str] = Field(default_factory=list)

    # Meta
    secoes: list[SecaoEdital] = Field(default_factory=list)
    metadados: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Regex patterns para seções de editais
# ---------------------------------------------------------------------------

SECAO_PATTERNS: dict[str, list[re.Pattern]] = {
    "OBJETO": [
        re.compile(r"(?:DO\s+OBJETO|OBJETO\s+DA\s+LICITA[ÇC][ÃA]O)", re.IGNORECASE),
        re.compile(r"CL[AÁ]USULA\s+(?:PRIMEIRA|1[ªa]?)\s*[.:\-–]+\s*(?:DO\s+)?OBJETO", re.IGNORECASE),
    ],
    "HABILITACAO": [
        re.compile(r"(?:DA\s+HABILITA[ÇC][ÃA]O|DOCUMENTOS?\s+DE\s+HABILITA[ÇC][ÃA]O)", re.IGNORECASE),
        re.compile(r"REQUISITOS?\s+(?:DE\s+)?HABILITA[ÇC][ÃA]O", re.IGNORECASE),
    ],
    "PRAZOS": [
        re.compile(r"(?:DOS?\s+PRAZOS?|DATA\s+(?:DE\s+)?ABERTURA)", re.IGNORECASE),
        re.compile(r"CRONOGRAMA", re.IGNORECASE),
    ],
    "VALOR": [
        re.compile(r"(?:DO\s+VALOR|VALOR\s+(?:ESTIMADO|M[AÁ]XIMO|DE\s+REFER[EÊ]NCIA|GLOBAL))", re.IGNORECASE),
        re.compile(r"PRE[ÇC]O\s+(?:M[AÁ]XIMO|DE\s+REFER[EÊ]NCIA)", re.IGNORECASE),
    ],
    "JULGAMENTO": [
        re.compile(r"(?:DO\s+JULGAMENTO|CRIT[EÉ]RIO\s+DE\s+JULGAMENTO)", re.IGNORECASE),
        re.compile(r"TIPO\s+DE\s+LICITA[ÇC][ÃA]O", re.IGNORECASE),
    ],
    "PAGAMENTO": [
        re.compile(r"(?:DO\s+PAGAMENTO|CONDI[ÇC][OÕ]ES\s+DE\s+PAGAMENTO)", re.IGNORECASE),
    ],
    "PENALIDADES": [
        re.compile(r"(?:DAS?\s+PENALIDADES?|DAS?\s+SAN[ÇC][OÕ]ES)", re.IGNORECASE),
        re.compile(r"MULTAS?\s+E\s+SAN[ÇC][OÕ]ES", re.IGNORECASE),
    ],
    "IMPUGNACAO": [
        re.compile(r"(?:DA\s+IMPUGNA[ÇC][ÃA]O|ESCLARECIMENTOS?)", re.IGNORECASE),
    ],
    "PROPOSTA": [
        re.compile(r"(?:DA\s+PROPOSTA|PROPOSTAS?\s+(?:DE\s+)?PRE[ÇC]OS?)", re.IGNORECASE),
    ],
    "GARANTIA": [
        re.compile(r"(?:DA\s+GARANTIA|GARANTIA\s+(?:CONTRATUAL|DE\s+EXECU[ÇC][ÃA]O))", re.IGNORECASE),
    ],
    "SUBCONTRATACAO": [
        re.compile(r"(?:DA\s+SUBCONTRATA[ÇC][ÃA]O|SUBCONTRATA[ÇC][ÃA]O)", re.IGNORECASE),
    ],
    "CONSORCIO": [
        re.compile(r"(?:DO\s+CONS[OÓ]RCIO|PARTICIPA[ÇC][ÃA]O\s+(?:DE\s+)?CONS[OÓ]RCIOS?)", re.IGNORECASE),
    ],
    "VISITA": [
        re.compile(r"(?:DA\s+VISITA\s+T[EÉ]CNICA|VISITA[ÇC][ÃA]O\s+T[EÉ]CNICA)", re.IGNORECASE),
        re.compile(r"VISTORIA", re.IGNORECASE),
    ],
    "AMOSTRA": [
        re.compile(r"(?:DA\s+AMOSTRA|APRESENTA[ÇC][ÃA]O\s+DE\s+AMOSTRAS?)", re.IGNORECASE),
    ],
}

# Pattern para valores monetários
VALOR_PATTERN = re.compile(
    r"R\$\s*([\d.,]+(?:\s*(?:milh[oõ]es?|mil|bi(?:lh[oõ]es?)))?)",
    re.IGNORECASE,
)

# Pattern para datas brasileiras
DATA_PATTERN = re.compile(
    r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{2,4})"
    r"(?:\s+(?:[aà]s?\s+)?(\d{1,2})\s*[h:]\s*(\d{0,2}))?"
)

# Pattern para critérios de julgamento
JULGAMENTO_PATTERN = re.compile(
    r"(?:menor\s+pre[çc]o|melhor\s+t[eé]cnica|t[eé]cnica\s+e\s+pre[çc]o|maior\s+desconto|maior\s+lance)",
    re.IGNORECASE,
)

# Pattern para ME/EPP
ME_EPP_PATTERN = re.compile(
    r"(?:exclusiv\w*|reservad\w*)\s+.*?"
    r"(?:ME|EPP|micro\s*empresa|empresa\s+de\s+pequeno\s+porte)",
    re.IGNORECASE,
)

# Cota reservada
COTA_RESERVADA_PATTERN = re.compile(
    r"cota\s+(?:de\s+)?(?:\d+%?\s+)?reservad[ao]",
    re.IGNORECASE,
)

# Margem de preferência
MARGEM_PATTERN = re.compile(
    r"margem\s+de\s+prefer[eê]ncia",
    re.IGNORECASE,
)

# Garantia percentual
GARANTIA_PCT_PATTERN = re.compile(
    r"garantia\s+.*?(\d+)\s*%",
    re.IGNORECASE,
)

# Subcontratação
SUBCONTRATACAO_PERMITE = re.compile(
    r"(?:permitid[ao]|autorizada?|admitid[ao])\s+.*?subcontrata[çc][ãa]o"
    r"|subcontrata[çc][ãa]o\s+.*?(?:permitid[ao]|autorizada?|admitid[ao])",
    re.IGNORECASE,
)
SUBCONTRATACAO_VEDA = re.compile(
    r"(?:vedad[ao]|proibid[ao]|n[ãa]o\s+(?:ser[aá]\s+)?(?:permitid[ao]|admitid[ao]))\s+.*?subcontrata[çc][ãa]o"
    r"|subcontrata[çc][ãa]o\s+.*?(?:vedad[ao]|proibid[ao])",
    re.IGNORECASE,
)

# Consórcio
CONSORCIO_PERMITE = re.compile(
    r"(?:permitid[ao]|autorizada?|admitid[ao])\s+.*?cons[oó]rcio"
    r"|cons[oó]rcio\s+.*?(?:permitid[ao]|autorizada?|admitid[ao])",
    re.IGNORECASE,
)
CONSORCIO_VEDA = re.compile(
    r"(?:vedad[ao]|proibid[ao]|n[ãa]o\s+(?:ser[aá]\s+)?(?:permitid[ao]|admitid[ao]))\s+.*?cons[oó]rcio"
    r"|cons[oó]rcio\s+.*?(?:vedad[ao]|proibid[ao]|n[ãa]o\s+(?:ser[aá]\s+)?(?:permitid[ao]|admitid[ao]))",
    re.IGNORECASE,
)

# Visita técnica
VISITA_OBRIGATORIA = re.compile(
    r"visita\s+t[eé]cnica\s+.*?obrigat[oó]ri[ao]"
    r"|obrigat[oó]ri[ao]\s+.*?visita\s+t[eé]cnica",
    re.IGNORECASE,
)
VISITA_FACULTATIVA = re.compile(
    r"visita\s+t[eé]cnica\s+.*?facultativ[ao]"
    r"|facultativ[ao]\s+.*?visita\s+t[eé]cnica",
    re.IGNORECASE,
)

# Amostra
AMOSTRA_PATTERN = re.compile(
    r"(?:apresenta[çc][ãa]o|entrega|exig[eê]ncia)\s+(?:de\s+)?amostra",
    re.IGNORECASE,
)

# Categorias de habilitação
_HAB_CATEGORIAS = {
    "juridica": [
        "contrato social", "estatuto", "requerimento de empresário",
        "registro comercial", "ato constitutivo", "cnpj",
        "registro na junta", "procuração",
    ],
    "tecnica": [
        "atestado de capacidade", "atestado técnico", "registro no crea",
        "registro no cau", "certidão de acervo", "cat ",
        "responsável técnico", "qualificação técnica",
    ],
    "economico_financeira": [
        "balanço patrimonial", "demonstrações contábeis",
        "certidão negativa de falência", "certidão de falência",
        "índice de liquidez", "patrimônio líquido",
        "capital social", "qualificação econômico",
    ],
    "fiscal": [
        "certidão negativa de débit", "cnd", "regularidade fiscal",
        "fgts", "inss", "certidão federal", "certidão estadual",
        "certidão municipal", "fazenda", "receita federal",
        "receita estadual", "tributos",
    ],
}

# Header heurístico (CLÁUSULA, SEÇÃO, CAPÍTULO, item numerado)
HEADER_PATTERN = re.compile(
    r"^(?:"
    r"CL[AÁ]USULA\s+\w+"
    r"|SE[ÇC][ÃA]O\s+\w+"
    r"|CAP[IÍ]TULO\s+\w+"
    r"|\d{1,2}(?:\.\d{1,2})*\s*[.)\-–]\s*[A-ZÀ-Ú]"
    r")",
    re.MULTILINE | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Extração de texto
# ---------------------------------------------------------------------------

def _extrair_texto_pdf(path: Path) -> tuple[list[str], int]:
    """Extrai texto de um PDF página por página."""
    pages_text: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        total = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)
    return pages_text, total


def _extrair_texto_docx(path: Path) -> tuple[list[str], int]:
    """Extrai texto de um DOCX.

    Retorna todo o conteúdo como uma única "página" (DOCX não tem
    paginação física confiável).
    """
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "python-docx é necessário para processar DOCX. "
            "Instale com: pip install python-docx"
        )

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)
    return [full_text], 1


# ---------------------------------------------------------------------------
# Extrator
# ---------------------------------------------------------------------------

class EditalExtractor:
    """Extrai dados estruturados de editais em PDF/DOCX.

    Estratégia de extração:
    - Regex patterns para seções padrão (DO/DOU formatação)
    - Heurística de headers (CLÁUSULA, SEÇÃO, CAPÍTULO, item numerado)
    - Detecção booleana para flags (consórcio, subcontratação, etc.)
    """

    def extrair(self, path: str | Path) -> EditalExtraido:
        """Extrai informações de um edital PDF ou DOCX."""
        path = Path(path)

        suffix = path.suffix.lower()
        if suffix not in (".pdf", ".docx", ".doc"):
            raise ValueError(f"Formato não suportado: {suffix}. Use PDF ou DOCX.")

        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")

        logger.info("Extraindo edital: %s", path.name)

        if suffix == ".pdf":
            pages_text, total_paginas = _extrair_texto_pdf(path)
        else:
            pages_text, total_paginas = _extrair_texto_docx(path)

        texto_completo = "\n".join(pages_text)

        # Identificar seções
        secoes = self._identificar_secoes(pages_text)

        # Extrair campos
        objeto = self._extrair_objeto(secoes, texto_completo)
        valor = self._extrair_valor(secoes, texto_completo)
        data_abertura = self._extrair_data_abertura(secoes, texto_completo)
        criterio = self._extrair_criterio_julgamento(secoes, texto_completo)
        me_epp = self._detectar_me_epp(texto_completo)
        cota = self._detectar_cota_reservada(texto_completo)
        margem = self._detectar_margem_preferencia(texto_completo)
        requisitos = self._extrair_requisitos_habilitacao(secoes)
        hab_detalhada = self._categorizar_habilitacao(secoes, texto_completo)
        prazos = self._extrair_prazos(secoes, texto_completo)
        garantia = self._extrair_garantia(secoes, texto_completo)
        subcontratacao = self._detectar_subcontratacao(secoes, texto_completo)
        consorcio = self._detectar_consorcio(secoes, texto_completo)
        visita = self._detectar_visita_tecnica(secoes, texto_completo)
        amostra = self._detectar_amostra(secoes, texto_completo)
        penalidades = self._extrair_penalidades(secoes)

        return EditalExtraido(
            arquivo=path.name,
            total_paginas=total_paginas,
            objeto=objeto,
            valor_estimado=valor,
            data_abertura=data_abertura,
            criterio_julgamento=criterio,
            exclusiva_me_epp=me_epp,
            cota_reservada=cota,
            margem_preferencia=margem,
            requisitos_habilitacao=requisitos,
            habilitacao_detalhada=hab_detalhada,
            prazos=prazos,
            garantia=garantia,
            permite_subcontratacao=subcontratacao,
            permite_consorcio=consorcio,
            visita_tecnica=visita,
            exige_amostra=amostra,
            penalidades=penalidades,
            secoes=secoes,
            metadados={"total_caracteres": len(texto_completo)},
        )

    # ----- Seções -----

    def _identificar_secoes(self, pages_text: list[str]) -> list[SecaoEdital]:
        """Identifica seções do edital usando regex patterns."""
        secoes: list[SecaoEdital] = []

        for tipo, patterns in SECAO_PATTERNS.items():
            for page_idx, page_text in enumerate(pages_text):
                for pattern in patterns:
                    match = pattern.search(page_text)
                    if match:
                        # Extrai texto após o header da seção até próximo header ou fim da página
                        start = match.end()
                        texto_secao = page_text[start:].strip()

                        # Tenta cortar no próximo header
                        next_header = HEADER_PATTERN.search(texto_secao)
                        if next_header and next_header.start() > 50:
                            texto_secao = texto_secao[:next_header.start()].strip()

                        # Limita a 2000 chars por seção
                        if len(texto_secao) > 2000:
                            texto_secao = texto_secao[:2000] + "..."

                        confianca = 0.8 if pattern == patterns[0] else 0.6

                        secoes.append(SecaoEdital(
                            tipo=tipo,
                            texto=texto_secao,
                            pagina_inicio=page_idx + 1,
                            pagina_fim=page_idx + 1,
                            confianca=confianca,
                        ))
                        break  # Só 1 match por tipo por página

        return secoes

    # ----- 1. Objeto -----

    def _extrair_objeto(self, secoes: list[SecaoEdital], texto: str) -> str | None:
        """Extrai descrição do objeto da licitação."""
        for s in secoes:
            if s.tipo == "OBJETO" and s.texto:
                linhas = s.texto.split("\n")
                for linha in linhas:
                    if len(linha.strip()) > 30:
                        return linha.strip()[:500]
                return s.texto[:500]
        return None

    # ----- 2. Valor -----

    def _extrair_valor(self, secoes: list[SecaoEdital], texto: str) -> Decimal | None:
        """Extrai valor estimado."""
        for s in secoes:
            if s.tipo == "VALOR":
                valor = self._parse_primeiro_valor(s.texto)
                if valor:
                    return valor

        idx = texto.lower().find("valor estimado")
        if idx >= 0:
            trecho = texto[idx:idx + 200]
            return self._parse_primeiro_valor(trecho)
        return None

    def _parse_primeiro_valor(self, texto: str) -> Decimal | None:
        """Extrai o primeiro valor R$ de um trecho de texto."""
        match = VALOR_PATTERN.search(texto)
        if not match:
            return None
        raw = match.group(1).strip()
        raw = re.sub(r"\s*(milh[oõ]es?|mil|bi(?:lh[oõ]es?))", "", raw, flags=re.IGNORECASE)
        raw = raw.strip().rstrip(".")
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "." in raw:
            raw = raw.replace(".", "")
        try:
            return Decimal(raw)
        except InvalidOperation:
            return None

    # ----- 3. Habilitação -----

    def _extrair_requisitos_habilitacao(self, secoes: list[SecaoEdital]) -> list[str]:
        """Extrai requisitos de habilitação (lista flat)."""
        requisitos = []
        for s in secoes:
            if s.tipo == "HABILITACAO":
                for linha in s.texto.split("\n"):
                    linha = linha.strip()
                    if re.match(r"^[a-z\d]{1,3}[.)]\s", linha):
                        requisitos.append(linha[:200])
                    elif len(linha) > 20 and any(kw in linha.lower() for kw in [
                        "certidão", "atestado", "balanço", "registro", "alvará",
                        "declaração", "comprovante", "contrato social",
                    ]):
                        requisitos.append(linha[:200])
        return requisitos[:30]

    def _categorizar_habilitacao(
        self, secoes: list[SecaoEdital], texto: str
    ) -> HabilitacaoDetalhada:
        """Categoriza requisitos de habilitação em jurídica, técnica, etc."""
        hab = HabilitacaoDetalhada()

        # Junta todo texto de seções HABILITACAO
        hab_texto = ""
        for s in secoes:
            if s.tipo == "HABILITACAO":
                hab_texto += s.texto + "\n"

        if not hab_texto:
            # Fallback: busca no texto completo
            idx = texto.lower().find("habilitação")
            if idx >= 0:
                hab_texto = texto[idx:idx + 3000]

        if not hab_texto:
            return hab

        linhas = [line.strip() for line in hab_texto.split("\n") if len(line.strip()) > 15]

        for linha in linhas:
            lower = linha.lower()
            categorizada = False
            for categoria, keywords in _HAB_CATEGORIAS.items():
                if any(kw in lower for kw in keywords):
                    getattr(hab, categoria).append(linha[:200])
                    categorizada = True
                    break
            if not categorizada and re.match(r"^[a-z\d]{1,3}[.)]\s", linha):
                hab.outros.append(linha[:200])

        # Limita cada lista
        for campo in ["juridica", "tecnica", "economico_financeira", "fiscal", "outros"]:
            items = getattr(hab, campo)
            if len(items) > 15:
                setattr(hab, campo, items[:15])

        return hab

    # ----- 4. Prazos -----

    def _extrair_data_abertura(self, secoes: list[SecaoEdital], texto: str) -> datetime | None:
        """Extrai data de abertura."""
        for s in secoes:
            if s.tipo == "PRAZOS":
                dt = self._parse_primeira_data(s.texto)
                if dt:
                    return dt

        for keyword in ["data de abertura", "data da abertura", "abertura da sessão", "sessão pública"]:
            idx = texto.lower().find(keyword)
            if idx >= 0:
                trecho = texto[idx:idx + 150]
                dt = self._parse_primeira_data(trecho)
                if dt:
                    return dt
        return None

    def _extrair_prazos(self, secoes: list[SecaoEdital], texto: str) -> dict[str, str]:
        """Extrai prazos relevantes."""
        prazos: dict[str, str] = {}

        keywords_prazos = {
            "abertura": ["abertura", "sessão pública", "recebimento das propostas"],
            "impugnacao": ["impugnação", "impugnar"],
            "esclarecimento": ["esclarecimento", "pedidos de esclarecimento"],
            "recurso": ["recurso", "prazo recursal"],
            "vigencia": ["vigência", "prazo de vigência", "prazo contratual"],
        }

        search_text = texto
        for s in secoes:
            if s.tipo == "PRAZOS":
                search_text = s.texto + "\n" + texto
                break

        for key, keywords in keywords_prazos.items():
            for kw in keywords:
                idx = search_text.lower().find(kw)
                if idx >= 0:
                    trecho = search_text[idx:idx + 150]
                    dt = self._parse_primeira_data(trecho)
                    if dt:
                        prazos[key] = dt.isoformat()
                        break
        return prazos

    def _parse_primeira_data(self, texto: str) -> datetime | None:
        """Parse a primeira data BR encontrada no texto."""
        match = DATA_PATTERN.search(texto)
        if not match:
            return None
        dia, mes, ano = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if ano < 100:
            ano += 2000
        hora = int(match.group(4)) if match.group(4) else 0
        minuto = int(match.group(5)) if match.group(5) else 0
        try:
            return datetime(ano, mes, dia, hora, minuto)
        except ValueError:
            return None

    # ----- 5. Critério de julgamento -----

    def _extrair_criterio_julgamento(self, secoes: list[SecaoEdital], texto: str) -> str | None:
        """Extrai critério de julgamento."""
        for s in secoes:
            if s.tipo == "JULGAMENTO":
                match = JULGAMENTO_PATTERN.search(s.texto)
                if match:
                    return match.group(0).strip().lower()

        match = JULGAMENTO_PATTERN.search(texto)
        if match:
            return match.group(0).strip().lower()
        return None

    # ----- 6. Tratamento diferenciado ME/EPP -----

    def _detectar_me_epp(self, texto: str) -> bool | None:
        """Detecta se é exclusiva para ME/EPP."""
        if ME_EPP_PATTERN.search(texto):
            return True
        lower = texto.lower()
        if "exclusiv" in lower and ("me/epp" in lower or "microempresa" in lower):
            return True
        return False

    def _detectar_cota_reservada(self, texto: str) -> bool | None:
        """Detecta cota reservada para ME/EPP (Art. 48 LC 123/2006)."""
        return bool(COTA_RESERVADA_PATTERN.search(texto))

    def _detectar_margem_preferencia(self, texto: str) -> bool | None:
        """Detecta margem de preferência."""
        return bool(MARGEM_PATTERN.search(texto))

    # ----- 7. Garantia -----

    def _extrair_garantia(self, secoes: list[SecaoEdital], texto: str) -> GarantiaContratual:
        """Extrai informações sobre garantia contratual."""
        search_text = ""
        for s in secoes:
            if s.tipo == "GARANTIA":
                search_text = s.texto
                break

        if not search_text:
            # Busca no texto completo
            idx = texto.lower().find("garantia contratual")
            if idx < 0:
                idx = texto.lower().find("garantia de execução")
            if idx >= 0:
                search_text = texto[idx:idx + 500]

        if not search_text:
            return GarantiaContratual()

        # Detectar se exige
        lower = search_text.lower()
        exige = any(kw in lower for kw in [
            "exigida", "exigir", "deverá prestar", "prestará garantia",
            "garantia contratual", "garantia de execução",
        ])

        # Extrair percentual
        pct_match = GARANTIA_PCT_PATTERN.search(search_text)
        pct = float(pct_match.group(1)) if pct_match else None

        return GarantiaContratual(
            exige=exige,
            percentual=pct,
            descricao=search_text[:300] if exige else None,
        )

    # ----- 8-11. Detecção genérica por seção + regex -----

    @staticmethod
    def _texto_da_secao(secoes: list[SecaoEdital], tipo: str, fallback: str) -> str:
        """Retorna o texto de uma seção pelo tipo, ou fallback se não encontrada.

        Args:
            secoes: Lista de seções identificadas no edital.
            tipo: Tipo de seção a buscar (ex: ``"SUBCONTRATACAO"``).
            fallback: Texto completo do edital usado se a seção não existir.

        Returns:
            Texto da seção encontrada ou *fallback*.
        """
        for s in secoes:
            if s.tipo == tipo:
                return s.texto
        return fallback

    def _detectar_por_regex(
        self,
        secoes: list[SecaoEdital],
        texto: str,
        tipo_secao: str,
        *,
        pattern_positivo: re.Pattern[str] | None = None,
        pattern_negativo: re.Pattern[str] | None = None,
    ) -> bool | None:
        """Detecta presença/ausência de cláusula via regex em seção ou texto completo.

        Busca primeiro na seção específica; se não encontrada, busca no texto
        completo. Testa o padrão negativo antes do positivo (veda antes de permite).

        Args:
            secoes: Lista de seções identificadas.
            texto: Texto completo do edital (fallback).
            tipo_secao: Tipo da seção a buscar.
            pattern_positivo: Regex que indica presença/permissão.
            pattern_negativo: Regex que indica vedação/proibição.

        Returns:
            ``True`` se positivo, ``False`` se negativo, ``None`` se indeterminado.
        """
        search_text = self._texto_da_secao(secoes, tipo_secao, texto)
        if pattern_negativo and pattern_negativo.search(search_text):
            return False
        if pattern_positivo and pattern_positivo.search(search_text):
            return True
        return None

    def _detectar_subcontratacao(self, secoes: list[SecaoEdital], texto: str) -> bool | None:
        """Detecta se permite subcontratação."""
        return self._detectar_por_regex(
            secoes, texto, "SUBCONTRATACAO",
            pattern_positivo=SUBCONTRATACAO_PERMITE,
            pattern_negativo=SUBCONTRATACAO_VEDA,
        )

    def _detectar_consorcio(self, secoes: list[SecaoEdital], texto: str) -> bool | None:
        """Detecta se permite participação em consórcio."""
        return self._detectar_por_regex(
            secoes, texto, "CONSORCIO",
            pattern_positivo=CONSORCIO_PERMITE,
            pattern_negativo=CONSORCIO_VEDA,
        )

    def _detectar_visita_tecnica(self, secoes: list[SecaoEdital], texto: str) -> str | None:
        """Detecta se exige visita técnica e se é obrigatória/facultativa."""
        search_text = self._texto_da_secao(secoes, "VISITA", texto)
        if VISITA_OBRIGATORIA.search(search_text):
            return "obrigatoria"
        if VISITA_FACULTATIVA.search(search_text):
            return "facultativa"
        return None

    def _detectar_amostra(self, secoes: list[SecaoEdital], texto: str) -> bool | None:
        """Detecta se exige apresentação de amostra."""
        search_text = self._texto_da_secao(secoes, "AMOSTRA", texto)
        return True if AMOSTRA_PATTERN.search(search_text) else False

    # ----- 12. Penalidades -----

    def _extrair_penalidades(self, secoes: list[SecaoEdital]) -> list[str]:
        """Extrai itens de penalidade (multas, sanções)."""
        penalidades = []
        for s in secoes:
            if s.tipo == "PENALIDADES":
                for linha in s.texto.split("\n"):
                    linha = linha.strip()
                    lower = linha.lower()
                    if len(linha) > 20 and any(kw in lower for kw in [
                        "multa", "suspensão", "impedimento", "declaração de inidoneidade",
                        "advertência", "rescisão", "sanção", "%",
                    ]):
                        penalidades.append(linha[:200])
        return penalidades[:15]
